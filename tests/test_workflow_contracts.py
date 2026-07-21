from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
FULL_SHA = re.compile(r"(?m)^\s*uses:\s*[^@\s]+@([0-9a-f]{40})(?:\s*#.*)?$")


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _event_block(text: str, event: str) -> str:
    marker = f"  {event}:\n"
    start = text.index(marker) + len(marker)
    match = re.search(r"(?m)^  [a-z_]+:\s*$", text[start:])
    return text[start:] if match is None else text[start : start + match.start()]


def test_every_required_pull_request_workflow_always_instantiates() -> None:
    for name in (
        "validate.yml",
        "eval.yml",
        "compatibility.yml",
        "codeql.yml",
        "dco.yml",
        "dependency-review.yml",
    ):
        text = _workflow(name)
        assert "  pull_request:\n" in text
        assert "paths:" not in _event_block(text, "pull_request")


def test_required_check_contexts_are_stable() -> None:
    expected = {
        "validate.yml": (
            "repository contracts (Python ${{ matrix.python-version }})",
            "Python 3.14 current compatibility",
            "Rust 1.85+ asset contracts",
            "ShellCheck 0.9.0 and Actionlint 1.7.12",
            "PSScriptAnalyzer 1.25.0",
            "required-validation",
        ),
        "eval.yml": ("complete structural eval export",),
        "compatibility.yml": ("adapters and installers (${{ matrix.os }})",),
        "codeql.yml": ("codeql-python",),
        "dco.yml": ("DCO",),
        "dependency-review.yml": ("dependency-review",),
    }
    for workflow, names in expected.items():
        text = _workflow(workflow)
        for name in names:
            assert f"    name: {name}\n" in text

    validate = yaml.safe_load(_workflow("validate.yml"))
    compatibility = yaml.safe_load(_workflow("compatibility.yml"))
    assert validate["jobs"]["repository"]["strategy"]["matrix"]["python-version"] == [
        "3.11",
        "3.13",
    ]
    assert compatibility["jobs"]["adapters-and-installers"]["strategy"]["matrix"]["os"] == [
        "ubuntu-24.04",
        "macos-15",
        "windows-2025",
    ]


def test_structural_compatibility_retains_bounded_nonredundant_checks() -> None:
    workflow = yaml.safe_load(_workflow("compatibility.yml"))
    job = workflow["jobs"]["adapters-and-installers"]
    assert job["timeout-minutes"] == 20
    assert job["strategy"]["fail-fast"] is False
    bytecode_cache = "${{ runner.temp }}/genaptic-structural-pycache"

    windows_bootstrap = next(
        step
        for step in job["steps"]
        if step["name"] == "Exercise the documented Windows bootstrap path"
    )
    assert windows_bootstrap["env"] == {"PYTHONPYCACHEPREFIX": bytecode_cache}

    windows_check = next(
        step
        for step in job["steps"]
        if step["name"] == "Exercise the documented Windows full-check path"
    )
    assert windows_check["if"] == "runner.os == 'Windows'"
    assert windows_check["run"] == "./scripts/check.ps1"
    assert windows_check["env"] == {
        "PYTHONPYCACHEPREFIX": bytecode_cache,
        "PYTEST_ADDOPTS": (
            "--no-cov -n 3 --dist=loadscope --max-worker-restart=0 --durations=25 --durations-min=1"
        ),
    }
    development_inputs = (ROOT / "requirements-dev.in").read_text(encoding="utf-8")
    dependency_lock = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert development_inputs.splitlines().count("pytest-xdist==3.8.0") == 1
    assert dependency_lock.splitlines().count("pytest-xdist==3.8.0 \\") == 1
    assert not any(
        step["name"] == "Exercise PowerShell GitHub CLI capability preflights"
        for step in job["steps"]
    )

    path_safety = next(
        step
        for step in job["steps"]
        if step["name"] == "Run cross-platform filesystem safety fixtures"
    )
    assert path_safety["if"] == "runner.os != 'Windows'"
    assert "tests/test_path_safety.py" in path_safety["run"]
    assert "--no-cov" in path_safety["run"]


