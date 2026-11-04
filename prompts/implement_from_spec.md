# Implement a dbt model from its spec

You are implementing **one** dbt model. The spec is the source of truth.

## Inputs
- The spec: `specs/<model>.yml`
- The platform conventions: `specs/_conventions.yml`
- The generated contract: `models/<layer>/_<model>.yml` (read-only)
- The upstream models named in the spec's `depends_on`

## Your task
Write `models/<layer>/<model>.sql` so that `dbt build --select <model>` passes.

## Rules
1. Select only from models listed in `depends_on`, always via `ref()`.
2. Output exactly the spec's columns, in the spec's order, cast to the spec's types.
3. Implement every line under `rules:` literally. If a rule is ambiguous, stop and
   ask; do not guess.
4. Never edit the spec, the conventions or the generated contract to make a test pass.
5. Use CTEs with clear names; one CTE per step of the logic.

## When the data contradicts the spec
A test can fail (or warn, on a `draft` spec) even though your SQL follows the spec
exactly: the data is not what the spec author expected. That is a finding, not a bug
to hide.

1. First rule out your own SQL: re-read the rule the test checks and your implementation.
2. Do not bend the SQL to make the test pass: no filtering out, capping or defaulting
   rows the spec does not tell you to. Do not touch the spec or the tests.
3. Write `findings/<model>.md` with, for each finding:
   - which spec line or test disagrees with the data;
   - the query that shows it, and how many rows it affects;
   - two or three example rows;
   - the options you see (fix the data upstream, change the spec), without choosing.
4. Stop and hand it to a human. They decide, and change the spec if needed.

## Done means
`python tools/specgen.py validate <model>` passes and `dbt build --select <model>`
passes, or it fails or warns only on findings you documented in `findings/<model>.md`.
