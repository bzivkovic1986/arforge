from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import json
import yaml
from jsonschema import Draft202012Validator

from .model import Project, from_dict

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

def validate_semantic(project: Project) -> List[str]:
    errs: List[str] = []

    # uniqueness
    if len({d.name for d in project.datatypes}) != len(project.datatypes):
        errs.append("Duplicate datatype names found.")
    if len({i.name for i in project.interfaces}) != len(project.interfaces):
        errs.append("Duplicate interface names found.")
    if len({s.name for s in project.swcs}) != len(project.swcs):
        errs.append("Duplicate SWC names found.")

    iface_by_name = {i.name: i for i in project.interfaces}
    dt_names = {d.name for d in project.datatypes}

    # interface internal refs
    for itf in project.interfaces:
        if itf.type == "senderReceiver":
            if not itf.dataElements:
                errs.append(f"SenderReceiver interface '{itf.name}' must have dataElements.")
            else:
                for de in itf.dataElements:
                    if de.typeRef not in dt_names:
                        errs.append(f"Interface '{itf.name}' dataElement '{de.name}' references unknown datatype '{de.typeRef}'.")
        elif itf.type == "clientServer":
            if not itf.operations:
                errs.append(f"ClientServer interface '{itf.name}' must have operations.")
        else:
            errs.append(f"Unknown interface type '{itf.type}' on '{itf.name}'.")

    # ports -> interfaces
    swc_by_name = {s.name: s for s in project.swcs}
    for s in project.swcs:
        port_names = [p.name for p in s.ports]
        if len(set(port_names)) != len(port_names):
            errs.append(f"SWC '{s.name}' has duplicate port names.")
        run_names = [r.name for r in s.runnables]
        if len(set(run_names)) != len(run_names):
            errs.append(f"SWC '{s.name}' has duplicate runnable names.")
        for p in s.ports:
            itf = iface_by_name.get(p.interfaceRef)
            if itf is None:
                errs.append(f"SWC '{s.name}' port '{p.name}' references unknown interface '{p.interfaceRef}'.")
            else:
                # Ensure interfaceType derived matches actual
                if p.interfaceType != itf.type:
                    errs.append(f"Internal mismatch: port '{s.name}.{p.name}' interfaceType '{p.interfaceType}' != interface '{itf.type}'.")

    # connections
    for c in project.connections:
        if c.from_swc not in swc_by_name:
            errs.append(f"Connection references unknown from SWC '{c.from_swc}'.")
            continue
        if c.to_swc not in swc_by_name:
            errs.append(f"Connection references unknown to SWC '{c.to_swc}'.")
            continue

        from_swc = swc_by_name[c.from_swc]
        to_swc = swc_by_name[c.to_swc]
        from_port = next((p for p in from_swc.ports if p.name == c.from_port), None)
        to_port = next((p for p in to_swc.ports if p.name == c.to_port), None)

        if from_port is None:
            errs.append(f"Connection from '{c.from_swc}.{c.from_port}' references unknown port.")
            continue
        if to_port is None:
            errs.append(f"Connection to '{c.to_swc}.{c.to_port}' references unknown port.")
            continue

        if from_port.direction != "provides":
            errs.append(f"Connection from '{c.from_swc}.{c.from_port}' must be a provides-port.")
        if to_port.direction != "requires":
            errs.append(f"Connection to '{c.to_swc}.{c.to_port}' must be a requires-port.")

        if from_port.interfaceRef != to_port.interfaceRef:
            errs.append(
                f"Connection interface mismatch: '{c.from_swc}.{c.from_port}' uses '{from_port.interfaceRef}' but "
                f"'{c.to_swc}.{c.to_port}' uses '{to_port.interfaceRef}'."
            )
            continue

        itf = iface_by_name.get(from_port.interfaceRef)
        if not itf:
            continue

        # SR must specify dataElement; CS must specify operation
        if itf.type == "senderReceiver":
            if not c.dataElement or c.operation:
                errs.append(f"SenderReceiver connection {c.from_swc}.{c.from_port} -> {c.to_swc}.{c.to_port} must specify dataElement only.")
            else:
                if c.dataElement not in {de.name for de in (itf.dataElements or [])}:
                    errs.append(f"Connection dataElement '{c.dataElement}' not found in interface '{itf.name}'.")
        else:
            if not c.operation or c.dataElement:
                errs.append(f"ClientServer connection {c.from_swc}.{c.from_port} -> {c.to_swc}.{c.to_port} must specify operation only.")
            else:
                if c.operation not in {op.name for op in (itf.operations or [])}:
                    errs.append(f"Connection operation '{c.operation}' not found in interface '{itf.name}'.")

    return errs