def test_python_current_probe_and_required_validation_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = yaml.safe_load(_workflow("validate.yml"))
    jobs = workflow["jobs"]

    repository = jobs["repository"]
    assert repository["timeout-minutes"] == 30
    assert repository["strategy"]["fail-fast"] is False

    current = jobs["python-current"]
    assert current["name"] == "Python 3.14 current compatibility"
    assert current["timeout-minutes"] == 20
    setup = next(step for step in current["steps"] if step["name"] == "Set up Python 3.14")
    assert setup["with"]["python-version"] == "3.14"
    commands = "\n".join(str(step.get("run", "")) for step in current["steps"])
    assert "python -m pytest --no-cov" in commands
    assert "skillpacks generate --check" in commands
    assert "skillpacks release python-best-practices --draft" in commands
    assert 'get_pack(Path.cwd(), "python-best-practices").tag' in commands
    assert "python-best-practices-v1.0.0-draft" not in commands
    assert '"dist/releases/${draft_tag}-draft.zip"' in commands
    assert "python -m compileall -q src tools tests packs" in commands

    aggregate = jobs["required-validation"]
    assert aggregate["name"] == "required-validation"
    assert aggregate["if"] == "${{ always() }}"
    assert aggregate["needs"] == [
        "repository",
        "rust-assets",
        "shell-and-workflow-lint",
        "powershell-lint",
    ]
    assert aggregate["env"] == {
        "REPOSITORY_RESULT": "${{ needs.repository.result }}",
        "RUST_ASSETS_RESULT": "${{ needs.rust-assets.result }}",
        "SHELL_AND_WORKFLOW_LINT_RESULT": "${{ needs.shell-and-workflow-lint.result }}",
        "POWERSHELL_LINT_RESULT": "${{ needs.powershell-lint.result }}",
    }
    assert all("uses" not in step for step in aggregate["steps"])
    assert all(not step.get("continue-on-error", False) for step in aggregate["steps"])
    script = aggregate["steps"][0]["run"]

    result_variables = (
        "REPOSITORY_RESULT",
        "RUST_ASSETS_RESULT",
        "SHELL_AND_WORKFLOW_LINT_RESULT",
        "POWERSHELL_LINT_RESULT",
    )
    for variable in result_variables:
        monkeypatch.setenv(variable, "success")
    exec(compile(script, "validate.yml:required-validation", "exec"), {})

    for failed_variable in result_variables:
        for rejected in ("failure", "cancelled", "skipped", "", "unknown"):
            for variable in result_variables:
                monkeypatch.setenv(variable, "success")
            monkeypatch.setenv(failed_variable, rejected)
            with pytest.raises(SystemExit, match="required validation did not succeed"):
                exec(compile(script, "validate.yml:required-validation", "exec"), {})


def test_all_external_actions_are_pinned_and_pull_request_target_is_absent() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        assert "pull_request_target" not in text
        uses_lines = re.findall(r"(?m)^\s*uses:\s*[^\n]+$", text)
        assert len(FULL_SHA.findall(text)) == len(uses_lines), path


def test_validate_checkouts_fetch_history_for_published_source_materialization() -> None:
    workflow = yaml.safe_load(_workflow("validate.yml"))
    for job_name, job in workflow["jobs"].items():
        checkout = next(
            (
                step
                for step in job.get("steps", [])
                if str(step.get("uses", "")).startswith("actions/checkout@")
            ),
            None,
        )
        if checkout is not None:
            assert checkout["with"]["fetch-depth"] == 0, job_name


def test_candidate_preview_is_a_read_only_ci_artifact() -> None:
    workflow = yaml.safe_load(_workflow("validate.yml"))
    repository = workflow["jobs"]["repository"]
    upload = next(
        step
        for step in repository["steps"]
        if step["name"] == "Upload candidate preview distributions"
    )
    assert upload["if"] == "matrix.python-version == '3.11'"
    assert upload["with"]["path"] == "dist/preview"
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["include-hidden-files"] is True
    assert workflow["permissions"] == {"contents": "read"}


def test_embedded_python_steps_compile() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in workflow["jobs"].items():
            for index, step in enumerate(job.get("steps", [])):
                if step.get("shell") == "python":
                    compile(step["run"], f"{path.name}:{job_name}:step-{index}", "exec")


def test_release_precheckout_validators_enforce_strict_semver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = yaml.safe_load(_workflow("release.yml"))
    scripts = [
        next(
            step["run"]
            for step in workflow["jobs"][job]["steps"]
            if step["name"]
            in {
                "Validate the requested tag before checkout",
                "Validate dispatch identifiers before checkout",
                "Validate publication identifiers before checkout",
            }
        )
        for job in ("source", "release-build", "release")
    ]
    monkeypatch.setenv("REQUESTED_PACK", "example-pack")
    monkeypatch.setenv("CLAUDE_RUN", "1")
    monkeypatch.setenv("CODEX_RUN", "2")
    monkeypatch.setenv("OPENCODE_RUN", "3")
    for version in ("1.0.0", "1.0.0-alpha.1", "1.0.0+build.7"):
        monkeypatch.setenv("REQUESTED_TAG", f"example-pack-v{version}")
        for script in scripts:
            exec(compile(script, "release.yml:strict-semver", "exec"), {})
    for version in ("1.0.0-01", "1.0.0-alpha..1", "1.0.0-.", "1.0.0+build..x"):
        monkeypatch.setenv("REQUESTED_TAG", f"example-pack-v{version}")
        for script in scripts:
            with pytest.raises(SystemExit, match="valid SemVer"):
                exec(compile(script, "release.yml:strict-semver", "exec"), {})


