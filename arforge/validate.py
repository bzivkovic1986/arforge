from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import json
import yaml
from jsonschema import Draft202012Validator

from .model import Project, from_dict
from .semantic_validation import Finding, ValidationContext, ValidationReport, ValidationRunner, format_finding
from .validation_registry import get_ruleset

class ValidationError(Exception):
    def __init__(self, errors: List[str]):
        super().__init__("Validation failed")
        self.errors = errors

def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValidationError([f"{path}: expected a YAML mapping (object) at root"])
    return data

def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _validate_with_schema(data: Dict[str, Any], schema: Dict[str, Any], label: str) -> List[str]:
    v = Draft202012Validator(schema)
    errs = []
    for e in sorted(v.iter_errors(data), key=lambda x: (list(x.absolute_path), x.message)):
        loc = ".".join([str(p) for p in e.absolute_path]) or "<root>"
        errs.append(f"{label}:{loc}: {e.message}")
    return errs

def _schema_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas"

def _expand_patterns(base_dir: Path, patterns: Sequence[str]) -> List[Path]:
    out: List[Path] = []
    for pat in patterns:
        if any(ch in pat for ch in ["*", "?", "["]):
            matches = sorted(base_dir.glob(pat))
            out.extend([m.resolve() for m in matches if m.is_file()])
        else:
            out.append((base_dir / pat).resolve())

    seen = set()
    uniq: List[Path] = []
    for p in out:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq

def load_and_validate_aggregator(agg_path: Path, schema_path: Optional[Path] = None) -> Project:
    agg = _load_yaml(agg_path)
    agg_schema = _load_json(schema_path or (_schema_dir() / "aggregator.schema.json"))
    errs = _validate_with_schema(agg, agg_schema, str(agg_path))
    if errs:
        raise ValidationError(errs)

    base_dir = agg_path.parent
    inputs = agg["inputs"]

    merged: Dict[str, Any] = {
        "autosar": agg["autosar"],
        "datatypes": [],
        "interfaces": [],
        "swcs": [],
        "system": None,
        "connections": [],
    }

    dt_path = (base_dir / inputs["datatypes"]).resolve()
    dt_data = _load_yaml(dt_path)
    dt_schema = _load_json(_schema_dir() / "datatypes.schema.json")
    errs = _validate_with_schema(dt_data, dt_schema, str(dt_path))
    if errs:
        raise ValidationError(errs)
    merged["datatypes"] = dt_data.get("datatypes", [])

    itf_schema = _load_json(_schema_dir() / "interface.schema.json")
    interface_files = _expand_patterns(base_dir, inputs["interfaces"])
    if not interface_files:
        raise ValidationError([f"No interface files matched patterns in {agg_path}"])
    for p in interface_files:
        data = _load_yaml(p)
        errs = _validate_with_schema(data, itf_schema, str(p))
        if errs:
            raise ValidationError(errs)
        merged["interfaces"].append(data["interface"])

    swc_schema = _load_json(_schema_dir() / "swc.schema.json")
    swc_files = _expand_patterns(base_dir, inputs["swcs"])
    if not swc_files:
        raise ValidationError([f"No SWC files matched patterns in {agg_path}"])
    for p in swc_files:
        data = _load_yaml(p)
        errs = _validate_with_schema(data, swc_schema, str(p))
        if errs:
            raise ValidationError(errs)
        merged["swcs"].append(data["swc"])

    if "system" in inputs and "connections" in inputs:
        raise ValidationError([f"{agg_path}:inputs: define only one of 'system' or legacy 'connections'."])

    if "system" in inputs:
        s_path = (base_dir / inputs["system"]).resolve()
        s_data = _load_yaml(s_path)
        s_schema = _load_json(_schema_dir() / "system.schema.json")
        errs = _validate_with_schema(s_data, s_schema, str(s_path))
        if errs:
            raise ValidationError(errs)
        merged["system"] = s_data.get("system")
    else:
        c_path = (base_dir / inputs["connections"]).resolve()
        c_data = _load_yaml(c_path)
        c_schema = _load_json(_schema_dir() / "connections.schema.json")
        errs = _validate_with_schema(c_data, c_schema, str(c_path))
        if errs:
            raise ValidationError(errs)
        merged["connections"] = c_data.get("connections", [])

    project = from_dict(merged)
    sem_errs = validate_semantic(project)
    if sem_errs:
        raise ValidationError(sem_errs)
    return project

def run_semantic_validation(
    project: Project,
    ctx: Optional[ValidationContext] = None,
    *,
    ruleset: str = "core",
) -> List[Finding]:
    context = ctx or ValidationContext(project)
    runner = ValidationRunner(get_ruleset(ruleset))
    return runner.run(context)


def build_semantic_report(
    project: Project,
    ctx: Optional[ValidationContext] = None,
    *,
    ruleset: str = "core",
) -> ValidationReport:
    return ValidationReport(ruleset=ruleset, findings=run_semantic_validation(project, ctx, ruleset=ruleset))


def validate_semantic(project: Project) -> List[str]:
    # Compatibility shim for existing CLI output.
    findings = run_semantic_validation(project, None, ruleset="core")
    return [format_finding(f) for f in findings if f.severity == "error"]
