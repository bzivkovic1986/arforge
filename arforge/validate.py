from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Sequence

import json
import yaml
from jsonschema import Draft202012Validator

from .model import Project, from_dict
from .semantic_validation import (
    Finding,
    FindingSeverity,
    ValidationContext,
    ValidationReport,
    ValidationRunner,
    format_finding,
)
from .validation_registry import get_ruleset


@dataclass(frozen=True)
class InputPatternReport:
    pattern: str
    matched_files: List[Path]


@dataclass(frozen=True)
class AggregatorLoadReport:
    project_path: Path
    autosar_version: str
    base_types_file: Optional[Path]
    implementation_types_file: Optional[Path]
    application_types_file: Optional[Path]
    unit_patterns: List[InputPatternReport]
    compu_method_patterns: List[InputPatternReport]
    interface_patterns: List[InputPatternReport]
    swc_patterns: List[InputPatternReport]
    system_file: Optional[Path]
    load_schema_ms: float
    model_build_ms: float


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
    return _expand_patterns_with_details(base_dir, patterns)[0]


def _expand_patterns_with_details(base_dir: Path, patterns: Sequence[str]) -> tuple[List[Path], List[InputPatternReport]]:
    out: List[Path] = []
    details: List[InputPatternReport] = []
    for pat in patterns:
        if any(ch in pat for ch in ["*", "?", "["]):
            matches = sorted(base_dir.glob(pat))
            files = [m.resolve() for m in matches if m.is_file()]
            out.extend(files)
            details.append(InputPatternReport(pattern=pat, matched_files=files))
        else:
            resolved = (base_dir / pat).resolve()
            out.append(resolved)
            details.append(InputPatternReport(pattern=pat, matched_files=[resolved] if resolved.is_file() else []))

    seen = set()
    uniq: List[Path] = []
    for p in out:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq, details