def test_release_and_recovery_verify_downloaded_evidence_artifact_digests() -> None:
    for workflow_name in ("release.yml", "release-recovery.yml"):
        workflow = _workflow(workflow_name)
        assert '[[ ! "$artifact_digest" =~ ^sha256:[0-9a-f]{64}$ ]]' in workflow
        assert "hashlib.file_digest" in workflow
        assert '[[ "$downloaded_digest" != "$artifact_digest" ]]' in workflow
        assert workflow.index("downloaded_digest=$(python") < workflow.index(
            'unzip -q "$reports_dir/$client.zip"'
        )


def test_release_and_recovery_prove_protected_main_ancestry_before_tagged_execution() -> None:
    release = _workflow("release.yml")
    source = release.split("  source:\n", 1)[1].split("\n  rust-assets:\n", 1)[0]
    assert 'cat-file -e "$TESTED_SOURCE_SHA^{commit}"' in source
    ancestry = source.index('merge-base --is-ancestor "$TESTED_SOURCE_SHA" "$GITHUB_SHA"')
    export = source.index("handle.write(f\"source_sha={os.environ['TESTED_SOURCE_SHA']}")
    assert ancestry < export

    recovery = _workflow("release-recovery.yml")
    resume_build = recovery.split("  resume-build:\n", 1)[1].split("\n  resume:\n", 1)[0]
    resume = recovery.split("  resume:\n", 1)[1].split("\n  recovered-publication", 1)[0]
    assert 'os.environ["PROTECTED_MAIN_SHA"]' in resume_build
    assert "signed release source is not an ancestor of protected main" in resume_build
    assert resume_build.index("merge-base") < resume_build.index(
        "Install signed tag tooling only after trust verification"
    )
    assert 'merge-base --is-ancestor "$source_sha" "$PROTECTED_MAIN_SHA"' in resume
    assert resume.index("merge-base --is-ancestor") < resume.index(
        "Upload only missing assets without replacement"
    )


def test_dco_and_dependency_review_are_read_only() -> None:
    dco = _workflow("dco.yml")
    assert "permissions:\n  contents: read\n" in dco
    assert "fetch-depth: 0" in dco
    assert 'if [[ "$PR_AUTHOR" == "dependabot[bot]" ]]' in dco
    assert 'python tools/check-dco "${arguments[@]}" "$BASE_SHA" "$HEAD_SHA"' in dco

    dependency_review = _workflow("dependency-review.yml")
    assert "permissions:\n  contents: read\n" in dependency_review
    assert "pull-requests: write" not in dependency_review
    assert "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294" in (
        dependency_review
    )
    for setting in (
        "fail-on-severity: high",
        "fail-on-scopes: runtime, development, unknown",
        "show-patched-versions: true",
        "retry-on-snapshot-warnings: true",
        "retry-on-snapshot-warnings-timeout: 120",
        "comment-summary-in-pr: never",
    ):
        assert setting in dependency_review


def test_pages_deploys_only_validated_generated_dist() -> None:
    pages = _workflow("pages.yml")
    assert '      - "main"\n' in _event_block(pages, "push")
    assert "          DEFAULT_BRANCH: main\n" in pages
    assert '[[ "$GITHUB_REF" != "refs/heads/$DEFAULT_BRANCH" ]]' in pages
    assert "contents: read" in pages
    assert "pages: write" in pages
    assert "id-token: write" in pages
    assert "cancel-in-progress: false" in pages
    assert "python tools/generate-all --check" in pages
    assert "python tools/validate-repository --check-generated --strict-placeholders" in pages
    assert "actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d" in pages
    assert "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9" in pages
    assert "actions/deploy-pages@cd2ce8fcbc39b97be8ca5fce6e763baed58fa128" in pages
    assert "          path: dist/public\n" in pages
    assert "          path: dist\n" not in pages
    assert "      url: ${{ steps.deployment.outputs.page_url }}\n" in pages
    assert "      removed_paths: ${{ steps.removed-paths.outputs.paths }}\n" in pages
    assert 'pages_absent_paths(packs, legacy["paths"])' in pages
    assert "tests/fixtures/pages-legacy-public-urls-v1.json" in pages
    assert '[[ "$status" = 200 ]]' in pages
    assert 'if [[ "$status" != 404 ]]' in pages
    assert pages.count("if ! status=$(curl") == 2
    assert pages.count('status="000"') == 2

    workflow = yaml.safe_load(pages)
    build = workflow["jobs"]["build"]
    deploy = workflow["jobs"]["deploy"]
    assert build["permissions"] == {"contents": "read"}
    assert deploy["needs"] == "build"
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    upload = next(
        step
        for step in build["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-pages-artifact@")
    )
    assert upload["with"] == {"path": "dist/public"}

    legacy = json.loads(
        (ROOT / "tests/fixtures/pages-legacy-public-urls-v1.json").read_text(encoding="utf-8")
    )
    assert legacy["schemaVersion"] == 1
    assert legacy["paths"] == sorted(set(legacy["paths"]))
    assert "install/repository-development.sh" in legacy["paths"]
    assert "install/repository-development.ps1" in legacy["paths"]
    assert "opencode/shared/repository-development/index.json" in legacy["paths"]
    assert not any(
        str(step.get("uses", "")).startswith("actions/deploy-pages@") for step in build["steps"]
    )
    assert any(
        str(step.get("uses", "")).startswith("actions/deploy-pages@") for step in deploy["steps"]
    )


