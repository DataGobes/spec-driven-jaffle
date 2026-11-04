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
   If the spec looks wrong, say so and propose a spec change instead.
5. Use CTEs with clear names; one CTE per step of the logic.

## Done means
`python tools/specgen.py validate <model>` and `dbt build --select <model>` both pass.
