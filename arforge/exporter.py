from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .model import Project, Swc

SHARED_TEMPLATE = "shared_42.arxml.j2"
SWC_TEMPLATE = "swc_42.arxml.j2"
SYSTEM_TEMPLATE = "system_42.arxml.j2"
MONOLITHIC_TEMPLATE = "all_42.arxml.j2"


@dataclass(frozen=True)
class InputPatternExpansion:
    pattern: str
    matched_files: List[Path]


@dataclass(frozen=True)
class ExportInputSummary:
    datatypes_file: Optional[Path]
    base_types_file: Optional[Path]
    implementation_types_file: Optional[Path]
    application_types_file: Optional[Path]
    unit_patterns: List[InputPatternExpansion]
    compu_method_patterns: List[InputPatternExpansion]
    interface_patterns: List[InputPatternExpansion]
    swc_patterns: List[InputPatternExpansion]
    system_file: Optional[Path]


@dataclass(frozen=True)
class ExportModelSummary:
    datatypes_count: int
    interfaces_count: int
    sr_interfaces_count: int
    cs_interfaces_count: int
    swcs_count: int
    instances_count: int
    connectors_count: int


@dataclass(frozen=True)
class OutputArtifact:
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class ExportReport:
    project_path: Optional[Path]
    autosar_version: str
    layout: str
    template_dir: Path
    templates: Dict[str, str]
    input_summary: Optional[ExportInputSummary]
    model_summary: ExportModelSummary
    timings_ms: Dict[str, float]
    outputs: List[OutputArtifact]