def test_release_dispatch_permissions_and_environment_are_narrow() -> None:
    release = _workflow("release.yml")
    workflow = yaml.safe_load(release)
    preflight = release.split("  preflight:\n", 1)[1].split("\n  source:\n", 1)[0]
    source_job = release.split("  source:\n", 1)[1].split("\n  rust-assets:\n", 1)[0]
    rust_job = release.split("  rust-assets:\n", 1)[1].split("\n  release-gates:\n", 1)[0]
    gate_job = release.split("  release-gates:\n", 1)[1].split("\n  release-build:\n", 1)[0]
    build_job = workflow["jobs"]["release-build"]
    publication = release.split("\n  release:\n", 1)[1]

    assert "          DEFAULT_BRANCH: main\n" in preflight
    assert '[[ "$GITHUB_REF" != "refs/heads/$DEFAULT_BRANCH" ]]' in preflight
    assert "    needs: preflight\n" in source_job
    assert "    needs: source\n" in rust_job
    assert "      - source\n" in gate_job
    assert "      - rust-assets\n" in gate_job
    assert "    environment: release\n" not in rust_job
    assert "environment" not in build_job
    assert build_job["permissions"] == {
        "actions": "read",
        "attestations": "read",
        "contents": "read",
    }
    assert "    environment: release\n" in publication
    for permission in (
        "      actions: read\n",
        "      attestations: write\n",
        "      contents: write\n",
        "      id-token: write\n",
    ):
        assert permission in publication
    before_publication = release.split("\n  release:\n", 1)[0]
    assert "attestations: write" not in before_publication
    assert "id-token: write" not in before_publication


def test_release_build_is_sealed_before_the_minimal_publisher_mutates() -> None:
    workflow = yaml.safe_load(_workflow("release.yml"))
    build = workflow["jobs"]["release-build"]
    publication = workflow["jobs"]["release"]

    build_names = [step["name"] for step in build["steps"]]
    assert build_names.index("Run immutable-source release gates") < build_names.index(
        "Download and verify the three protected evidence artifacts"
    )
    assert build_names.index("Download and verify the three protected evidence artifacts") < (
        build_names.index("Build the deterministic evidence-gated release")
    )
    assert build_names.index("Build the deterministic evidence-gated release") < build_names.index(
        "Assemble the deterministic release-build bundle"
    )
    assert build_names[-1] == "Upload the authenticated release-build bundle"
    upload = build["steps"][-1]
    assert upload["id"] == "release-bundle"
    assert upload["with"] == {
        "name": "release-build-${{ inputs.pack_id }}-${{ github.run_id }}",
        "path": "${{ runner.temp }}/release-build-bundle",
        "if-no-files-found": "error",
        "compression-level": 0,
        "retention-days": 7,
    }
    assert build["outputs"] == {
        "artifact_digest": "${{ steps.release-bundle.outputs.artifact-digest }}",
        "artifact_id": "${{ steps.release-bundle.outputs.artifact-id }}",
        "artifact_name": "release-build-${{ inputs.pack_id }}-${{ github.run_id }}",
    }
    build_script = "\n".join(str(step.get("run", "")) for step in build["steps"])
    for client in ("claude-code", "codex", "opencode"):
        assert client in build_script
    for suffix in ("json", "envelope.json", "attestation.jsonl"):
        assert suffix in build_script
    assert 'Path(os.environ["NOTES"])' in build_script
    assert 'Path(os.environ["ARCHIVE"])' in build_script
    assert 'Path(os.environ["CHECKSUM"])' in build_script
    assert '"release-build-manifest.json"' in build_script

    publication_names = [step["name"] for step in publication["steps"]]
    download_index = publication_names.index(
        "Download and digest-verify the exact release-build artifact"
    )
    revalidate_index = publication_names.index(
        "Revalidate the tag, source, signer, lifecycle, and sealed bundle"
    )
    refusal_index = publication_names.index(
        "Refuse to overwrite any existing release after bundle verification"
    )
    attest_index = publication_names.index("Generate ZIP provenance")
    assert download_index < revalidate_index < refusal_index < attest_index
    download = publication["steps"][download_index]["run"]
    assert "EXPECTED_ARTIFACT_ID" in download
    assert "EXPECTED_ARTIFACT_NAME" in download
    assert "EXPECTED_ARTIFACT_DIGEST" in download
    assert 'test "$api_digest" = "sha256:$EXPECTED_ARTIFACT_DIGEST"' in download
    assert 'test "$downloaded_digest" = "$EXPECTED_ARTIFACT_DIGEST"' in download
    assert download.index('test "$downloaded_digest"') < download.index("zipfile.ZipFile")

    revalidate = publication["steps"][revalidate_index]
    assert revalidate["env"]["POLICY_ROOT"] == "${{ github.workspace }}"
    assert revalidate["env"]["RELEASE_ROOT"] == "${{ github.workspace }}/release-source"
    assert 'export PYTHONPATH="$POLICY_ROOT/src"' in revalidate["run"]
    assert "get_pack(release_root" in revalidate["run"]
    assert "verify_tag(release_root" in revalidate["run"]
    assert "release-build file failed its sealed digest" in revalidate["run"]

    publisher_script = "\n".join(str(step.get("run", "")) for step in publication["steps"])
    for forbidden in (
        "python tools/check-dependency-lock",
        "python tools/generate-all",
        "python tools/run-evals",
        "python -m pytest",
        "python -m pip install --disable-pip-version-check --no-deps --no-build-isolation -e .",
    ):
        assert forbidden not in publisher_script
    seal_index = publication_names.index("Seal the exact draft state before publication")
    preserve_index = publication_names.index(
        "Preserve the sealed release intent before publication"
    )
    publish_index = publication_names.index("Publish the verified draft")
    exact_index = publication_names.index("Verify the exact immutable release state by numeric ID")
    assert attest_index < seal_index < preserve_index < publish_index < exact_index
    seal = publication["steps"][seal_index]["run"]
    assert "seal-intent" in seal
    assert '--policy-sha "$GITHUB_SHA"' in seal
    assert '--release-id "$RELEASE_ID"' in seal
    assert "releases/$RELEASE_ID/assets?per_page=100" in seal
    publish = publication["steps"][publish_index]["run"]
    assert '--method PATCH "/repos/$GITHUB_REPOSITORY/releases/$RELEASE_ID"' in publish
    assert "gh release edit" not in publish
    verify = publication["steps"][exact_index]["run"]
    assert "verify-published" in verify
    assert "releases/$RELEASE_ID/assets?per_page=100" in verify


