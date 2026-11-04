#!/usr/bin/env python3
"""specgen: turn data model specs into enforceable dbt contracts.

The spec (specs/<model>.yml) is the source of truth. This tool:
  validate  check every spec against specs/_conventions.yml
  generate  write models/<layer>/_<model>.yml: contract, constraints, tests, docs
  status    show which specs have a contract and an implementation
  task      print the full task for a coding agent to implement one model

The SQL itself is written by a coding agent from the spec
(see prompts/implement_from_spec.md). The generated contract and tests are
what prove the agent got it right.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs"

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)


class SpecError(Exception):
    pass


# ---------------------------------------------------------------- loading
def load_conventions() -> dict:
    return yaml.safe_load((SPECS / "_conventions.yml").read_text())


def load_specs(only: str | None = None) -> list[tuple[Path, dict]]:
    specs = []
    for path in sorted(SPECS.glob("*.yml")):
        if path.name.startswith("_"):
            continue
        spec = yaml.safe_load(path.read_text())
        if only and spec.get("model") != only:
            continue
        specs.append((path, spec))
    if only and not specs:
        raise SpecError(f"no spec found for model '{only}'")
    return specs


# ------------------------------------------------------------- validation
def validate(spec: dict, conv: dict) -> list[str]:
    """Return a list of violations; empty means the spec is valid."""
    errs: list[str] = []
    name = spec.get("model", "<missing>")
    layer = conv["layers"].get(spec.get("layer"))
    if layer is None:
        errs.append(f"unknown layer '{spec.get('layer')}'")
        return errs

    if not any(name.startswith(p) for p in layer["allowed_prefixes"]):
        errs.append(f"name must start with one of {layer['allowed_prefixes']}")

    docs = conv["documentation"]
    if docs["owner_required"] and not spec.get("owner"):
        errs.append("owner is required")
    if docs["model_description_required"] and not spec.get("description"):
        errs.append("model description is required")

    cols = spec.get("columns") or []
    col_names = [c.get("name") for c in cols]
    if len(set(col_names)) != len(col_names):
        errs.append("duplicate column names")

    grain = spec.get("grain") or []
    if conv["keys"]["primary_key_required"] and not grain:
        errs.append("grain (primary key) is required")
    for g in grain:
        if g not in col_names:
            errs.append(f"grain column '{g}' is not defined in columns")

    allowed_types = conv["types"]["allowed"]
    for c in cols:
        cname = c.get("name")
        if c.get("type") not in allowed_types:
            errs.append(f"{cname}: type '{c.get('type')}' not in {allowed_types}")
        if docs["column_description_required"] and not c.get("description"):
            errs.append(f"{cname}: description is required")
        if "accepted_values" in c and c.get("type") != "varchar":
            errs.append(f"{cname}: accepted_values only allowed on varchar")
        ref = c.get("references")
        if ref and ref.count(".") != 1:
            errs.append(f"{cname}: references must look like model.column")

    if not spec.get("depends_on"):
        errs.append("depends_on is required (lineage must be declared)")
    return errs


# ------------------------------------------------------------- generation
def build_contract(spec: dict, conv: dict) -> dict:
    """Translate one spec into a dbt properties document."""
    layer = conv["layers"][spec["layer"]]
    grain = spec["grain"]
    pk_tests = conv["keys"]["primary_key_tests"]

    columns = []
    for c in spec["columns"]:
        col: dict = {
            "name": c["name"],
            "description": c["description"],
            "data_type": c["type"],
        }
        tests: list = []
        constraints: list = []

        if c["name"] in grain:
            constraints.append({"type": "not_null"})
            if "not_null" in pk_tests:
                tests.append("not_null")
            if len(grain) == 1 and "unique" in pk_tests:
                tests.append("unique")
        if "accepted_values" in c:
            tests.append({"accepted_values": {
                "arguments": {"values": c["accepted_values"]}}})
        if c.get("references"):
            ref_model, ref_col = c["references"].split(".")
            tests.append({"relationships": {"arguments": {
                "to": f"ref('{ref_model}')", "field": ref_col}}})
        for expr in c.get("checks", []):
            tests.append({"spec_check": {"arguments": {"expression": expr}}})

        if constraints:
            col["constraints"] = constraints
        if tests:
            col["data_tests"] = tests
        columns.append(col)

    model_tests: list = []
    if len(grain) > 1:
        model_tests.append({"spec_unique_combination": {
            "arguments": {"columns": grain}}})
    exp = spec.get("expectations") or {}
    if exp.get("row_count_equals"):
        model_tests.append({"spec_rowcount_equals": {"arguments": {
            "compare_model": f"ref('{exp['row_count_equals']}')"}}})

    model: dict = {
        "name": spec["model"],
        "description": " ".join(spec["description"].split()),
        "config": {
            "materialized": layer["materialized"],
            "contract": {"enforced": layer["contract_enforced"]},
            "meta": {
                "owner": spec["owner"],
                "grain": grain,
                "spec": f"specs/{spec['model']}.yml",
                "rules": spec.get("rules", []),
            },
        },
    }
    if model_tests:
        model["data_tests"] = model_tests
    model["columns"] = columns
    return {"version": 2, "models": [model]}


def contract_path(spec: dict, conv: dict) -> Path:
    layer = conv["layers"][spec["layer"]]
    return ROOT / layer["path"] / f"_{spec['model']}.yml"


def sql_path(spec: dict, conv: dict) -> Path:
    layer = conv["layers"][spec["layer"]]
    return ROOT / layer["path"] / f"{spec['model']}.sql"


def write_contract(spec: dict, conv: dict) -> tuple[Path, int]:
    doc = build_contract(spec, conv)
    header = (
        f"# GENERATED by tools/specgen.py from specs/{spec['model']}.yml\n"
        "# Do not edit by hand: change the spec and regenerate.\n"
    )
    body = yaml.safe_dump(doc, sort_keys=False, width=100)
    path = contract_path(spec, conv)
    path.write_text(header + body)
    model = doc["models"][0]
    n_tests = len(model.get("data_tests", [])) + sum(
        len(c.get("data_tests", [])) for c in model["columns"])
    return path, n_tests


# -------------------------------------------------------------------- CLI
def cmd_validate(only: str | None) -> int:
    conv = load_conventions()
    failed = 0
    for path, spec in load_specs(only):
        errs = validate(spec, conv)
        if errs:
            failed += 1
            print(f"{RED}✗{RESET} {spec.get('model')}")
            for e in errs:
                print(f"    {RED}-{RESET} {e}")
        else:
            print(f"{GREEN}✓{RESET} {spec['model']}  "
                  f"{DIM}grain={spec['grain']}  "
                  f"{len(spec['columns'])} columns{RESET}")
    return 1 if failed else 0


def cmd_generate(only: str | None) -> int:
    conv = load_conventions()
    if cmd_validate(only):
        print(f"\n{RED}Refusing to generate: fix the spec first.{RESET}")
        return 1
    print()
    for _, spec in load_specs(only):
        path, n = write_contract(spec, conv)
        rel = path.relative_to(ROOT)
        print(f"{GREEN}→{RESET} {rel}  {DIM}contract enforced, {n} tests{RESET}")
        if not sql_path(spec, conv).exists():
            print(f"  {YELLOW}! implementation missing:{RESET} "
                  f"{sql_path(spec, conv).relative_to(ROOT)}  "
                  f"{DIM}(hand the spec to your coding agent){RESET}")
    return 0


def cmd_status(only: str | None) -> int:
    conv = load_conventions()
    print(f"{BOLD}{'model':34} {'contract':10} {'implementation'}{RESET}")
    for _, spec in load_specs(only):
        has_c = contract_path(spec, conv).exists()
        has_s = sql_path(spec, conv).exists()
        mark = lambda ok: f"{GREEN}yes{RESET}       " if ok else f"{YELLOW}missing{RESET}   "
        print(f"{spec['model']:34} {mark(has_c)}{mark(has_s)}")
    return 0


def cmd_task(only: str | None) -> int:
    """Print a self-contained task for a coding agent: prompt, spec and paths."""
    if not only:
        raise SpecError("usage: specgen.py task <model>")
    conv = load_conventions()
    path, spec = load_specs(only)[0]
    prompt = (ROOT / "prompts" / "implement_from_spec.md").read_text()
    layer = spec["layer"]
    prompt = prompt.replace("<model>", spec["model"]).replace("<layer>", layer)
    print(prompt.rstrip())
    print(f"\n## This task\n- Spec: `{path.relative_to(ROOT)}`")
    print(f"- Contract (read-only): `{contract_path(spec, conv).relative_to(ROOT)}`")
    print(f"- Write: `{sql_path(spec, conv).relative_to(ROOT)}`")
    print(f"- Upstream models: {', '.join(spec['depends_on'])}")
    print(f"\n## The spec\n```yaml\n{path.read_text().rstrip()}\n```")
    return 0


def main(argv: list[str]) -> int:
    commands = {"validate": cmd_validate, "generate": cmd_generate,
                "status": cmd_status, "task": cmd_task}
    if len(argv) < 2 or argv[1] not in commands:
        print(__doc__)
        return 2
    only = argv[2] if len(argv) > 2 else None
    try:
        return commands[argv[1]](only)
    except SpecError as e:
        print(f"{RED}error:{RESET} {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
