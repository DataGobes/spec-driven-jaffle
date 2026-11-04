# Working agreement for coding agents

This repo is spec-driven. The order of work is always:

1. **Spec**: a human writes or changes `specs/<model>.yml`. It is reviewed in a PR first.
2. **Contract**: `python tools/specgen.py generate <model>` writes the dbt contract and tests.
3. **Implementation**: the agent writes the SQL, following `prompts/implement_from_spec.md`.
4. **Verification**: `dbt build --select <model>` runs the contract and every test against real data.

Never edit generated `_<model>.yml` files or the specs to make a build pass.
A failing test is either a bug in the SQL or a finding about the spec: report which.