def test_recovery_build_is_sealed_before_the_minimal_resume_job_mutates() -> None:
    workflow = yaml.safe_load(_workflow("release-recovery.yml"))
    build = workflow["jobs"]["resume-build"]
    resume = workflow["jobs"]["resume"]

    assert "environment" not in build
    assert build["permissions"] == {
        "actions": "read",
        "attestations": "read",
        "contents": "read",
    }
    build_names = [step["name"] for step in build["steps"]]
    assert build_names.index("Run all immutable-source repository checks") < build_names.index(
        "Download exact protected evidence artifacts"
    )
    assert build_names.index("Download exact protected evidence artifacts") < build_names.index(
        "Rebuild the deterministic release and exact asset set"
    )
    assert build_names.index("Require original release-workflow ZIP attestation") < (
        build_names.index("Compare the draft with locally rebuilt bytes")
    )
    assert build_names.index("Compare the draft with locally rebuilt bytes") < build_names.index(
        "Assemble the deterministic recovery-build bundle"
    )
    assert build_names[-1] == "Upload the authenticated recovery-build bundle"
    upload = build["steps"][-1]
    assert upload["id"] == "recovery-bundle"
    assert upload["with"] == {
        "name": (
            "recovery-build-${{ inputs.pack_id }}-${{ inputs.release_id }}-${{ github.run_id }}"
        ),
        "path": "${{ runner.temp }}/recovery-build-bundle",
        "if-no-files-found": "error",
        "compression-level": 0,
        "retention-days": 7,
    }
    assert build["outputs"] == {
        "artifact_digest": "${{ steps.recovery-bundle.outputs.artifact-digest }}",
        "artifact_id": "${{ steps.recovery-bundle.outputs.artifact-id }}",
        "artifact_name": (
            "recovery-build-${{ inputs.pack_id }}-${{ inputs.release_id }}-${{ github.run_id }}"
        ),
    }
    build_script = "\n".join(str(step.get("run", "")) for step in build["steps"])
    assert 'Path(os.environ["NOTES"])' in build_script
    assert 'Path(os.environ["ARCHIVE"])' in build_script
    assert 'Path(os.environ["CHECKSUM"])' in build_script
    assert 'Path(os.environ["RUNNER_TEMP"], "release-inspection.json")' in build_script
    assert 'Path(os.environ["RUNNER_TEMP"], "recovery-plan.json")' in build_script
    assert '"recovery-build-manifest.json"' in build_script

    assert resume["needs"] == ["inspect", "resume-build"]
    assert resume["environment"] == "release"
    assert resume["permissions"] == {
        "actions": "read",
        "attestations": "read",
        "contents": "write",
    }
    resume_names = [step["name"] for step in resume["steps"]]
    download_index = resume_names.index(
        "Download and digest-verify the exact recovery-build artifact"
    )
    revalidate_index = resume_names.index(
        "Revalidate source, signer, lifecycle, and sealed recovery build"
    )
    replan_index = resume_names.index("Re-read the draft and recompute the exact recovery plan")
    attest_index = resume_names.index("Reverify the original normal-release ZIP attestation")
    upload_index = resume_names.index("Upload only missing assets without replacement")
    assert download_index < revalidate_index < replan_index < attest_index < upload_index

    download = resume["steps"][download_index]["run"]
    assert "EXPECTED_ARTIFACT_ID" in download
    assert "EXPECTED_ARTIFACT_NAME" in download
    assert "EXPECTED_ARTIFACT_DIGEST" in download
    assert 'test "$api_digest" = "sha256:$EXPECTED_ARTIFACT_DIGEST"' in download
    assert 'test "$downloaded_digest" = "$EXPECTED_ARTIFACT_DIGEST"' in download
    assert download.index('test "$downloaded_digest"') < download.index("zipfile.ZipFile")

    revalidate = resume["steps"][revalidate_index]
    assert revalidate["env"]["POLICY_ROOT"] == "${{ github.workspace }}/policy-source"
    assert revalidate["env"]["RELEASE_ROOT"] == "${{ github.workspace }}/release-source"
    assert 'export PYTHONPATH="$POLICY_ROOT/src"' in revalidate["run"]
    assert "verify_tag(release_root" in revalidate["run"]
    assert "get_pack(release_root" in revalidate["run"]
    assert "recovery-build file failed its sealed digest" in revalidate["run"]
    assert "sealed recovery plan does not match the manifest missing assets" in revalidate["run"]

    replan = resume["steps"][replan_index]
    assert replan["env"]["PYTHONPATH"] == "${{ github.workspace }}/policy-source/src"
    assert 'gh api "/repos/$GITHUB_REPOSITORY/releases/$RELEASE_ID"' in replan["run"]
    assert "expected-body" in replan["run"]
    assert "current-release-inspection.json" in replan["run"]
    assert "plan-resume" in replan["run"]
    resume_script = "\n".join(str(step.get("run", "")) for step in resume["steps"])
    for step in resume["steps"]:
        invokes_python = step.get("shell") == "python" or "python" in str(step.get("run", ""))
        if invokes_python:
            assert step.get("working-directory") != "release-source"
    for forbidden in (
        "Install signed tag tooling only after trust verification",
        "python tools/check-dependency-lock",
        "python tools/generate-all",
        "python tools/run-evals",
        "python -m pytest",
        "Download exact protected evidence artifacts",
    ):
        assert forbidden not in resume_script
    assert "--clobber" not in resume_script


