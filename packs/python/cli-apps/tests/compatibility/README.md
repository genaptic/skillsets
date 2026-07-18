# Python CLI Applications compatibility fixture

`expected-skills.json` is the exact ordered discovery contract for this pack. The root
validator checks it against `skillpack.yaml`. Client smoke tests must compare their discovered
skill names to this file and record the client/model versions, exact pack SHA, permissions,
network/filesystem effects, and reviewer verdict in a schema-valid compatibility report.

No test in this directory connects to an external service or installs a plugin. Passing this
fixture is structural evidence only, not a native-client or model-backed claim.
