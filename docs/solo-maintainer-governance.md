# Solo-maintainer governance

Genaptic Skillsets currently has one maintainer. Protection therefore uses zero required review
approvals while retaining the controls that can be satisfied independently: pull requests,
twelve required checks, an up-to-date branch, resolved conversations, linear history, and no
force pushes or branch deletion.

## Main branch

`main` is the default and deployment branch. Squash merge is the only merge method, and the
pull-request title and description become the commit message. Main has no bypass actor, no
CODEOWNERS or latest-push approval requirement, and no merge queue. CODEOWNERS still assigns all
six independently versioned pack paths so ownership is explicit when more maintainers join.

A documentation-only protection probe must instantiate all twelve required checks. Create or
change the active `protect-main` ruleset only from the exact contexts and GitHub Actions app
identity observed on that run. Zero approvals is not permission to bypass failing, skipped,
pending, or stale checks.

The planned aggregate-check migration is deliberately two-step. First observe the non-required
Python 3.14 probe and `required-validation` aggregate on a real pull request. Only then replace
the five host validation contexts with the aggregate using the observed App ID and read the
complete ruleset back. Python 3.13 remains required until a subsequent pull request promotes
3.14; a local workflow edit alone never authorizes changing the live ruleset.

## Releases and environments

The `compatibility`, `release`, and `github-pages` environments accept deployments only from
`main`, contain no secrets, and disable administrator bypass. `release` has a five-minute wait;
the other environments have no reviewer or wait requirement.

The release-tag ruleset protects `refs/tags/*-v*` from creation, update, deletion, and
non-fast-forward changes. The resolved organization-administrator role is an always-bypass actor
only so the sole maintainer can create an initial signed annotated tag. Immutable releases then
lock published tags and assets further. No tag or release is created during repository
infrastructure setup.

## Contribution and incident boundaries

Every human commit must be SSH-signed and DCO-compliant. Dependabot receives only the narrowly
validated bot-identity DCO exemption. Web signoff helps contributors create the trailer but does
not replace cryptographic signing for maintainer-authored local commits.

Vulnerabilities go exclusively through private vulnerability reporting. Support and design
questions go to Discussions Q&A. Repository automation uses only GitHub-hosted runners and the
short-lived workflow token with job-scoped permissions; it does not receive maintainer PATs,
client credentials, deploy keys, or external publisher accounts.

When additional maintainers join, review approval counts, CODEOWNERS enforcement, environment
reviewers, tag bypass actors, and incident responsibilities before weakening or extending any
existing rule.
