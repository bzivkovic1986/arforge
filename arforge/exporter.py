from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
from time import perf_counter
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .model import CompuMethod, Connection, Interface, ModeDeclarationGroup, Operation, Project, Runnable, Swc

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
    base_types_file: Optional[Path]
    implementation_types_file: Optional[Path]
    application_types_file: Optional[Path]
    unit_patterns: List[InputPatternExpansion]
    compu_method_patterns: List[InputPatternExpansion]
    mode_declaration_group_patterns: List[InputPatternExpansion]
    interface_patterns: List[InputPatternExpansion]
    swc_patterns: List[InputPatternExpansion]
    system_file: Optional[Path]


@dataclass(frozen=True)
class ExportModelSummary:
    datatypes_count: int
    mode_declaration_groups_count: int
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


def _connection_sort_key(conn: Connection) -> tuple[str, str, str, str]:
    return (
        conn.from_instance,
        conn.from_port,
        conn.to_instance,
        conn.to_port,
    )


def _sort_compu_method(compu_method: CompuMethod) -> CompuMethod:
    return replace(
        compu_method,
        entries=sorted(compu_method.entries, key=lambda entry: (entry.value, entry.label)),
    )


def _sort_operation(operation: Operation) -> Operation:
    # Preserve authored argument order because it defines the exported signature.
    return replace(
        operation,
        arguments=list(operation.arguments),
        possibleErrors=sorted(
            operation.possibleErrors,
            key=lambda err: (
                err.name,
                -1 if err.code is None else err.code,
            ),
        ),
    )


def _sort_interface(interface: Interface) -> Interface:
    if interface.type == "senderReceiver":
        return replace(
            interface,
            dataElements=sorted(interface.dataElements or [], key=lambda data_element: data_element.name),
        )

    operations = sorted((interface.operations or []), key=lambda operation: operation.name)
    return replace(interface, operations=[_sort_operation(operation) for operation in operations])


def _sort_mode_declaration_group(group: ModeDeclarationGroup) -> ModeDeclarationGroup:
    # Preserve authored mode order because MODE-DECLARATION-GROUP uses explicit ordering.
    return replace(group, modes=list(group.modes))


def _collect_interface_errors(interface: Interface) -> list[object]:
    unique_errors: dict[str, object] = {}
    for operation in interface.operations or []:
        for error in operation.possibleErrors:
            unique_errors.setdefault(error.name, error)
    return list(unique_errors.values())


def _sort_runnable(runnable: Runnable) -> Runnable:
    return replace(
        runnable,
        reads=sorted(runnable.reads, key=lambda access: (access.port, access.dataElement)),
        writes=sorted(runnable.writes, key=lambda access: (access.port, access.dataElement)),
        calls=sorted(
            runnable.calls,
            key=lambda call: (
                call.port,
                call.operation,
                -1 if call.timeoutMs is None else call.timeoutMs,
            ),
        ),
        operationInvokedEvents=sorted(
            runnable.operationInvokedEvents,
            key=lambda event: (event.port, event.operation),
        ),
        dataReceiveEvents=sorted(
            runnable.dataReceiveEvents,
            key=lambda event: (event.port, event.dataElement),
        ),
        raisesErrors=sorted(
            runnable.raisesErrors,
            key=lambda raised_error: (raised_error.operation, raised_error.error),
        ),
    )


def _sort_swc(swc: Swc) -> Swc:
    return replace(
        swc,
        ports=sorted(swc.ports, key=lambda port: port.name),
        runnables=sorted(
            (_sort_runnable(runnable) for runnable in swc.runnables),
            key=lambda runnable: runnable.name,
        ),
    )


def _swc_type_dests(project: Project) -> Dict[str, str]:
    return {swc.name: swc.component_type_dest for swc in project.swcs}


def _safe_filename_stem(value: Optional[str], fallback: str) -> str:
    candidate = (value or "").strip()
    candidate = re.sub(r"[^A-Za-z0-9_.-]+", "_", candidate)
    candidate = candidate.strip("._-")
    return candidate or fallback


def _shared_output_name(project: Project) -> str:
    stem = _safe_filename_stem(
        project.rootPackage or project.system.name or project.system.composition.name,
        "Shared",
    )
    return f"{stem}_SharedTypes.arxml"


def _system_output_name(project: Project) -> str:
    stem = _safe_filename_stem(
        project.system.name or project.system.composition.name or project.rootPackage,
        "system",
    )
    return f"{stem}.arxml"


