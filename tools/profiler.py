"""Profile a relation in the DuckDB warehouse to draft a spec from real data.

Everything here is a proposal for a human to review: candidate keys, references,
allowed values and ranges are what the data shows today, not what it must be.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

# DuckDB type -> the spec types allowed by specs/_conventions.yml
TYPE_MAP = {
    "INTEGER": "integer", "SMALLINT": "integer", "TINYINT": "integer",
    "BIGINT": "bigint", "HUGEINT": "bigint", "UBIGINT": "bigint",
    "VARCHAR": "varchar", "DATE": "date", "BOOLEAN": "boolean",
    "TIMESTAMP": "timestamp", "TIMESTAMP WITH TIME ZONE": "timestamp",
    "DOUBLE": "decimal(18,2)", "FLOAT": "decimal(18,2)",
}
MAX_ENUM = 10          # a varchar with at most this many values becomes accepted_values
SCHEMA = "main"


def spec_type(duck_type: str) -> str:
    if duck_type.startswith("DECIMAL"):
        return "decimal(18,2)"
    return TYPE_MAP.get(duck_type, "varchar")


def connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path.name} not found: run `dbt build` first")
    return duckdb.connect(str(db_path), read_only=True)


def relations(con) -> list[str]:
    rows = con.execute(
        "select table_name from information_schema.tables where table_schema = ?",
        [SCHEMA]).fetchall()
    return [r[0] for r in rows]


def unique_keys(con, rel: str) -> list[str]:
    """Columns that are unique and never null in the current data."""
    cols = con.execute(
        "select column_name from information_schema.columns "
        "where table_schema = ? and table_name = ? order by ordinal_position",
        [SCHEMA, rel]).fetchall()
    keys = []
    for (c,) in cols:
        n, d, nulls = con.execute(
            f'select count(*), count(distinct "{c}"), count(*) - count("{c}") '
            f'from {SCHEMA}."{rel}"').fetchone()
        if n and d == n and nulls == 0:
            keys.append(c)
    return keys


def profile(con, rel: str) -> dict:
    if rel not in relations(con):
        raise ValueError(f"relation '{rel}' not found in the warehouse")
    rows = con.execute(f'select count(*) from {SCHEMA}."{rel}"').fetchone()[0]
    cols = con.execute(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = ? and table_name = ? order by ordinal_position",
        [SCHEMA, rel]).fetchall()
    keys = unique_keys(con, rel)
    # unique keys of every other model, to propose references
    others = {o: unique_keys(con, o) for o in relations(con)
              if o != rel and not o.startswith("raw_")}

    out = []
    for name, dtype in cols:
        q = f'"{name}"'
        distinct, nulls, lo, hi = con.execute(
            f"select count(distinct {q}), count(*) - count({q}), min({q}), max({q}) "
            f'from {SCHEMA}."{rel}"').fetchone()
        col = {"name": name, "type": spec_type(dtype), "distinct": distinct,
               "nulls": nulls, "min": lo, "max": hi, "key": name in keys}
        if col["type"] == "varchar" and 0 < distinct <= MAX_ENUM and rows >= 2 * distinct:
            vals = con.execute(
                f'select distinct {q} from {SCHEMA}."{rel}" where {q} is not null order by 1'
            ).fetchall()
            col["accepted_values"] = [v[0] for v in vals]
        if col["type"] in ("integer", "bigint", "decimal(18,2)") and lo is not None and lo >= 0 \
                and not col["key"] and not name.endswith("_id"):
            col["checks"] = [f"{name} >= 0"]
        # prefer the model named after the entity (customer_id -> *customer*), staging first
        entity = name[:-3] if name.endswith("_id") else name
        ranked = sorted(others, key=lambda o: (entity not in o, not o.startswith("stg_"), o))
        for other in ranked:
            okeys = others[other]
            if name in okeys and not col["key"]:
                missing = con.execute(
                    f'select count(*) from {SCHEMA}."{rel}" r where {q} is not null and not exists '
                    f'(select 1 from {SCHEMA}."{other}" o where o."{name}" = r.{q})').fetchone()[0]
                if missing == 0:
                    col["references"] = f"{other}.{name}"
                    break
        out.append(col)
    return {"relation": rel, "rows": rows, "keys": keys, "columns": out}


def draft_yaml(p: dict, model: str, layer: str) -> str:
    """Render a draft spec as commented YAML, ready for human review."""
    keys = p["keys"]
    grain = [k for k in keys if k.endswith("_id")][:1] or keys[:1]
    lines = [
        f"# DRAFT written by `specgen draft {p['relation']} --as {model}`,",
        f"# profiled on {p['rows']} rows. Everything below is what the data shows today:",
        "# review every line, replace the TODOs, then run `specgen promote " + model + "`.",
        f"model: {model}",
        f"layer: {layer}",
        "status: draft",
        "owner: TODO",
        "description: TODO what does one row mean?",
        "",
        f"grain: [{', '.join(grain)}]" + ("" if grain else "  # TODO no unique column found"),
        "",
        f"depends_on: [{p['relation']}]",
        "",
        "columns:",
    ]
    for c in p["columns"]:
        stats = f"{c['distinct']} distinct, {c['nulls']} nulls"
        if c["min"] is not None and "accepted_values" not in c:
            stats += f", {c['min']} .. {c['max']}"
        lines += [f"  - name: {c['name']}",
                  f"    type: {c['type']}",
                  "    description: TODO",
                  f"    # profiled: {stats}"]
        if c.get("references"):
            lines.append(f"    references: {c['references']}  # every value exists there today")
        if c.get("accepted_values"):
            lines.append(f"    accepted_values: [{', '.join(c['accepted_values'])}]")
        if c.get("checks"):
            lines.append(f"    checks: [\"{c['checks'][0]}\"]")
        lines.append("")
    lines += ["rules:", "  - TODO the business logic, one line per rule", "",
              "expectations:", f"  row_count_equals: {p['relation']}  # TODO keep only if the grain matches", ""]
    return "\n".join(lines)