def test_release_gate_aggregate_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = yaml.safe_load(_workflow("release.yml"))
    jobs = workflow["jobs"]
    source = jobs["source"]
    rust = jobs["rust-assets"]
    aggregate = jobs["release-gates"]
    build = jobs["release-build"]
    publication = jobs["release"]

    assert source["needs"] == "preflight"
    assert source["outputs"]["source_sha"] == "${{ steps.gate-policy.outputs.source_sha }}"
    assert rust["needs"] == "source"
    assert rust["if"] == "needs.source.outputs.requires_rust == 'true'"
    assert '--pack "$PACK_ID"' in "\n".join(str(step.get("run", "")) for step in rust["steps"])
    assert aggregate["if"] == "${{ always() }}"
    assert aggregate["needs"] == ["source", "rust-assets"]
    assert build["needs"] == ["source", "release-gates"]
    assert build["steps"][1]["with"]["ref"] == "${{ needs.source.outputs.source_sha }}"
    assert publication["needs"] == ["source", "release-gates", "release-build"]
    assert publication["steps"][1]["with"]["ref"] == "${{ github.sha }}"

    script = aggregate["steps"][0]["run"]
    accepted = (("success", "true", "success"), ("success", "false", "skipped"))
    statuses = ("success", "failure", "cancelled", "skipped", "")
    for source_result in statuses:
        for requires_rust in ("true", "false", "", "unknown"):
            for rust_result in statuses:
                monkeypatch.setenv("SOURCE_RESULT", source_result)
                monkeypatch.setenv("REQUIRES_RUST", requires_rust)
                monkeypatch.setenv("RUST_RESULT", rust_result)
                values = (source_result, requires_rust, rust_result)
                if values in accepted:
                    exec(compile(script, "release.yml:release-gates", "exec"), {})
                else:
                    with pytest.raises(SystemExit):
                        exec(compile(script, "release.yml:release-gates", "exec"), {})


def test_rust_jobs_install_hash_locked_python_dependencies_before_checker() -> None:
    for workflow_name in ("validate.yml", "release.yml"):
        workflow = yaml.safe_load(_workflow(workflow_name))
        steps = workflow["jobs"]["rust-assets"]["steps"]
        setup = next(
            step for step in steps if str(step.get("uses", "")).startswith("actions/setup-python@")
        )
        assert setup["with"] == {
            "python-version": "3.11",
            "cache": "pip",
            "cache-dependency-path": "requirements-dev.txt",
        }

        locked_install = (
            "python -m pip install --disable-pip-version-check "
            "--require-hashes -r requirements-dev.txt"
        )
        install_index = next(
            index for index, step in enumerate(steps) if locked_install in str(step.get("run", ""))
        )
        checker_indexes = [
            index
            for index, step in enumerate(steps)
            if "check-rust-assets" in str(step.get("run", ""))
        ]
        assert checker_indexes
        assert install_index < min(checker_indexes)


