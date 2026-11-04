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
every test passes, or the build tells you exactly where SQL and spec disagree
```

## Run it (about a minute)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./demo.sh
```

## Run the agent step yourself

The SQL in `models/marts/` was written by a coding agent. To watch that step happen,
delete it and let your own agent rebuild it from the spec:

```bash
rm models/marts/dim_customer_value.sql
python tools/specgen.py status                         # implementation: missing
python tools/specgen.py task dim_customer_value > task.md
```

Open the repo in Claude Code, GitHub Copilot agent mode or any other coding agent and
give it `task.md`. It contains the prompt, the spec and the paths it may write to.
`AGENTS.md` holds the working agreement most agents read on their own.

Then check its work:

```bash
DBT_PROFILES_DIR=. dbt build --select +dim_customer_value
```

Green means the agent's SQL matches the spec. Red tells you exactly where it doesn't.

## From draft to enforced

Writing a spec blind is finicky: you don't know the data yet, and the data rarely
matches what you expected. So specs have a lifecycle.

```bash
python tools/specgen.py draft stg_orders --as fct_orders   # profile real data into a draft spec
```

The draft proposes columns, types, the grain (a column that is unique and never null),
references, allowed values and ranges, from the data as it is today. A human reviews it,
fills in the TODOs and adds the business rules.

While a spec has `status: draft`, every test is a **warning** and the contract is not
enforced: the model can meet real data without breaking the build. When a warning fires,
the agent writes it up in `findings/<model>.md` with the query and example rows, and a
human decides: fix the data upstream, or change the spec.

That happened here. The reviewer added `amount > 0` to `fct_orders`, assuming every order
costs something. The draft build warned on order 65: completed, paid with a $0 card
payment. The finding is in [`findings/fct_orders.md`](findings/fct_orders.md); the
decision was "free orders are real", so the spec became `amount >= 0` with a rule that
says why.

```bash
python tools/specgen.py promote fct_orders   # refuses while docs have TODOs or any test still warns
```

`promote` reads dbt's own run results, so a spec only becomes `enforced` after it has met
the data cleanly. From then on, every test fails the build.

## What's in here

| Path | What it is |
|---|---|
| `specs/_conventions.yml` | Platform rules every spec inherits: naming, allowed types, key and documentation rules |
| `specs/*.yml` | One spec per model: grain, columns, types, rules, expectations |
| `tools/specgen.py` | Validates specs, generates the dbt contracts, drafts and promotes specs |
| `tools/profiler.py` | Profiles a table in the warehouse to propose a draft spec |
| `findings/` | What the agent found when the data disagreed with a spec, and what was decided |
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
- **Strictness is earned.** New specs start as drafts that warn, built from profiled data.
  They become enforced only after a clean run on real data.

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
