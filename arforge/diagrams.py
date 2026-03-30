from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List, Literal, Sequence

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .exporter import _safe_filename_stem, _sort_project_for_export
from .model import ApplicationDataType, Connection, Interface, ModeDeclarationGroup, Port, Project, Swc


DiagramFormat = Literal["plantuml"]


@dataclass(frozen=True)
class DiagramOutputArtifact:
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class CompositionPortView:
    id: str
    name: str
    kind_label: str
    interface_name: str
    extra_label: str | None
    style_class: str
    fill_color: str


@dataclass(frozen=True)
class CompositionInstanceView:
    id: str
    name: str
    type_name: str
    type_label: str
    fill_color: str
    incoming_ports: List[CompositionPortView]
    outgoing_ports: List[CompositionPortView]


@dataclass(frozen=True)
class CompositionRowView:
    id: str
    instances: List[CompositionInstanceView]


@dataclass(frozen=True)
class CompositionRowLinkView:
    source_id: str
    target_id: str
    direction: str


@dataclass(frozen=True)
class CompositionConnectorView:
    source_id: str
    target_id: str
    label: str
    line_style: str
    direction_hint: str


@dataclass(frozen=True)
class CompositionDiagramView:
    system_name: str
    composition_name: str
    boundary_id: str
    grid_columns: int
    rows: List[CompositionRowView]
    instances: List[CompositionInstanceView]
    row_links: List[CompositionRowLinkView]
    assembly_connectors: List[CompositionConnectorView]
    delegation_connectors: List[CompositionConnectorView]


@dataclass(frozen=True)
class InterfaceEntityView:
    id: str
    name: str
    stereotype: str
    layer: str
    body_lines: List[str]
    style_class: str
    fill_color: str
    shape: str


@dataclass(frozen=True)
class InterfaceRelationView:
    source_id: str
    target_id: str
    label: str


@dataclass(frozen=True)
class InterfaceLayerView:
    id: str
    entities: List[InterfaceEntityView]


@dataclass(frozen=True)
class InterfaceDiagramView:
    entities: List[InterfaceEntityView]
    layers: List[InterfaceLayerView]
    relations: List[InterfaceRelationView]


@dataclass(frozen=True)
class BehaviorPortView:
    id: str
    name: str
    kind_label: str
    interface_name: str
    extra_label: str | None
    style_class: str
    fill_color: str


@dataclass(frozen=True)
class BehaviorRunnableView:
    id: str
    name: str
    metadata_lines: List[str]


@dataclass(frozen=True)
class BehaviorRunnableRowView:
    id: str
    runnables: List[BehaviorRunnableView]


@dataclass(frozen=True)
class BehaviorEdgeView:
    source_id: str
    target_id: str
    label: str
    style_class: str


@dataclass(frozen=True)
class BehaviorDiagramView:
    swc_name: str
    swc_type_label: str
    swc_fill_color: str
    incoming_ports: List[BehaviorPortView]
    outgoing_ports: List[BehaviorPortView]
    runnable_columns: int
    runnable_rows: List[BehaviorRunnableRowView]
    runnables: List[BehaviorRunnableView]
    edges: List[BehaviorEdgeView]


@dataclass(frozen=True)
class DiagramBuild:
    composition: CompositionDiagramView
    interfaces: InterfaceDiagramView
    behaviors: List[BehaviorDiagramView]


@dataclass(frozen=True)
class DiagramBackendSpec:
    extension: str
    composition_template: str
    interfaces_template: str
    behavior_template: str


BACKENDS: Dict[DiagramFormat, DiagramBackendSpec] = {
    "plantuml": DiagramBackendSpec(
        extension=".puml",
        composition_template="diagrams/plantuml/composition.puml.j2",
        interfaces_template="diagrams/plantuml/interfaces.puml.j2",
        behavior_template="diagrams/plantuml/behavior.puml.j2",
    ),
}