def test_release_publication_is_fail_closed_and_ordered() -> None:
    release = _workflow("release.yml")
    ordered_steps = (
        "      - name: Refuse to overwrite any existing release after bundle verification",
        "      - name: Create an asset-free draft for the verified tag",
        "      - name: Upload the immutable release asset set without replacement",
        "      - name: Seal the exact draft state before publication",
        "      - name: Preserve the sealed release intent before publication",
        "      - name: Publish the verified draft",
        "      - name: Wait boundedly for the immutable-release attestation",
        "      - name: Verify the immutable release attestation",
        "      - name: Verify the exact immutable release state by numeric ID",
        "      - name: Verify every published asset against the immutable release",
        "      - name: Verify the published ZIP provenance",
    )
    positions = [release.index(step) for step in ordered_steps]
    assert positions == sorted(positions)
    assert "--clobber" not in release
    assert "gh release delete" not in release
    assert "--draft" in release
    assert "--verify-tag" in release
    assert "'{name: $name, body: $body, draft: false, prerelease: false}'" in release
    assert '--method PATCH "/repos/$GITHUB_REPOSITORY/releases/$RELEASE_ID"' in release
    assert 'gh release verify "$RELEASE_TAG"' in release
    assert 'gh release verify-asset "$RELEASE_TAG" "$asset"' in release
    assert release.count("Could not prove that $RELEASE_TAG has no existing release.") == 2


def test_release_attests_and_immediately_verifies_the_zip() -> None:
    release = _workflow("release.yml")
    refusal = "      - name: Refuse to overwrite any existing release after bundle verification"
    action = "actions/attest@f7c74d28b9d84cb8768d0b8ca14a4bac6ef463e6"
    immediate = "      - name: Verify the returned provenance bundle immediately"
    draft = "      - name: Create an asset-free draft for the verified tag"
    assert (
        release.index(refusal)
        < release.index(action)
        < release.index(immediate)
        < release.index(draft)
    )
    assert "          subject-path: ${{ steps.metadata.outputs.archive }}\n" in release
    assert "          ATTESTATION_BUNDLE: ${{ steps.provenance.outputs.bundle-path }}\n" in release
    assert '--bundle "$ATTESTATION_BUNDLE"' in release
    assert '--repo "$GITHUB_REPOSITORY"' in release
    assert '--signer-workflow "$SIGNER_WORKFLOW"' in release
    assert "--deny-self-hosted-runners" in release


def test_release_rechecks_evidence_ancestry_from_the_protected_dispatch_sha() -> None:
    release = _workflow("release.yml")
    assert "          PROTECTED_MAIN_SHA: ${{ github.sha }}\n" in release
    assert 'git cat-file -e "$evidence_sha^{commit}"' in release
    assert 'git merge-base --is-ancestor "$SOURCE_SHA" "$evidence_sha"' in release
    assert 'git merge-base --is-ancestor "$evidence_sha" "$PROTECTED_MAIN_SHA"' in release


def test_publication_handoff_issue_job_is_narrow_and_idempotent(tmp_path: Path) -> None:
    handoff_text = _workflow("publication-handoff.yml")
    workflow = yaml.safe_load(handoff_text)
    verify = workflow["jobs"]["verify-and-plan"]
    follow_up = workflow["jobs"]["notify"]
    assert workflow["permissions"] == {
        "actions": "read",
        "attestations": "read",
        "contents": "read",
    }
    assert "permissions" not in verify
    assert follow_up["needs"] == "verify-and-plan"
    assert follow_up["permissions"] == {"contents": "read", "issues": "write"}
    assert all("uses" not in step for step in follow_up["steps"])
    script = follow_up["steps"][0]["run"]
    assert "<!-- publication-update:$RELEASE_ID:$RELEASE_TAG -->" in script
    assert "gh api --paginate --slurp" in script
    assert 'test "${#matches[@]}" -le 1' in script
    assert 'if [[ "${#matches[@]}" = 1 ]]' in script
    assert 'elif [[ "${#matches[@]}" = 0 ]]' in script
    assert r"Immutable release \140%s\140 for \140%s\140" in script
    assert 'MARKER="$marker" jq -r' in script
    assert "contains(env.MARKER)" in script
    assert "--method POST" in script
    assert "--method PATCH" in script
    assert "-f state=open" in script
    assert "issues: write" not in _workflow("release.yml")
    assert "issues: write" not in _workflow("release-recovery.yml")
    assert "contents: write" not in handoff_text

    body_builder = script.split("gh api", 1)[0]
    environment = {
        **os.environ,
        "ARTIFACT_NAME": "publication-handoff-python-best-practices-42-100",
        "GITHUB_REPOSITORY": "genaptic/skillsets",
        "GITHUB_RUN_ID": "100",
        "PACK_ID": "python-best-practices",
        "RELEASE_ID": "42",
        "RELEASE_TAG": "python-best-practices-v1.0.0",
        "RUNNER_TEMP": str(tmp_path),
        "STATUS": "update-required",
    }
    bash = shutil.which("bash")
    assert bash is not None
    subprocess.run([bash, "-c", body_builder], check=True, env=environment)
    body = (tmp_path / "publication-handoff.md").read_text(encoding="utf-8")
    assert "Immutable release `42`" in body
    assert "`python-best-practices-v1.0.0`" in body
    assert "- Handoff status: `update-required`" in body


