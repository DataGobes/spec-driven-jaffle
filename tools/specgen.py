#!/usr/bin/env python3
"""specgen: turn data model specs into enforceable dbt contracts.

The spec (specs/<model>.yml) is the source of truth. This tool:
  validate  check every spec against specs/_conventions.yml
  generate  write models/<layer>/_<model>.yml: contract, constraints, tests, docs
  status    show each spec's lifecycle, contract and implementation
  task      print the full task for a coding agent to implement one model
  draft     profile a relation and write a draft spec:  draft <relation> --as <model>
  promote   move a draft spec to enforced once it is complete

Lifecycle: a `draft` spec generates every test as a warning and does not
enforce the contract, so a new model can meet real data before it is strict.
An `enforced` spec turns everything into hard failures.

The SQL itself is written by a coding agent from the spec
(see prompts/implement_from_spec.md). The generated contract and tests are
what prove the agent got it right.
"""
from __future__ import annotations

import argparse
import re
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
def status_of(spec: dict) -> str:
    return spec.get("status", "enforced")


def missing(text) -> bool:
    """Empty, or still a TODO left by `specgen draft`."""
    return not text or str(text).strip().upper().startswith("TODO")


def validate(spec: dict, conv: dict, as_status: str | None = None) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Documentation gaps are warnings for a draft."""
    errs: list[str] = []
    docs_gaps: list[str] = []
    name = spec.get("model", "<missing>")
    status = as_status or status_of(spec)
    if status not in conv["lifecycle"]["statuses"]:
        errs.append(f"unknown status '{status}', use one of {conv['lifecycle']['statuses']}")
    layer = conv["layers"].get(spec.get("layer"))
    if layer is None:
        errs.append(f"unknown layer '{spec.get('layer')}'")
        return errs, []

    if not any(name.startswith(p) for p in layer["allowed_prefixes"]):
        errs.append(f"name must start with one of {layer['allowed_prefixes']}")

    docs = conv["documentation"]
    if docs["owner_required"] and missing(spec.get("owner")):
        docs_gaps.append("owner is required")
    if docs["model_description_required"] and missing(spec.get("description")):
        docs_gaps.append("model description is required")
    if any(missing(r) for r in spec.get("rules") or []):
        docs_gaps.append("rules still contain a TODO")

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
        if docs["column_description_required"] and missing(c.get("description")):
            docs_gaps.append(f"{cname}: description is required")
        if "accepted_values" in c and c.get("type") != "varchar":
            errs.append(f"{cname}: accepted_values only allowed on varchar")
        ref = c.get("references")
        if ref and ref.count(".") != 1:
            errs.append(f"{cname}: references must look like model.column")

    if not spec.get("depends_on"):
        errs.append("depends_on is required (lineage must be declared)")

    # examples: the only thing that verifies a business rule
    rules = spec.get("rules") or []
    deps = set(spec.get("depends_on") or [])
    covered: set[int] = set()
    for i, ex in enumerate(spec.get("examples") or [], 1):
        label = ex.get("name") or f"example {i}"
        r = ex.get("rule")
        if not isinstance(r, int) or not 1 <= r <= len(rules):
            errs.append(f"example '{label}': rule must be a rule number 1..{len(rules)}")
        else:
            covered.add(r)
        unknown = set(ex.get("given") or {}) - deps
        if unknown:
            errs.append(f"example '{label}': given {sorted(unknown)} is not in depends_on")
        expect = ex.get("expect")
        if not expect:
            errs.append(f"example '{label}': expect needs at least one row")
        else:
            bad = {k for row in expect for k in row} - set(col_names)
            if bad:
                errs.append(f"example '{label}': expect uses unknown columns {sorted(bad)}")
    if conv["business_rules"]["every_rule_needs_an_example"]:
        for i, r in enumerate(rules, 1):
            if i not in covered and not missing(r):
                docs_gaps.append(f"rule {i} has no example, so nothing verifies it")

    if status == "draft":
        return errs, docs_gaps
    return errs + docs_gaps, []


# ------------------------------------------------------------- generation
def build_contract(spec: dict, conv: dict) -> dict:
    """Translate one spec into a dbt properties document."""
    layer = conv["layers"][spec["layer"]]
    grain = spec["grain"]
    pk_tests = conv["keys"]["primary_key_tests"]
    draft = status_of(spec) == "draft"

    def t(test):
        """A draft reports a failing test as a warning instead of failing the build."""
        if not draft:
            return test
        if isinstance(test, str):
            return {test: {"config": {"severity": "warn"}}}
        (name, body), = test.items()
        return {name: {**body, "config": {"severity": "warn"}}}

    columns = []
    for c in spec["columns"]:
        col: dict = {
            "name": c["name"],
            "description": str(c["description"]),
            "data_type": c["type"],
        }
        tests: list = []
        constraints: list = []

        if c["name"] in grain:
            if not draft:
                constraints.append({"type": "not_null"})
            if "not_null" in pk_tests:
                tests.append(t("not_null"))
            if len(grain) == 1 and "unique" in pk_tests:
                tests.append(t("unique"))
        if "accepted_values" in c:
            tests.append(t({"accepted_values": {
                "arguments": {"values": c["accepted_values"]}}}))
        if c.get("references"):
            ref_model, ref_col = c["references"].split(".")
            tests.append(t({"relationships": {"arguments": {
                "to": f"ref('{ref_model}')", "field": ref_col}}}))
        for expr in c.get("checks", []):
            tests.append(t({"spec_check": {"arguments": {"expression": expr}}}))

        if constraints:
            col["constraints"] = constraints
        if tests:
            col["data_tests"] = tests
        columns.append(col)

    model_tests: list = []
    if len(grain) > 1:
        model_tests.append(t({"spec_unique_combination": {
            "arguments": {"columns": grain}}}))
    exp = spec.get("expectations") or {}
    if exp.get("row_count_equals"):
        model_tests.append(t({"spec_rowcount_equals": {"arguments": {
            "compare_model": f"ref('{exp['row_count_equals']}')"}}}))

    model: dict = {
        "name": spec["model"],
        "description": " ".join(str(spec["description"]).split()),
        "config": {
            "materialized": layer["materialized"],
            "contract": {"enforced": layer["contract_enforced"] and not draft},
            "meta": {
                "status": status_of(spec),
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
    doc: dict = {"version": 2, "models": [model]}

    # every example becomes a dbt unit test: fixed input rows in, expected rows out
    rules = spec.get("rules") or []
    unit_tests = []
    for ex in spec.get("examples") or []:
        given = ex.get("given") or {}
        unit_tests.append({
            "name": f"{spec['model']}__{slug(ex['name'])}",
            "description": f"Rule {ex['rule']}: {rules[ex['rule'] - 1]}",
            "model": spec["model"],
            "given": [{"input": f"ref('{d}')", "rows": given.get(d, [])}
                      for d in spec["depends_on"]],
            "expect": {"rows": ex["expect"]},
        })
    if unit_tests:
        doc["unit_tests"] = unit_tests
    return doc


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60]


def contract_path(spec: dict, conv: dict) -> Path:
    layer = conv["layers"][spec["layer"]]
    return ROOT / layer["path"] / f"_{spec['model']}.yml"


def sql_path(spec: dict, conv: dict) -> Path:
    layer = conv["layers"][spec["layer"]]
    return ROOT / layer["path"] / f"{spec['model']}.sql"


def write_contract(spec: dict, conv: dict) -> tuple[Path, int, int]:
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
    return path, n_tests, len(doc.get("unit_tests", []))


# -------------------------------------------------------------------- CLI
def cmd_validate(only: str | None) -> int:
    conv = load_conventions()
    failed = 0
    for path, spec in load_specs(only):
        errs, warns = validate(spec, conv)
        if errs:
            failed += 1
            print(f"{RED}✗{RESET} {spec.get('model')}")
            for e in errs:
                print(f"    {RED}-{RESET} {e}")
        else:
            tag = f"  {YELLOW}draft{RESET}" if status_of(spec) == "draft" else ""
            print(f"{GREEN}✓{RESET} {spec['model']}{tag}  "
                  f"{DIM}grain={spec['grain']}  "
                  f"{len(spec['columns'])} columns{RESET}")
            for w in warns:
                print(f"    {YELLOW}~{RESET} {w}")
    return 1 if failed else 0


def cmd_generate(only: str | None) -> int:
    conv = load_conventions()
    if cmd_validate(only):
        print(f"\n{RED}Refusing to generate: fix the spec first.{RESET}")
        return 1
    print()
    for _, spec in load_specs(only):
        path, n, n_ex = write_contract(spec, conv)
        rel = path.relative_to(ROOT)
        ex_txt = f", {n_ex} rule examples" if n_ex else ""
        if status_of(spec) == "draft":
            print(f"{GREEN}→{RESET} {rel}  {YELLOW}draft:{RESET} "
                  f"{DIM}contract not enforced, {n} tests as warnings{ex_txt}{RESET}")
        else:
            print(f"{GREEN}→{RESET} {rel}  {DIM}contract enforced, {n} tests{ex_txt}{RESET}")
        if not sql_path(spec, conv).exists():
            print(f"  {YELLOW}! implementation missing:{RESET} "
                  f"{sql_path(spec, conv).relative_to(ROOT)}  "
                  f"{DIM}(hand the spec to your coding agent){RESET}")
    return 0


def cmd_status(only: str | None) -> int:
    conv = load_conventions()
    print(f"{BOLD}{'model':32} {'status':10} {'contract':10} {'implementation'}{RESET}")
    for _, spec in load_specs(only):
        has_c = contract_path(spec, conv).exists()
        has_s = sql_path(spec, conv).exists()
        mark = lambda ok: f"{GREEN}yes{RESET}       " if ok else f"{YELLOW}missing{RESET}   "
        st = status_of(spec)
        st_txt = f"{YELLOW}{st:10}{RESET}" if st == "draft" else f"{st:10}"
        print(f"{spec['model']:32} {st_txt} {mark(has_c)}{mark(has_s)}")
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


def cmd_draft(relation: str, model: str) -> int:
    """Profile a relation and write specs/<model>.yml as a draft for review."""
    import profiler
    conv = load_conventions()
    target = SPECS / f"{model}.yml"
    if target.exists():
        raise SpecError(f"{target.relative_to(ROOT)} already exists; drafts never overwrite a spec")
    layer = next((name for name, l in conv["layers"].items()
                  if any(model.startswith(p) for p in l["allowed_prefixes"])), None)
    if layer is None:
        raise SpecError(f"'{model}' matches no layer prefix in _conventions.yml")
    try:
        con = profiler.connect(ROOT / "jaffle.duckdb")
        prof = profiler.profile(con, relation)
    except (FileNotFoundError, ValueError) as e:
        raise SpecError(str(e))
    target.write_text(profiler.draft_yaml(prof, model, layer))
    print(f"{GREEN}→{RESET} {target.relative_to(ROOT)}  {YELLOW}draft{RESET}  "
          f"{DIM}{len(prof['columns'])} columns profiled on {prof['rows']} rows{RESET}")
    print(f"  {DIM}review it, replace the TODOs, then: specgen.py promote {model}{RESET}")
    return 0


def open_test_results(model: str) -> list[str]:
    """Tests on this model that did not pass in the last dbt run.

    A draft is only promoted once it has met real data without surprises, so promote
    reads dbt's own run artifacts instead of trusting anyone's word for it.
    """
    import json
    target = ROOT / "target"
    try:
        results = json.loads((target / "run_results.json").read_text())["results"]
        nodes = json.loads((target / "manifest.json").read_text())["nodes"]
    except FileNotFoundError:
        return [f"no dbt results found: run `dbt build --select {model}` first"]
    model_id = next((k for k, n in nodes.items()
                     if n.get("resource_type") == "model" and n.get("name") == model), None)
    if model_id is None:
        return [f"{model} has not been built yet: implement it, then run `dbt build --select {model}`"]
    tests = [r for r in results
             if nodes.get(r["unique_id"], {}).get("resource_type") == "test"
             and nodes[r["unique_id"]].get("attached_node") == model_id]
    if not tests:
        return [f"{model} was not tested in the last dbt run: run `dbt build --select {model}`"]
    return [f"test {nodes[r['unique_id']]['name']} ended with '{r['status']}' in the last run"
            for r in tests if r["status"] != "pass"]


def cmd_promote(only: str | None) -> int:
    """Flip a complete draft to enforced and regenerate its contract."""
    if not only:
        raise SpecError("usage: specgen.py promote <model>")
    conv = load_conventions()
    path, spec = load_specs(only)[0]
    if status_of(spec) != "draft":
        print(f"{spec['model']} is already {status_of(spec)}")
        return 0
    errs, _ = validate(spec, conv, as_status="enforced")
    errs += open_test_results(spec["model"])
    if errs:
        print(f"{RED}✗{RESET} {spec['model']} is not ready to enforce:")
        for e in errs:
            print(f"    {RED}-{RESET} {e}")
        return 1
    text = re.sub(r"(?m)^status:\s*draft\s*$", "status: enforced", path.read_text())
    path.write_text(text)
    print(f"{GREEN}✓{RESET} {spec['model']}: draft → enforced")
    return cmd_generate(only)


def main(argv: list[str]) -> int:
    commands = {"validate": cmd_validate, "generate": cmd_generate,
                "status": cmd_status, "task": cmd_task, "promote": cmd_promote}
    parser = argparse.ArgumentParser(prog="specgen.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=[*commands, "draft"])
    parser.add_argument("target", nargs="?", help="model name (or relation, for draft)")
    parser.add_argument("--as", dest="as_model", help="draft only: name of the new model")
    args = parser.parse_args(argv[1:])
    try:
        if args.command == "draft":
            if not args.target or not args.as_model:
                raise SpecError("usage: specgen.py draft <relation> --as <model>")
            return cmd_draft(args.target, args.as_model)
        return commands[args.command](args.target)
    except SpecError as e:
        print(f"{RED}error:{RESET} {e}")
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main(sys.argv))