def _env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=("xml", "arxml", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _node_id(*parts: str) -> str:
    raw = "__".join(part for part in parts if part)
    raw = re.sub(r"[^A-Za-z0-9_]+", "_", raw)
    raw = raw.strip("_")
    return raw or "node"


def _port_style(port: Port) -> tuple[str, str, str]:
    token = f"{port.interfaceType}_{port.direction}"
    if token == "senderReceiver_provides":
        return ("SR provides", "srProvides", "#b7efc5")
    if token == "senderReceiver_requires":
        return ("SR requires", "srRequires", "#9ec5fe")
    if token == "clientServer_provides":
        return ("C/S provides", "csProvides", "#fff3bf")
    if token == "clientServer_requires":
        return ("C/S requires", "csRequires", "#ffcf99")
    if token == "modeSwitch_provides":
        return ("ModeSwitch provides", "msProvides", "#e0bbff")
    return ("ModeSwitch requires", "msRequires", "#ffb3c6")


def _port_extra_label(port: Port) -> str | None:
    if port.interfaceType == "senderReceiver" and port.comSpec and port.comSpec.mode:
        if port.comSpec.mode == "queued" and port.comSpec.queueLength is not None:
            return f"queued x{port.comSpec.queueLength}"
        return port.comSpec.mode
    if port.interfaceType == "modeSwitch" and port.modeGroupRef:
        return port.modeGroupRef
    return None


def _connector_port_type(connection: Connection, project: Project) -> Port | None:
    instance_by_name = {instance.name: instance for instance in project.system.composition.components}
    swc_by_name = {swc.name: swc for swc in project.swcs}
    source_instance = instance_by_name.get(connection.from_instance)
    if source_instance is None:
        return None
    swc = swc_by_name.get(source_instance.typeRef)
    if swc is None:
        return None
    return next((port for port in swc.ports if port.name == connection.from_port), None)


def _swc_fill_color(category: str) -> str:
    return {
        "application": "#d6e4ff",
        "service": "#d8f3dc",
        "complexDeviceDriver": "#ffe5b4",
    }.get(category, "#f7f7f7")


def _connector_style(source_port: Port | None) -> str:
    if source_port is None:
        return "[#666666]"
    return {
        "senderReceiver": "[#2e8b57]",
        "clientServer": "[#c77d00,bold]",
        "modeSwitch": "[#8e44ad,dashed]",
    }.get(source_port.interfaceType, "[#666666]")


def _sorted_unique(items: Iterable[str]) -> List[str]:
    return sorted({item for item in items if item})


def _build_interface_layers(entities: Iterable[InterfaceEntityView]) -> List[InterfaceLayerView]:
    layer_order = [
        "instances",
        "ports",
        "interfaces",
        "application_types",
        "implementation_types",
        "compu_methods",
        "mode_groups",
    ]
    grouped = {layer: [] for layer in layer_order}
    for entity in entities:
        grouped.setdefault(entity.layer, []).append(entity)
    return [
        InterfaceLayerView(id=layer, entities=sorted(grouped[layer], key=lambda entity: (entity.name, entity.stereotype)))
        for layer in layer_order
        if grouped.get(layer)
    ]


def _build_composition_view(project: Project) -> CompositionDiagramView:
    swc_by_name = {swc.name: swc for swc in project.swcs}
    instances: List[CompositionInstanceView] = []
    for instance in project.system.composition.components:
        swc = swc_by_name[instance.typeRef]
        ports = []
        for port in swc.ports:
            kind_label, style_class, fill_color = _port_style(port)
            ports.append(
                CompositionPortView(
                    id=_node_id(instance.name, port.name),
                    name=port.name,
                    kind_label=kind_label,
                    interface_name=port.interfaceRef,
                    extra_label=_port_extra_label(port),
                    style_class=style_class,
                    fill_color=fill_color,
                )
            )
        instances.append(
            CompositionInstanceView(
                id=_node_id(instance.name),
                name=instance.name,
                type_name=instance.typeRef,
                type_label=_swc_category_label(swc.category),
                fill_color=_swc_fill_color(swc.category),
                incoming_ports=[port for port in ports if "requires" in port.kind_label],
                outgoing_ports=[port for port in ports if "provides" in port.kind_label],
            )
        )

    grid_columns = _composition_grid_columns(len(instances))
    instance_positions = {
        instance.name: (index // grid_columns, index % grid_columns)
        for index, instance in enumerate(project.system.composition.components)
    }

    assembly_connectors: List[CompositionConnectorView] = []
    for connector in project.system.composition.connectors:
        source_port = _connector_port_type(connector, project)
        line_style = _connector_style(source_port)
        direction_hint = _connector_direction_hint(
            connector.from_instance,
            connector.to_instance,
            instance_positions,
        )
        assembly_connectors.append(
            CompositionConnectorView(
                source_id=_node_id(connector.from_instance, connector.from_port),
                target_id=_node_id(connector.to_instance, connector.to_port),
                label="",
                line_style=line_style,
                direction_hint=direction_hint,
            )
        )
    assembly_connectors = sorted(
        assembly_connectors,
        key=lambda connector: (
            {"down": 0, "right": 1, "left": 2, "up": 3}.get(connector.direction_hint, 9),
            connector.source_id,
            connector.target_id,
            connector.label,
        ),
    )
    rows = [
        CompositionRowView(
            id=_node_id(project.system.composition.name, "row", str(row_index + 1)),
            instances=instances[row_index : row_index + grid_columns],
        )
        for row_index in range(0, len(instances), grid_columns)
    ]
    row_links: List[CompositionRowLinkView] = []
    for row in rows:
        for left, right in zip(row.instances, row.instances[1:]):
            row_links.append(
                CompositionRowLinkView(
                    source_id=left.id,
                    target_id=right.id,
                    direction="right",
                )
            )
    for upper_row, lower_row in zip(rows, rows[1:]):
        if upper_row.instances and lower_row.instances:
            row_links.append(
                CompositionRowLinkView(
                    source_id=upper_row.instances[0].id,
                    target_id=lower_row.instances[0].id,
                    direction="down",
                )
            )

    return CompositionDiagramView(
        system_name=project.system.name,
        composition_name=project.system.composition.name,
        boundary_id=_node_id(project.system.composition.name),
        grid_columns=grid_columns,
        rows=rows,
        instances=instances,
        row_links=row_links,
        assembly_connectors=assembly_connectors,
        delegation_connectors=[],
    )


def _composition_grid_columns(instance_count: int) -> int:
    if instance_count <= 4:
        return 1
    if instance_count <= 8:
        return 2
    return 3


def _swc_category_label(category: str) -> str:
    return {
        "application": "(Application SWC)",
        "service": "(Service SWC)",
        "complexDeviceDriver": "(Complex Device Driver)",
    }.get(category, f"({category})")


def _connector_direction_hint(
    source_instance: str,
    target_instance: str,
    instance_positions: Dict[str, tuple[int, int]],
) -> str:
    source_row, source_col = instance_positions.get(source_instance, (0, 0))
    target_row, target_col = instance_positions.get(target_instance, (0, 0))
    row_delta = target_row - source_row
    col_delta = target_col - source_col

    if row_delta > 0 and abs(row_delta) >= abs(col_delta):
        return "down"
    if row_delta < 0 and abs(row_delta) >= abs(col_delta):
        return "up"
    if col_delta > 0:
        return "right"
    if col_delta < 0:
        return "left"
    return "down"


def _type_body_lines(data_type: ApplicationDataType) -> List[str]:
    lines = [f"impl: {data_type.implementationTypeRef}"]
    if data_type.constraint is not None:
        lines.append(f"range: {data_type.constraint.min}..{data_type.constraint.max}")
    if data_type.unitRef:
        lines.append(f"unit: {data_type.unitRef}")
    if data_type.compuMethodRef:
        lines.append(f"compu: {data_type.compuMethodRef}")
    return lines


def _build_interface_view(project: Project) -> InterfaceDiagramView:
    app_types = {data_type.name: data_type for data_type in project.applicationDataTypes}
    impl_types = {data_type.name: data_type for data_type in project.implementationDataTypes}
    compu_methods = {compu.name: compu for compu in project.compuMethods}
    mode_groups = {group.name: group for group in project.modeDeclarationGroups}
    swc_by_name = {swc.name: swc for swc in project.swcs}

    entities: List[InterfaceEntityView] = []
    relations: List[InterfaceRelationView] = []
    referenced_app_types: set[str] = set()
    referenced_impl_types: set[str] = set()
    referenced_compu_methods: set[str] = set()
    referenced_mode_groups: set[str] = set()

    for instance in project.system.composition.components:
        swc = swc_by_name.get(instance.typeRef)
        entities.append(
            InterfaceEntityView(
                id=_node_id("instance", instance.name),
                name=instance.name,
                stereotype="componentInstance",
                layer="instances",
                body_lines=[f"type: {instance.typeRef}"],
                style_class="componentInstance",
                fill_color="#f7f7f7",
                shape="class",
            )
        )
        if swc is None:
            continue
        for port in swc.ports:
            kind_label, _, fill_color = _port_style(port)
            port_id = _node_id("port", instance.name, port.name)
            port_lines = [kind_label]
            entities.append(
                InterfaceEntityView(
                    id=port_id,
                    name=port.name,
                    stereotype="instantiatedPort",
                    layer="ports",
                    body_lines=port_lines,
                    style_class="instantiatedPort",
                    fill_color=fill_color,
                    shape="class",
                )
            )
            relations.append(
                InterfaceRelationView(
                    source_id=_node_id("instance", instance.name),
                    target_id=port_id,
                    label="port",
                )
            )
            relations.append(
                InterfaceRelationView(
                    source_id=port_id,
                    target_id=_node_id("if", port.interfaceRef),
                    label="interface",
                )
            )

    for interface in project.interfaces:
        body_lines: List[str] = []
        if interface.type == "senderReceiver":
            for data_element in interface.dataElements or []:
                body_lines.append(f"data {data_element.name}: {data_element.typeRef}")
                referenced_app_types.add(data_element.typeRef)
                relations.append(
                    InterfaceRelationView(
                        source_id=_node_id("if", interface.name),
                        target_id=_node_id("type", data_element.typeRef),
                        label=f"data {data_element.name}",
                    )
                )
        elif interface.type == "clientServer":
            for operation in interface.operations or []:
                args = ", ".join(
                    f"{argument.direction} {argument.name}: {argument.typeRef}"
                    for argument in operation.arguments
                )
                signature = f"op {operation.name}({args})"
                if operation.returnType and operation.returnType != "void":
                    signature += f" : {operation.returnType}"
                    if operation.returnType in app_types or operation.returnType in impl_types:
                        relations.append(
                            InterfaceRelationView(
                                source_id=_node_id("if", interface.name),
                                target_id=_node_id("type", operation.returnType),
                                label=f"returns {operation.name}",
                            )
                        )
                        if operation.returnType in app_types:
                            referenced_app_types.add(operation.returnType)
                        else:
                            referenced_impl_types.add(operation.returnType)
                body_lines.append(signature)
                for argument in operation.arguments:
                    if argument.typeRef in app_types:
                        referenced_app_types.add(argument.typeRef)
                        relations.append(
                            InterfaceRelationView(
                                source_id=_node_id("if", interface.name),
                                target_id=_node_id("type", argument.typeRef),
                                label=f"arg {operation.name}.{argument.name}",
                            )
                        )
                    elif argument.typeRef in impl_types:
                        referenced_impl_types.add(argument.typeRef)
                        relations.append(
                            InterfaceRelationView(
                                source_id=_node_id("if", interface.name),
                                target_id=_node_id("type", argument.typeRef),
                                label=f"arg {operation.name}.{argument.name}",
                            )
                        )
        else:
            if interface.modeGroupRef:
                body_lines.append(f"modeGroup: {interface.modeGroupRef}")
                referenced_mode_groups.add(interface.modeGroupRef)
                relations.append(
                    InterfaceRelationView(
                        source_id=_node_id("if", interface.name),
                        target_id=_node_id("mode", interface.modeGroupRef),
                        label="mode group",
                    )
                )

        entities.append(
            InterfaceEntityView(
                id=_node_id("if", interface.name),
                name=interface.name,
                stereotype=f"{interface.type}Interface",
                layer="interfaces",
                body_lines=body_lines,
                style_class=f"interface_{interface.type}",
                fill_color={
                    "senderReceiver": "#d8e9ff",
                    "clientServer": "#fff2cc",
                    "modeSwitch": "#eadcf8",
                }[interface.type],
                shape="class",
            )
        )

    for type_name in sorted(referenced_app_types):
        data_type = app_types[type_name]
        entities.append(
            InterfaceEntityView(
                id=_node_id("type", data_type.name),
                name=data_type.name,
                stereotype="applicationDataType",
                layer="application_types",
                body_lines=_type_body_lines(data_type),
                style_class="applicationType",
                fill_color="#d9f2d9",
                shape="class",
            )
        )
        referenced_impl_types.add(data_type.implementationTypeRef)
        relations.append(
            InterfaceRelationView(
                source_id=_node_id("type", data_type.name),
                target_id=_node_id("type", data_type.implementationTypeRef),
                label="impl",
            )
        )
        if data_type.compuMethodRef and data_type.compuMethodRef in compu_methods:
            referenced_compu_methods.add(data_type.compuMethodRef)
            relations.append(
                InterfaceRelationView(
                    source_id=_node_id("type", data_type.name),
                    target_id=_node_id("compu", data_type.compuMethodRef),
                    label="compu",
                )
            )

    for type_name in sorted(referenced_impl_types):
        data_type = impl_types.get(type_name)
        if data_type is None:
            continue
        body_lines = []
        if data_type.baseTypeRef:
            body_lines.append(f"base: {data_type.baseTypeRef}")
        if data_type.is_array and data_type.elementTypeRef and data_type.length is not None:
            body_lines.append(f"array[{data_type.length}] of {data_type.elementTypeRef}")
        for field in data_type.fields:
            body_lines.append(f"field {field.name}: {field.typeRef}")
        entities.append(
            InterfaceEntityView(
                id=_node_id("type", data_type.name),
                name=data_type.name,
                stereotype="implementationDataType",
                layer="implementation_types",
                body_lines=body_lines,
                style_class="implementationType",
                fill_color="#f4f4f4",
                shape="class",
            )
        )

    for compu_name in sorted(referenced_compu_methods):
        compu = compu_methods[compu_name]
        body_lines = [f"category: {compu.category}"]
        if compu.category == "textTable":
            body_lines.extend(f"{entry.value} = {entry.label}" for entry in compu.entries)
            shape = "enum"
            stereotype = "enumLike"
        else:
            if compu.factor is not None or compu.offset is not None:
                body_lines.append(f"scale: {compu.factor or 0}x + {compu.offset or 0}")
            shape = "class"
            stereotype = "compuMethod"
        entities.append(
            InterfaceEntityView(
                id=_node_id("compu", compu.name),
                name=compu.name,
                stereotype=stereotype,
                layer="compu_methods",
                body_lines=body_lines,
                style_class="compuMethod",
                fill_color="#fde9d9",
                shape=shape,
            )
        )

    for group_name in sorted(referenced_mode_groups):
        group = mode_groups[group_name]
        body_lines = [f"initial: {group.initialMode}"]
        body_lines.extend(mode.name for mode in group.modes)
        entities.append(
            InterfaceEntityView(
                id=_node_id("mode", group.name),
                name=group.name,
                stereotype="modeDeclarationGroup",
                layer="mode_groups",
                body_lines=body_lines,
                style_class="modeGroup",
                fill_color="#eadcf8",
                shape="enum",
            )
        )

    entities = sorted(entities, key=lambda entity: (entity.name, entity.stereotype))
    layers = _build_interface_layers(entities)
    relations = sorted(relations, key=lambda relation: (relation.source_id, relation.target_id, relation.label))
    return InterfaceDiagramView(entities=entities, layers=layers, relations=relations)


def _runnable_metadata_lines(swc: Swc, runnable_name: str) -> List[str]:
    runnable = next(r for r in swc.runnables if r.name == runnable_name)
    if runnable.initEvent:
        return ["(init)"]
    if runnable.timingEventMs is not None:
        return [f"(cyclic, {runnable.timingEventMs} ms)"]
    if runnable.modeSwitchEvents:
        event = sorted(runnable.modeSwitchEvents, key=lambda item: (item.port, item.mode))[0]
        return [f"(mode, {event.port}: {event.mode})"]
    if runnable.dataReceiveEvents:
        event = sorted(runnable.dataReceiveEvents, key=lambda item: (item.port, item.dataElement))[0]
        return [f"(receive, {event.port}: {event.dataElement})"]
    if runnable.operationInvokedEvents:
        event = sorted(runnable.operationInvokedEvents, key=lambda item: (item.port, item.operation))[0]
        return [f"(invoked, {event.port}: {event.operation})"]
    return []


def _behavior_edge(
    source_id: str,
    target_id: str,
    label: str,
    style_class: str,
) -> BehaviorEdgeView:
    return BehaviorEdgeView(source_id=source_id, target_id=target_id, label=label, style_class=style_class)


def _build_behavior_view(swc: Swc) -> BehaviorDiagramView:
    ports: List[BehaviorPortView] = []
    port_map: Dict[str, BehaviorPortView] = {}
    for port in swc.ports:
        kind_label, style_class, fill_color = _port_style(port)
        port_view = BehaviorPortView(
            id=_node_id("port", swc.name, port.name),
            name=port.name,
            kind_label=kind_label,
            interface_name=port.interfaceRef,
            extra_label=_port_extra_label(port),
            style_class=style_class,
            fill_color=fill_color,
        )
        ports.append(port_view)
        port_map[port.name] = port_view

    runnables = [
        BehaviorRunnableView(
            id=_node_id("run", swc.name, runnable.name),
            name=runnable.name,
            metadata_lines=_runnable_metadata_lines(swc, runnable.name),
        )
        for runnable in swc.runnables
    ]
    runnable_map = {runnable.name: runnable for runnable in runnables}
    source_port_names: set[str] = set()
    sink_port_names: set[str] = set()

    edges: List[BehaviorEdgeView] = []
    for runnable in swc.runnables:
        runnable_id = runnable_map[runnable.name].id
        for read in runnable.reads:
            source_port_names.add(read.port)
            edges.append(
                _behavior_edge(
                    port_map[read.port].id,
                    runnable_id,
                    f"read {read.dataElement}",
                    "readEdge",
                )
            )
        for event in runnable.dataReceiveEvents:
            source_port_names.add(event.port)
            edges.append(
                _behavior_edge(
                    port_map[event.port].id,
                    runnable_id,
                    f"receive {event.dataElement}",
                    "eventEdge",
                )
            )
        for call in runnable.calls:
            source_port_names.add(call.port)
            edges.append(
                _behavior_edge(
                    port_map[call.port].id,
                    runnable_id,
                    f"call {call.operation}",
                    "callEdge",
                )
            )
        for event in runnable.operationInvokedEvents:
            source_port_names.add(event.port)
            edges.append(
                _behavior_edge(
                    port_map[event.port].id,
                    runnable_id,
                    "",
                    "eventEdge",
                )
            )
        for event in runnable.modeSwitchEvents:
            source_port_names.add(event.port)
            edges.append(
                _behavior_edge(
                    port_map[event.port].id,
                    runnable_id,
                    "",
                    "modeEdge",
                )
            )
        for write in runnable.writes:
            sink_port_names.add(write.port)
            edges.append(
                _behavior_edge(
                    runnable_id,
                    port_map[write.port].id,
                    f"write {write.dataElement}",
                    "writeEdge",
                )
            )

    edges = sorted(edges, key=lambda edge: (edge.source_id, edge.target_id, edge.label))
    incoming_ports: List[BehaviorPortView] = []
    outgoing_ports: List[BehaviorPortView] = []
    for port in ports:
        if port.name in source_port_names and port.name not in sink_port_names:
            incoming_ports.append(port)
        elif port.name in sink_port_names and port.name not in source_port_names:
            outgoing_ports.append(port)
        elif port.name in source_port_names and port.name in sink_port_names:
            if "provides" in port.kind_label:
                outgoing_ports.append(port)
            else:
                incoming_ports.append(port)
        elif "requires" in port.kind_label:
            incoming_ports.append(port)
        else:
            outgoing_ports.append(port)

    runnable_columns = _behavior_runnable_grid_columns(len(runnables))
    runnable_rows = [
        BehaviorRunnableRowView(
            id=_node_id("runnable_row", swc.name, str(row_index + 1)),
            runnables=runnables[row_index : row_index + runnable_columns],
        )
        for row_index in range(0, len(runnables), runnable_columns)
    ]

    return BehaviorDiagramView(
        swc_name=swc.name,
        swc_type_label=_swc_category_label(swc.category),
        swc_fill_color=_swc_fill_color(swc.category),
        incoming_ports=incoming_ports,
        outgoing_ports=outgoing_ports,
        runnable_columns=runnable_columns,
        runnable_rows=runnable_rows,
        runnables=runnables,
        edges=edges,
    )


def _behavior_runnable_grid_columns(runnable_count: int) -> int:
    if runnable_count <= 4:
        return max(1, runnable_count)
    if runnable_count <= 8:
        return 2
    return 3


def build_diagram_views(project: Project) -> DiagramBuild:
    project = _sort_project_for_export(project)
    return DiagramBuild(
        composition=_build_composition_view(project),
        interfaces=_build_interface_view(project),
        behaviors=[_build_behavior_view(swc) for swc in project.swcs],
    )


def _render_template(env: Environment, template_name: str, **context: object) -> str:
    return env.get_template(template_name).render(**context)


def _behavior_filename(swc_name: str, extension: str) -> str:
    return f"behavior_{_safe_filename_stem(swc_name, 'swc')}{extension}"


def _composition_filename(system_name: str, extension: str) -> str:
    return f"composition_{_safe_filename_stem(system_name, 'system')}{extension}"


def write_diagram_outputs(project: Project, template_dir: Path, out: Path, fmt: DiagramFormat) -> List[DiagramOutputArtifact]:
    backend = BACKENDS[fmt]
    env = _env(template_dir)
    views = build_diagram_views(project)
    out.mkdir(parents=True, exist_ok=True)

    rendered: List[tuple[Path, str]] = [
        (
            out / _composition_filename(views.composition.system_name, backend.extension),
            _render_template(env, backend.composition_template, view=views.composition),
        ),
        (out / f"interfaces{backend.extension}", _render_template(env, backend.interfaces_template, view=views.interfaces)),
    ]

    for behavior in views.behaviors:
        rendered.append(
            (
                out / _behavior_filename(behavior.swc_name, backend.extension),
                _render_template(env, backend.behavior_template, view=behavior),
            )
        )

    artifacts: List[DiagramOutputArtifact] = []
    for path, content in rendered:
        path.write_text(content, encoding="utf-8")
        artifacts.append(DiagramOutputArtifact(path=path, size_bytes=path.stat().st_size))
    return artifacts