def _sort_project_for_export(project: Project) -> Project:
    implementation_types = []
    for implementation_type in sorted(project.implementationDataTypes, key=lambda data_type: data_type.name):
        # Preserve authored field order because structure layout can be semantically meaningful.
        implementation_types.append(replace(implementation_type, fields=list(implementation_type.fields)))

    return replace(
        project,
        baseTypes=sorted(project.baseTypes, key=lambda data_type: data_type.name),
        implementationDataTypes=implementation_types,
        applicationDataTypes=sorted(project.applicationDataTypes, key=lambda data_type: data_type.name),
        units=sorted(project.units, key=lambda unit: unit.name),
        compuMethods=sorted(
            (_sort_compu_method(compu_method) for compu_method in project.compuMethods),
            key=lambda compu_method: compu_method.name,
        ),
        modeDeclarationGroups=sorted(
            (_sort_mode_declaration_group(group) for group in project.modeDeclarationGroups),
            key=lambda group: group.name,
        ),
        interfaces=sorted((_sort_interface(interface) for interface in project.interfaces), key=lambda interface: interface.name),
        swcs=sorted((_sort_swc(swc) for swc in project.swcs), key=lambda swc: swc.name),
        system=replace(
            project.system,
            composition=replace(
                project.system.composition,
                components=sorted(project.system.composition.components, key=lambda component: component.name),
                connectors=sorted(project.system.composition.connectors, key=_connection_sort_key),
            ),
        ),
    )


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
        mode_declaration_groups_count=len(project.modeDeclarationGroups),
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
    seen_port_pairs: set[tuple[str, str, str, str]] = set()
    for connector in project.system.composition.connectors:
        if _is_sender_receiver(connector):
            if connector.port_pair_key in seen_port_pairs:
                continue
            seen_port_pairs.add(connector.port_pair_key)
        else:
            if connector.identity_key in seen_port_pairs:
                continue
            seen_port_pairs.add(connector.identity_key)
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
    project = _sort_project_for_export(project)
    base_types = project.baseTypes
    implementation_types = project.implementationDataTypes
    application_types = project.applicationDataTypes
    units = project.units
    compu_methods = project.compuMethods
    mode_declaration_groups = project.modeDeclarationGroups
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
        mode_declaration_groups=mode_declaration_groups,
        type_trefs=type_trefs,
        sr_interfaces=sr,
        cs_interfaces=cs,
        cs_interface_errors={interface.name: _collect_interface_errors(interface) for interface in cs},
    )


def render_swc(project: Project, swc: Swc, template_dir: Path, template_name: str = SWC_TEMPLATE) -> str:
    env = _env(template_dir)
    tpl = env.get_template(template_name)
    project = _sort_project_for_export(project)
    swc = next(candidate for candidate in project.swcs if candidate.name == swc.name)
    return tpl.render(root_pkg=project.rootPackage, swc=swc)


def render_system(project: Project, template_dir: Path, template_name: str = SYSTEM_TEMPLATE) -> str:
    env = _env(template_dir)
    tpl = env.get_template(template_name)
    project = _sort_project_for_export(project)
    connections = _build_connections(project)
    return tpl.render(
        root_pkg=project.rootPackage,
        system_name=project.system.name,
        composition_name=project.system.composition.name,
        components=project.system.composition.components,
        connections=connections,
        swc_type_dests=_swc_type_dests(project),
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
    project = _sort_project_for_export(project)
    timings_ms = dict(stage_timings_ms or {})
    outputs: List[OutputArtifact] = []

    render_started = perf_counter()
    if not split_by_swc:
        env = _env(template_dir)
        tpl = env.get_template(MONOLITHIC_TEMPLATE)
        base_types = project.baseTypes
        implementation_types = project.implementationDataTypes
        application_types = project.applicationDataTypes
        units = project.units
        compu_methods = project.compuMethods
        mode_declaration_groups = project.modeDeclarationGroups
        type_trefs: Dict[str, Dict[str, str]] = {
            d.name: {"package": "BaseTypes", "dest": "SW-BASE-TYPE"} for d in base_types
        }
        type_trefs.update(
            {d.name: {"package": "ImplementationDataTypes", "dest": "IMPLEMENTATION-DATA-TYPE"} for d in implementation_types}
        )
        type_trefs.update(
            {d.name: {"package": "ApplicationDataTypes", "dest": "APPLICATION-PRIMITIVE-DATA-TYPE"} for d in application_types}
        )
        swcs = project.swcs
        sr, cs = _split_interfaces(project)
        connections = _build_connections(project)
        swc_type_dests = _swc_type_dests(project)
        rendered = {
            out: tpl.render(
                root_pkg=project.rootPackage,
                base_types=base_types,
                implementation_types=implementation_types,
                application_types=application_types,
                units=units,
                compu_methods=compu_methods,
                mode_declaration_groups=mode_declaration_groups,
                type_trefs=type_trefs,
                sr_interfaces=sr,
                cs_interfaces=cs,
                cs_interface_errors={interface.name: _collect_interface_errors(interface) for interface in cs},
                swcs=swcs,
                system_name=project.system.name,
                composition_name=project.system.composition.name,
                instances=project.system.composition.components,
                connections=connections,
                swc_type_dests=swc_type_dests,
            )
        }
        layout = "monolithic"
        templates = {"monolithic": MONOLITHIC_TEMPLATE}
    else:
        rendered = {}
        target_dir = out
        rendered[target_dir / _shared_output_name(project)] = render_shared(project, template_dir, template_name=SHARED_TEMPLATE)
        for swc in project.swcs:
            rendered[target_dir / f"{swc.name}.arxml"] = render_swc(project, swc=swc, template_dir=template_dir, template_name=SWC_TEMPLATE)
        rendered[target_dir / _system_output_name(project)] = render_system(project, template_dir, template_name=SYSTEM_TEMPLATE)
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