def load_aggregator_with_report(agg_path: Path, schema_path: Optional[Path] = None) -> tuple[Project, AggregatorLoadReport]:
    load_started = perf_counter()
    agg = _load_yaml(agg_path)
    agg_schema = _load_json(schema_path or (_schema_dir() / "aggregator.schema.json"))
    errs = _validate_with_schema(agg, agg_schema, str(agg_path))
    if errs:
        raise ValidationError(errs)

    base_dir = agg_path.parent
    inputs = agg["inputs"]

    merged: Dict[str, Any] = {
        "autosar": agg["autosar"],
        "baseTypes": [],
        "implementationDataTypes": [],
        "applicationDataTypes": [],
        "units": [],
        "compuMethods": [],
        "interfaces": [],
        "swcs": [],
        "system": None,
    }

    base_types_file: Optional[Path] = None
    implementation_types_file: Optional[Path] = None
    application_types_file: Optional[Path] = None
    unit_patterns: List[InputPatternReport] = []
    compu_method_patterns: List[InputPatternReport] = []

    uses_split = all(k in inputs for k in ["baseTypes", "implementationDataTypes", "applicationDataTypes"])
    if not uses_split:
        raise ValidationError(
            [
                f"{agg_path}:inputs: missing datatype inputs; define "
                f"'baseTypes' + 'implementationDataTypes' + 'applicationDataTypes'."
            ]
        )

    base_types_file = (base_dir / inputs["baseTypes"]).resolve()
    base_types_data = _load_yaml(base_types_file)
    base_types_schema = _load_json(_schema_dir() / "base_types.schema.json")
    errs = _validate_with_schema(base_types_data, base_types_schema, str(base_types_file))
    if errs:
        raise ValidationError(errs)
    merged["baseTypes"] = base_types_data.get("baseTypes", [])

    implementation_types_file = (base_dir / inputs["implementationDataTypes"]).resolve()
    implementation_types_data = _load_yaml(implementation_types_file)
    implementation_types_schema = _load_json(_schema_dir() / "implementation_types.schema.json")
    errs = _validate_with_schema(implementation_types_data, implementation_types_schema, str(implementation_types_file))
    if errs:
        raise ValidationError(errs)
    merged["implementationDataTypes"] = implementation_types_data.get("implementationDataTypes", [])

    application_types_file = (base_dir / inputs["applicationDataTypes"]).resolve()
    application_types_data = _load_yaml(application_types_file)
    application_types_schema = _load_json(_schema_dir() / "application_types.schema.json")
    errs = _validate_with_schema(application_types_data, application_types_schema, str(application_types_file))
    if errs:
        raise ValidationError(errs)
    merged["applicationDataTypes"] = application_types_data.get("applicationDataTypes", [])

    if "units" in inputs:
        units_schema = _load_json(_schema_dir() / "units.schema.json")
        unit_files, unit_patterns = _expand_patterns_with_details(base_dir, inputs["units"])
        for p in unit_files:
            data = _load_yaml(p)
            errs = _validate_with_schema(data, units_schema, str(p))
            if errs:
                raise ValidationError(errs)
            merged["units"].extend(data.get("units", []))

    if "compuMethods" in inputs:
        compu_schema = _load_json(_schema_dir() / "compu_methods.schema.json")
        compu_files, compu_method_patterns = _expand_patterns_with_details(base_dir, inputs["compuMethods"])
        for p in compu_files:
            data = _load_yaml(p)
            errs = _validate_with_schema(data, compu_schema, str(p))
            if errs:
                raise ValidationError(errs)
            merged["compuMethods"].extend(data.get("compuMethods", []))

    itf_schema = _load_json(_schema_dir() / "interface.schema.json")
    interface_files, interface_patterns = _expand_patterns_with_details(base_dir, inputs["interfaces"])
    if not interface_files:
        raise ValidationError([f"No interface files matched patterns in {agg_path}"])
    for p in interface_files:
        data = _load_yaml(p)
        errs = _validate_with_schema(data, itf_schema, str(p))
        if errs:
            raise ValidationError(errs)
        merged["interfaces"].append(data["interface"])

    swc_schema = _load_json(_schema_dir() / "swc.schema.json")
    swc_files, swc_patterns = _expand_patterns_with_details(base_dir, inputs["swcs"])
    if not swc_files:
        raise ValidationError([f"No SWC files matched patterns in {agg_path}"])
    for p in swc_files:
        data = _load_yaml(p)
        errs = _validate_with_schema(data, swc_schema, str(p))
        if errs:
            raise ValidationError(errs)
        merged["swcs"].append(data["swc"])

    system_file: Optional[Path] = None
    s_path = (base_dir / inputs["system"]).resolve()
    s_data = _load_yaml(s_path)
    s_schema = _load_json(_schema_dir() / "system.schema.json")
    errs = _validate_with_schema(s_data, s_schema, str(s_path))
    if errs:
        raise ValidationError(errs)
    merged["system"] = s_data.get("system")
    system_file = s_path

    load_schema_ms = (perf_counter() - load_started) * 1000.0
    model_started = perf_counter()
    project = from_dict(merged)
    model_build_ms = (perf_counter() - model_started) * 1000.0

    report = AggregatorLoadReport(
        project_path=agg_path,
        autosar_version=project.autosar_version,
        base_types_file=base_types_file,
        implementation_types_file=implementation_types_file,
        application_types_file=application_types_file,
        unit_patterns=unit_patterns,
        compu_method_patterns=compu_method_patterns,
        interface_patterns=interface_patterns,
        swc_patterns=swc_patterns,
        system_file=system_file,
        load_schema_ms=load_schema_ms,
        model_build_ms=model_build_ms,
    )
    return project, report

def load_aggregator(agg_path: Path, schema_path: Optional[Path] = None) -> Project:
    project, _ = load_aggregator_with_report(agg_path, schema_path=schema_path)
    return project


def load_and_validate_aggregator(agg_path: Path, schema_path: Optional[Path] = None) -> Project:
    project = load_aggregator(agg_path, schema_path=schema_path)
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
    context = ctx or ValidationContext(project)
    runner = ValidationRunner(get_ruleset(ruleset))
    return runner.run_report(context, ruleset=ruleset)


def validate_semantic(project: Project) -> List[str]:
    # Compatibility shim for existing CLI output.
    findings = run_semantic_validation(project, None, ruleset="core")
    return [format_finding(f) for f in findings if f.severity == FindingSeverity.ERROR]
