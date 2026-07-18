# Document roles and ownership

Use one canonical owner for each durable fact, then summarize or link from other documents.

| Role | Primary audience | Owns | Avoid |
|---|---|---|---|
| Product overview | users | purpose, supported outcomes, quick start | internal module maps |
| Architecture | maintainers | crates, modules, dependency direction, invariants | step-by-step setup |
| Contributor guide | contributors | development workflow, checks, review expectations | product marketing |
| Command reference | users and operators | grammar, options, exit/output behavior | internal implementation detail |
| Operations/runbook | operators | configuration, deployment, recovery, side effects | generic contributor setup |
| Testing guide | contributors | test layers, fixtures, required commands | duplicate architecture narrative |
| Security/threat model | reviewers | trust boundaries, abuse cases, reporting | secrets or operational credentials |
| Agent instructions | coding agents | scoped imperatives, source-of-truth rules, safety | general onboarding prose |
| Historical record | maintainers | past releases and decisions | current normative behavior |

## Reconciliation rules

- Put a fact where its owning audience will maintain it when behavior changes.
- Link to an owner rather than copy long command sequences or module inventories.
- Keep root documents broad; place subsystem detail near the subsystem when local conventions permit.
- Treat generated documents as consumers of canonical metadata, not manual owners.
- Mark historical records clearly and do not rewrite them to look current.
- Keep agent instructions direct, scoped, and testable. They should not silently redefine product or
  architecture behavior.
- When a document legitimately repeats a critical safety rule, ensure its wording and owner remain
  traceable instead of allowing independent variants to drift.

## Conflict resolution

When documents disagree:

1. Identify the executable/configuration evidence.
2. Determine whether the implementation or documentation is wrong.
3. Change implementation only when the user's request authorizes it.
4. Otherwise align documentation to current behavior and report any likely implementation defect.
5. If intent cannot be recovered, label the ambiguity and request a product decision rather than
   inventing one.