def _env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=("xml", "arxml", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _split_interfaces(project: Project):
    sr = [i for i in project.interfaces if i.type == "senderReceiver"]
    cs = [i for i in project.interfaces if i.type == "clientServer"]
    sr = sorted(sr, key=lambda x: x.name)
    cs = sorted(cs, key=lambda x: x.name)
    return sr, cs


def _model_summary(project: Project) -> ExportModelSummary:
    sr, cs = _split_interfaces(project)
    return ExportModelSummary(
        datatypes_count=(
            len(project.baseTypes)
            + len(project.implementationDataTypes)
            + len(project.applicationDataTypes)
            + len(project.units)
            + len(project.compuMethods)
        ),
        interfaces_count=len(project.interfaces),
        sr_interfaces_count=len(sr),
        cs_interfaces_count=len(cs),
        swcs_count=len(project.swcs),
        instances_count=len(project.system.composition.components),
        connectors_count=len(project.system.composition.connectors),
    )


def _build_connections(project: Project) -> List[Dict[str, object]]:
    swc_by_name = {swc.name: swc for swc in project.swcs}
    instance_by_name = {instance.name: instance for instance in project.system.composition.components}

    def _sort_key(conn):
        return (
            conn.from_instance,
            conn.from_port,
            conn.to_instance,
            conn.to_port,
            conn.dataElement or "",
            conn.operation or "",
        )

    def _is_sender_receiver(conn) -> bool:
        from_instance = instance_by_name.get(conn.from_instance)
        if from_instance is None:
            return False
        from_swc = swc_by_name.get(from_instance.typeRef)
        if from_swc is None:
            return False
        from_port = next((port for port in from_swc.ports if port.name == conn.from_port), None)
        if from_port is None:
            return False
        return from_port.interfaceType == "senderReceiver"

    unique_connectors = []
    seen_sr_port_pairs: set[tuple[str, str, str, str]] = set()
    for connector in sorted(project.system.composition.connectors, key=_sort_key):
        if _is_sender_receiver(connector):
            if connector.port_pair_key in seen_sr_port_pairs:
                continue
            seen_sr_port_pairs.add(connector.port_pair_key)
        unique_connectors.append(connector)

    return [
        {
            "from_instance": c.from_instance,
            "from_port": c.from_port,
            "to_instance": c.to_instance,
            "to_port": c.to_port,
            "dataElement": c.dataElement,
            "operation": c.operation,
            "short_name": f"Conn_{idx}",
        }
        for idx, c in enumerate(unique_connectors, start=1)
    ]


def render_shared(project: Project, template_dir: Path, template_name: str = SHARED_TEMPLATE) -> str:
    env = _env(template_dir)
    tpl = env.get_template(template_name)
    base_types = sorted(project.baseTypes, key=lambda x: x.name)
    implementation_types = sorted(project.implementationDataTypes, key=lambda x: x.name)
    application_types = sorted(project.applicationDataTypes, key=lambda x: x.name)
    units = sorted(project.units, key=lambda x: x.name)
    compu_methods = sorted(project.compuMethods, key=lambda x: x.name)
    type_trefs: Dict[str, Dict[str, str]] = {
        d.name: {"package": "BaseTypes", "dest": "SW-BASE-TYPE"} for d in base_types
    }
    type_trefs.update(
        {d.name: {"package": "ImplementationDataTypes", "dest": "IMPLEMENTATION-DATA-TYPE"} for d in implementation_types}
    )
    type_trefs.update(
        {d.name: {"package": "ApplicationDataTypes", "dest": "APPLICATION-PRIMITIVE-DATA-TYPE"} for d in application_types}
    )
    sr, cs = _split_interfaces(project)
    return tpl.render(
        root_pkg=project.rootPackage,
        base_types=base_types,
        implementation_types=implementation_types,
        application_types=application_types,
        units=units,
        compu_methods=compu_methods,
        type_trefs=type_trefs,
        sr_interfaces=sr,
        cs_interfaces=cs,
    )


def render_swc(project: Project, swc: Swc, template_dir: Path, template_name: str = SWC_TEMPLATE) -> str:
    env = _env(template_dir)
    tpl = env.get_template(template_name)
    return tpl.render(root_pkg=project.rootPackage, swc=swc)


def render_system(project: Project, template_dir: Path, template_name: str = SYSTEM_TEMPLATE) -> str:
    env = _env(template_dir)
    tpl = env.get_template(template_name)
    connections = _build_connections(project)
    return tpl.render(
        root_pkg=project.rootPackage,
        system_name=project.system.name,
        composition_name=project.system.composition.name,
        components=sorted(project.system.composition.components, key=lambda x: x.name),
        connections=connections,
    )


def write_outputs_with_report(
    project: Project,
    template_dir: Path,
    out: Path,
    split_by_swc: bool,
    *,
    project_path: Optional[Path] = None,
    autosar_version: Optional[str] = None,
    input_summary: Optional[ExportInputSummary] = None,
    stage_timings_ms: Optional[Dict[str, float]] = None,
) -> ExportReport:
    timings_ms = dict(stage_timings_ms or {})
    outputs: List[OutputArtifact] = []

    render_started = perf_counter()
    if not split_by_swc:
        env = _env(template_dir)
        tpl = env.get_template(MONOLITHIC_TEMPLATE)
        base_types = sorted(project.baseTypes, key=lambda x: x.name)
        implementation_types = sorted(project.implementationDataTypes, key=lambda x: x.name)
        application_types = sorted(project.applicationDataTypes, key=lambda x: x.name)
        units = sorted(project.units, key=lambda x: x.name)
        compu_methods = sorted(project.compuMethods, key=lambda x: x.name)
        type_trefs: Dict[str, Dict[str, str]] = {
            d.name: {"package": "BaseTypes", "dest": "SW-BASE-TYPE"} for d in base_types
        }
        type_trefs.update(
            {d.name: {"package": "ImplementationDataTypes", "dest": "IMPLEMENTATION-DATA-TYPE"} for d in implementation_types}
        )
        type_trefs.update(
            {d.name: {"package": "ApplicationDataTypes", "dest": "APPLICATION-PRIMITIVE-DATA-TYPE"} for d in application_types}
        )
        swcs = sorted(project.swcs, key=lambda x: x.name)
        sr, cs = _split_interfaces(project)
        connections = _build_connections(project)
        rendered = {
            out: tpl.render(
                root_pkg=project.rootPackage,
                base_types=base_types,
                implementation_types=implementation_types,
                application_types=application_types,
                units=units,
                compu_methods=compu_methods,
                type_trefs=type_trefs,
                sr_interfaces=sr,
                cs_interfaces=cs,
                swcs=swcs,
                system_name=project.system.name,
                composition_name=project.system.composition.name,
                instances=sorted(project.system.composition.components, key=lambda x: x.name),
                connections=connections,
            )
        }
        layout = "monolithic"
        templates = {"monolithic": MONOLITHIC_TEMPLATE}
    else:
        rendered = {}
        target_dir = out
        rendered[target_dir / "shared.arxml"] = render_shared(project, template_dir, template_name=SHARED_TEMPLATE)
        for swc in sorted(project.swcs, key=lambda x: x.name):
            rendered[target_dir / f"{swc.name}.arxml"] = render_swc(project, swc=swc, template_dir=template_dir, template_name=SWC_TEMPLATE)
        rendered[target_dir / "system.arxml"] = render_system(project, template_dir, template_name=SYSTEM_TEMPLATE)
        layout = "split-by-swc"
        templates = {
            "shared": SHARED_TEMPLATE,
            "swc": SWC_TEMPLATE,
            "system": SYSTEM_TEMPLATE,
        }
    timings_ms["rendering"] = (perf_counter() - render_started) * 1000.0

    write_started = perf_counter()
    if not split_by_swc:
        out.parent.mkdir(parents=True, exist_ok=True)
    else:
        out.mkdir(parents=True, exist_ok=True)

    for path, xml in rendered.items():
        path.write_text(xml, encoding="utf-8")
        outputs.append(OutputArtifact(path=path, size_bytes=path.stat().st_size))
    timings_ms["writing"] = (perf_counter() - write_started) * 1000.0

    return ExportReport(
        project_path=project_path,
        autosar_version=autosar_version or project.autosar_version,
        layout=layout,
        template_dir=template_dir,
        templates=templates,
        input_summary=input_summary,
        model_summary=_model_summary(project),
        timings_ms=timings_ms,
        outputs=outputs,
    )


def write_outputs(project: Project, template_dir: Path, out: Path, split_by_swc: bool) -> List[Path]:
    report = write_outputs_with_report(project, template_dir=template_dir, out=out, split_by_swc=split_by_swc)
    return [artifact.path for artifact in report.outputs]
