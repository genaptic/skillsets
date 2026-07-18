# Rust CLI Applications compatibility fixture

`expected-skills.json` is the exact ordered discovery contract for this pack. The root
validator checks it against `skillpack.yaml`. Client smoke tests must compare their discovered
skill names to this file and record client/model versions, exact source SHA, permissions,
network/filesystem effects, and reviewer verdict in a schema-valid report.

`smoke.py` is offline and checks that every declared canonical skill contains `SKILL.md`.
No test here connects externally or installs a plugin. Passing is structural evidence only,
not a native-client or model-backed compatibility claim.
