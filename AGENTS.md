# Working agreement for coding agents

This repo is spec-driven. The order of work is always:

1. **Spec**: a human writes or changes `specs/<model>.yml`, often starting from
   `python tools/specgen.py draft <relation> --as <model>`. It is reviewed in a PR first.
2. **Contract**: `python tools/specgen.py generate <model>` writes the dbt contract and tests.
3. **Implementation**: the agent writes the SQL, following `prompts/implement_from_spec.md`.
4. **Verification**: `dbt build --select <model>` runs the contract and every test against real data.
5. **Promotion**: once a draft spec has met real data without surprises, a human runs
   `python tools/specgen.py promote <model>` and every test becomes a hard failure.

Never edit generated `_<model>.yml` files or the specs to make a build pass.
A failing or warning test is either a bug in the SQL or a finding about the spec.
Findings go in `findings/<model>.md` with the evidence; a human decides what changes.
