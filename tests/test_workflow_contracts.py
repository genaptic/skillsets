from __future__ import annotations

import re
from pathlib import Path

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
            "Rust 1.85+ asset contracts",
            "ShellCheck 0.9.0 and Actionlint 1.7.12",
            "PSScriptAnalyzer 1.25.0",
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


def test_all_external_actions_are_pinned_and_pull_request_target_is_absent() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        assert "pull_request_target" not in text
        uses_lines = re.findall(r"(?m)^\s*uses:\s*[^\n]+$", text)
        assert len(FULL_SHA.findall(text)) == len(uses_lines), path


def test_embedded_python_steps_compile() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in workflow["jobs"].items():
            for index, step in enumerate(job.get("steps", [])):
                if step.get("shell") == "python":
                    compile(step["run"], f"{path.name}:{job_name}:step-{index}", "exec")


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
    assert "          path: dist\n" in pages
    assert "      url: ${{ steps.deployment.outputs.page_url }}\n" in pages


def test_release_dispatch_permissions_and_environment_are_narrow() -> None:
    release = _workflow("release.yml")
    preflight = release.split("  preflight:\n", 1)[1].split("\n  rust-assets:\n", 1)[0]
    rust_job = release.split("  rust-assets:\n", 1)[1].split("\n  release:\n", 1)[0]
    publication = release.split("\n  release:\n", 1)[1]

    assert "          DEFAULT_BRANCH: main\n" in preflight
    assert '[[ "$GITHUB_REF" != "refs/heads/$DEFAULT_BRANCH" ]]' in preflight
    assert "    needs: preflight\n" in rust_job
    assert "    environment: release\n" not in rust_job
    assert "    environment: release\n" in publication
    for permission in (
        "      actions: read\n",
        "      attestations: write\n",
        "      contents: write\n",
        "      id-token: write\n",
    ):
        assert permission in publication
    assert "attestations: write" not in release.split("\n  release:\n", 1)[0]
    assert "id-token: write" not in release.split("\n  release:\n", 1)[0]


def test_release_publication_is_fail_closed_and_ordered() -> None:
    release = _workflow("release.yml")
    ordered_steps = (
        "      - name: Refuse to overwrite any existing release",
        "      - name: Create an asset-free draft for the verified tag",
        "      - name: Upload the immutable release asset set without replacement",
        "      - name: Verify the exact draft asset inventory",
        "      - name: Publish the verified draft",
        "      - name: Wait boundedly for the immutable-release attestation",
        "      - name: Verify the immutable release attestation",
        "      - name: Verify every published asset against the immutable release",
        "      - name: Verify the published ZIP provenance",
    )
    positions = [release.index(step) for step in ordered_steps]
    assert positions == sorted(positions)
    assert "--clobber" not in release
    assert "gh release delete" not in release
    assert "--draft" in release
    assert "--verify-tag" in release
    assert "--draft=false" in release
    assert 'gh release verify "$RELEASE_TAG"' in release
    assert 'gh release verify-asset "$RELEASE_TAG" "$asset"' in release


def test_release_attests_and_immediately_verifies_the_zip() -> None:
    release = _workflow("release.yml")
    refusal = "      - name: Refuse to overwrite any existing release"
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


def test_native_evidence_dispatch_is_guarded_by_default_branch() -> None:
    native = _workflow("native-compatibility.yml")
    guard = native.index("      - name: Validate the workflow dispatch source branch")
    checkout = native.index("      - name: Check out the exact evaluated source")
    assert guard < checkout
    assert "          DEFAULT_BRANCH: main\n" in native
    assert '[[ "$GITHUB_REF" != "refs/heads/$DEFAULT_BRANCH" ]]' in native
