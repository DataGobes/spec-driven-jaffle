# Spec-driven Jaffle Shop

Spec-driven development for data engineering, on dbt + DuckDB.

You write a **spec** for a new table. A small generator turns it into an enforced
dbt **contract with tests**. A coding agent writes the **SQL**. `dbt build` proves
the SQL matches the spec, against real data.

```
specs/dim_customer_value.yml        ← you write and review this
        │  python tools/specgen.py generate
        ▼
models/marts/_dim_customer_value.yml  ← generated: contract, constraints, tests, docs
        │  coding agent + prompts/implement_from_spec.md
        ▼
models/marts/dim_customer_value.sql   ← generated: the implementation
        │  dbt build
        ▼
all 20 tests pass, or the build tells you exactly where SQL and spec disagree
```

## Run it (about a minute)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./demo.sh
```

## What's in here

| Path | What it is |
|---|---|
| `specs/_conventions.yml` | Platform rules every spec inherits: naming, allowed types, key and documentation rules |
| `specs/*.yml` | One spec per model: grain, columns, types, rules, expectations |
| `tools/specgen.py` | Validates specs against the conventions and generates the dbt contracts |
| `macros/spec_tests/` | The generic tests the generated contracts use |
| `prompts/implement_from_spec.md` | The prompt a coding agent gets to write the SQL |
| `AGENTS.md` | The working agreement: spec → contract → implementation → verification |

## Design choices

- **The spec generates the metadata, never the other way around.** The contract YAML is
  generated and marked "do not edit". Docs and catalog metadata can't drift from the spec.
- **Conventions are written once.** Naming, types and key rules live in one file, so a new
  spec only describes what's specific to that table. This is what makes it scale to many teams.
- **Verification runs against data, not just code.** The contract checks names and types;
  the tests check grain, references, ranges and row counts on the actual rows.
- **The agent may not edit the spec to pass a test.** A failing test is either a bug in the
  SQL or a finding about the spec, and a human decides which.

## Why not just write schema.yml?

For a single model, you could. The spec and the generated YAML are close. The spec layer
pays off when many models, many teams and coding agents are involved:

- **The agent doesn't grade its own homework.** If an agent writes both the SQL and the
  schema.yml, it can loosen a test to get a green build. Here a human owns the spec, the
  tests are generated from it, and the agent only writes SQL.
- **Conventions live in one place.** schema.yml accepts anything; `specgen` refuses a spec
  that breaks the naming, type, key or documentation rules. Change a rule once (say, every
  grain becomes a primary key constraint) and regenerate every model, instead of editing
  each YAML file.
- **Intent, not syntax.** `grain: [customer_id, order_month]` becomes not_null checks, a
  combined-uniqueness test and constraints. Business rules ("returned orders don't count")
  have no real home in schema.yml; in the spec they are what the agent implements and what
  the reviewer checks.
- **One source, many outputs.** The same spec can also feed catalog keys, docs or a data
  contract.

**The lighter alternative:** make "humans own schema.yml, agents only write SQL" a rule,
enforce it with `CODEOWNERS` and a linter such as dbt-project-evaluator, and skip the
separate spec format. For a small team that is often enough.

## Try breaking it

Rename `value_tier` to `tier` in `models/marts/dim_customer_value.sql` and run
`dbt build`. The enforced contract stops the build and shows the mismatch.

## Credits

Seed data and staging models from dbt Labs'
[jaffle_shop](https://github.com/dbt-labs/jaffle-shop-classic) (Apache 2.0, see
`LICENSE-jaffle-shop`).

## Video

`video/hyperframes/` contains the 60-second explainer for this repo as a HyperFrames
project. See `video/README.md`.