def test_publication_handoff_serializes_and_rebinds_the_exact_release() -> None:
    workflow = yaml.safe_load(_workflow("publication-handoff.yml"))
    resolve = workflow["jobs"]["resolve"]
    verify = workflow["jobs"]["verify-and-plan"]
    assert verify["needs"] == "resolve"
    assert verify["concurrency"] == {
        "group": (
            "publication-handoff-${{ github.repository }}-${{ needs.resolve.outputs.release_id }}"
        ),
        "cancel-in-progress": False,
    }
    resolver = resolve["steps"][0]["run"]
    assert 'workflow.get("runAttempt")' in resolver
    assert 'data.get("repository", {}).get("policySha")' in resolver
    scripts = "\n".join(str(step.get("run", "")) for step in verify["steps"])
    assert "| [.id, .digest] | @tsv" in scripts
    assert "read -r artifact_id artifact_digest" in scripts
    assert "read -r artifact_id artifact_name artifact_digest" not in scripts
    assert "validate_release_intent" in scripts
    assert 'merge-base --is-ancestor "$intent_policy_sha" "$GITHUB_SHA"' in scripts
    assert "'.tagObjectSha'" in scripts
    assert "_require_release_readiness" in scripts
    assert 'pack.publication_state == "published"' in scripts
    assert "pack.latest_release == expected_latest" in scripts
    assert '${RELEASE_TAG#"$PACK_ID-v"}' in scripts


def test_release_profiles_exclude_global_rust_contract_modules_exactly() -> None:
    expected = 'python -m pytest --no-cov -m "not rust_repository_contract"'
    for workflow_name, step_name in (
        ("release.yml", "Run immutable-source release gates"),
        ("release-recovery.yml", "Run all immutable-source repository checks"),
    ):
        workflow = yaml.safe_load(_workflow(workflow_name))
        scripts = [
            str(step.get("run", ""))
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
            if step.get("name") == step_name
        ]
        assert len(scripts) == 1
        assert expected in scripts[0]
        assert scripts[0].count("python -m pytest") == 1


def test_publication_reconciliation_rechecks_generated_public_membership() -> None:
    workflow = yaml.safe_load(_workflow("publication-reconcile.yml"))
    job = workflow["jobs"]["reconcile"]
    assert workflow["permissions"] == {"contents": "read"}
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "skillpack_tools.publication reconcile" in commands
    assert "normalized-tags.json" in commands
    assert "python tools/generate-all --check" not in commands
    comparison = next(step for step in job["steps"] if step["name"].startswith("Compare canonical"))
    assert comparison["continue-on-error"] is True
    assert "pages: write" not in _workflow("publication-reconcile.yml")
    assert "contents: write" not in _workflow("publication-reconcile.yml")


def test_native_evidence_dispatch_is_guarded_by_default_branch() -> None:
    native = _workflow("native-compatibility.yml")
    parsed = yaml.safe_load(native)
    guard = native.index("      - name: Validate the workflow dispatch source branch")
    checkout = native.index("      - name: Check out the protected dispatch commit")
    assert guard < checkout
    assert "          DEFAULT_BRANCH: main\n" in native
    assert '[[ "$GITHUB_REF" != "refs/heads/$DEFAULT_BRANCH" ]]' in native
    assert "      evidence_sha:\n" in native
    assert "evidence_ref" not in native
    assert 'git("merge-base", "--is-ancestor", evidence_sha, dispatch_sha)' in native
    assert 'git("merge-base", "--is-ancestor", source_sha, evidence_sha)' in native
    assert "report.write_bytes(blob)" in native
    assert "validated-report/${{ inputs.client }}.envelope.json" in native
    assert "validated-report/${{ inputs.client }}.attestation.jsonl" in native
    assert "actions/attest@f7c74d28b9d84cb8768d0b8ca14a4bac6ef463e6" in native
    assert "  attestations: write\n" in native
    assert "  id-token: write\n" in native
    assert '--source-ref "refs/heads/$DEFAULT_BRANCH"' in native
    python_steps = [
        step
        for step in parsed["jobs"]["validate-evidence"]["steps"]
        if step.get("shell") == "python"
    ]
    assert len(python_steps) == 5
    for step in python_steps:
        compile(step["run"], f"native-compatibility.yml:{step['name']}", "exec")
