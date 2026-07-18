# Security policy

Agent skills can influence tool use, filesystem access, command execution, network requests,
and database changes. Treat skill content, helper scripts, installation code, workflow files,
and generated manifests as supply-chain-sensitive code.

## Supported versions

Security fixes are provided for the latest major version of each pack and, when practical,
the immediately preceding major version. Packs are versioned independently; the repository
does not publish a repository-wide software version.

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/genaptic/skillsets/security/advisories/new).
Enabling that feature is a prerequisite for public repository publication. Until the remote
setting is enabled, do not put vulnerability details in an issue, discussion, pull request,
or other public channel; retain the report and coordinate a private submission with the
maintainer. The project does not publish a fallback security email address.

Include:

- The affected pack, skill, path, version, and release tag or commit SHA.
- The client and version where the behavior was observed.
- A minimal reproduction.
- Expected and actual behavior.
- The practical impact, required permissions, and whether secrets or external systems were
  involved.
- Any proposed mitigation.

Do not include live secrets, production data, exploit payloads that are unnecessary to
demonstrate the issue, or public links that expose affected systems.

## What counts as a security issue

Examples include:

- Prompt or instruction content that causes concealed or unjustified command execution.
- Installers or scripts that download, execute, or modify more than documented.
- Credential collection, logging, disclosure, or unsafe command-line handling.
- Path traversal, unsafe archive extraction, or writes outside an explicit destination.
- A destructive database workflow that lacks a clear confirmation boundary.
- Marketplace or release metadata that resolves to unintended mutable content.
- Workflow permissions or event choices that expose secrets to untrusted pull requests.
- Generated content that diverges from reviewed canonical content.

Incorrect advice without a meaningful security consequence is usually a normal issue.

## Response process

Maintainers will acknowledge a complete report, assess severity and affected versions,
coordinate a fix, add regression coverage, and publish an advisory when appropriate.
Timelines depend on impact and maintainer availability; no disclosure date is implied until
both parties agree.

## Research expectations

Use disposable repositories, accounts, databases, and credentials. Do not access data that
is not yours, degrade shared services, or test against production installations without
written authorization.

## Disclosure and credit

Coordinated public credit is offered unless the reporter requests anonymity. Reports made in
good faith under this policy will not be pursued merely for bypassing a control in a
maintainer-owned test environment.
