# Language Subject compatibility fixture

`expected-skills.json` is the exact ordered discovery contract for this pack. The root
validator checks it against `skillpack.yaml`. Native client runs must record client/model
versions, exact source SHA, permissions, network/filesystem effects, and reviewer verdict in
a schema-valid compatibility report.

`smoke.py` performs an offline structural check only. It does not connect to an external
service or install a plugin, and a pass is not native-client or model-backed evidence.
