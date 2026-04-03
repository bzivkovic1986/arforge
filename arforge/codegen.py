from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from .exporter import _sort_project_for_export
from .model import DataElement, Interface, Operation, Project, Swc


HEADER_TEMPLATE_C = "code/c/swc.h.j2"
SOURCE_TEMPLATE_C = "code/c/swc.c.j2"


@dataclass(frozen=True)
class CodegenBackend:
    language: str
    header_template: str
    source_template: str


BACKENDS: Dict[str, CodegenBackend] = {
    "c": CodegenBackend(
        language="c",
        header_template=HEADER_TEMPLATE_C,
        source_template=SOURCE_TEMPLATE_C,
    )
}


def supported_languages() -> List[str]:
    return sorted(BACKENDS.keys())


def _env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _safe_identifier(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", value)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if not sanitized:
        return "value"
    if sanitized[0].isdigit():
        sanitized = f"v_{sanitized}"
    return sanitized


def _snake_case(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", value)
    sanitized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized.lower() or "value"


def _header_guard(swc_name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", swc_name).upper()
    stem = re.sub(r"_+", "_", stem).strip("_")
    return f"ARFORGE_{stem}_H"


class CTypeResolver:
    def __init__(self, project: Project):
        self._base_types = {base_type.name: base_type for base_type in project.baseTypes}
        self._implementation_types = {
            implementation_type.name: implementation_type
            for implementation_type in project.implementationDataTypes
        }
        self._application_types = {
            application_type.name: application_type
            for application_type in project.applicationDataTypes
        }

    def resolve(self, type_ref: str) -> Optional[str]:
        if type_ref == "void":
            return "void"

        base_type = self._base_types.get(type_ref)
        if base_type is not None:
            return base_type.nativeDeclaration or base_type.name

        implementation_type = self._implementation_types.get(type_ref)
        if implementation_type is not None:
            if implementation_type.baseTypeRef:
                return self.resolve(implementation_type.baseTypeRef)
            return None

        application_type = self._application_types.get(type_ref)
        if application_type is not None:
            return self.resolve(application_type.implementationTypeRef)

        return None


def _local_initializer(c_type: str) -> str:
    if c_type in {"float", "double"}:
        return "0.0"
    return "0"


def _variable_spec(type_resolver: CTypeResolver, *, type_ref: str, name: str) -> dict[str, object]:
    c_type = type_resolver.resolve(type_ref)
    variable_name = _safe_identifier(name)
    if c_type is None:
        return {
            "name": variable_name,
            "c_type": None,
            "type_ref": type_ref,
            "initializer": None,
            "todo": f"TODO: map {type_ref} to a target C type for {variable_name}.",
        }

    return {
        "name": variable_name,
        "c_type": c_type,
        "type_ref": type_ref,
        "initializer": _local_initializer(c_type),
        "todo": None,
    }


def _format_operation_signature(operation: Optional[Operation], type_resolver: CTypeResolver) -> Optional[str]:
    if operation is None:
        return None

    resolved_return = type_resolver.resolve(operation.returnType) or operation.returnType
    args: list[str] = []
    for argument in operation.arguments:
        resolved_type = type_resolver.resolve(argument.typeRef) or argument.typeRef
        rendered_type = resolved_type
        if argument.direction in {"out", "inout"}:
            rendered_type = f"{rendered_type}*"
        args.append(f"{rendered_type} {argument.name}")
    joined_args = ", ".join(args) if args else "void"
    return f"{resolved_return} {operation.name}({joined_args})"


def _lookup_data_element(interface: Optional[Interface], data_element_name: str) -> Optional[DataElement]:
    if interface is None or interface.dataElements is None:
        return None
    return next((data_element for data_element in interface.dataElements if data_element.name == data_element_name), None)


def _lookup_operation(interface: Optional[Interface], operation_name: str) -> Optional[Operation]:
    if interface is None or interface.operations is None:
        return None
    return next((operation for operation in interface.operations if operation.name == operation_name), None)


def _build_runnable_model(
    runnable,
    port_by_name: dict[str, object],
    interface_by_name: dict[str, Interface],
    type_resolver: CTypeResolver,
) -> dict[str, object]:
    trigger_lines: list[str] = []
    if runnable.initEvent:
        trigger_lines.append("Trigger: InitEvent")
    if runnable.timingEventMs is not None:
        trigger_lines.append(f"Trigger: TimingEvent({runnable.timingEventMs} ms)")
    for event in runnable.dataReceiveEvents:
        trigger_lines.append(f"Trigger: DataReceiveEvent({event.port}.{event.dataElement})")
    for event in runnable.modeSwitchEvents:
        trigger_lines.append(f"Trigger: ModeSwitchEvent({event.port} -> {event.mode})")
    for event in runnable.operationInvokedEvents:
        trigger_lines.append(f"Trigger: OperationInvokedEvent({event.port}.{event.operation})")

    read_entries: list[dict[str, object]] = []
    for access in runnable.reads:
        port = port_by_name.get(access.port)
        interface = interface_by_name.get(port.interfaceRef) if port is not None else None
        data_element = _lookup_data_element(interface, access.dataElement)
        variable = _variable_spec(
            type_resolver,
            type_ref=data_element.typeRef if data_element is not None else "TODO_TYPE",
            name=f"{_snake_case(access.port)}_{_snake_case(access.dataElement)}",
        )
        read_entries.append(
            {
                "port": access.port,
                "data_element": access.dataElement,
                "variable": variable,
                "rte_api": f"Rte_Read_{access.port}_{access.dataElement}",
                "description": f"Read from {access.port}.{access.dataElement}.",
            }
        )

    write_entries: list[dict[str, object]] = []
    for access in runnable.writes:
        port = port_by_name.get(access.port)
        interface = interface_by_name.get(port.interfaceRef) if port is not None else None
        data_element = _lookup_data_element(interface, access.dataElement)
        variable = _variable_spec(
            type_resolver,
            type_ref=data_element.typeRef if data_element is not None else "TODO_TYPE",
            name=f"{_snake_case(access.port)}_{_snake_case(access.dataElement)}",
        )
        write_entries.append(
            {
                "port": access.port,
                "data_element": access.dataElement,
                "variable": variable,
                "rte_api": f"Rte_Write_{access.port}_{access.dataElement}",
                "description": f"Write to {access.port}.{access.dataElement}.",
            }
        )

    call_entries: list[dict[str, object]] = []
    for call in runnable.calls:
        port = port_by_name.get(call.port)
        interface = interface_by_name.get(port.interfaceRef) if port is not None else None
        operation = _lookup_operation(interface, call.operation)
        arguments: list[dict[str, object]] = []
        for argument in operation.arguments if operation is not None else []:
            variable = _variable_spec(
                type_resolver,
                type_ref=argument.typeRef,
                name=f"{_snake_case(call.operation)}_{_snake_case(argument.name)}",
            )
            arguments.append(
                {
                    "name": argument.name,
                    "direction": argument.direction,
                    "variable": variable,
                    "call_expr": f"&{variable['name']}" if argument.direction in {"out", "inout"} else variable["name"],
                }
            )

        return_variable = None
        return_assignment = ""
        if operation is not None and operation.returnType != "void":
            return_variable = _variable_spec(
                type_resolver,
                type_ref=operation.returnType,
                name=f"{_snake_case(call.operation)}_result",
            )
            return_assignment = f"{return_variable['name']} = "

        call_args = ", ".join(argument["call_expr"] for argument in arguments)
        call_entries.append(
            {
                "port": call.port,
                "operation": call.operation,
                "timeout_ms": call.timeoutMs,
                "rte_api": f"Rte_Call_{call.port}_{call.operation}",
                "arguments": arguments,
                "return_variable": return_variable,
                "rendered_call": f"{return_assignment}Rte_Call_{call.port}_{call.operation}({call_args})",
                "operation_signature": _format_operation_signature(operation, type_resolver),
            }
        )

    server_bindings: list[dict[str, object]] = []
    for event in runnable.operationInvokedEvents:
        port = port_by_name.get(event.port)
        interface = interface_by_name.get(port.interfaceRef) if port is not None else None
        operation = _lookup_operation(interface, event.operation)
        server_bindings.append(
            {
                "port": event.port,
                "operation": event.operation,
                "operation_signature": _format_operation_signature(operation, type_resolver),
            }
        )

    has_body_content = any(
        [
            runnable.description,
            read_entries,
            write_entries,
            call_entries,
            runnable.modeSwitchEvents,
            server_bindings,
            runnable.raisesErrors,
        ]
    )

    return {
        "name": runnable.name,
        "description": runnable.description,
        "trigger_lines": trigger_lines,
        "has_mode_switch_events": bool(runnable.modeSwitchEvents),
        "reads": read_entries,
        "writes": write_entries,
        "calls": call_entries,
        "server_bindings": server_bindings,
        "raises_errors": [
            {
                "operation": raised_error.operation,
                "error": raised_error.error,
            }
            for raised_error in runnable.raisesErrors
        ],
        "has_body_content": has_body_content,
    }


def _build_swc_code_model(project: Project, swc: Swc) -> dict[str, object]:
    interface_by_name = {interface.name: interface for interface in project.interfaces}
    port_by_name = {port.name: port for port in swc.ports}
    type_resolver = CTypeResolver(project)
    runnable_models = [
        _build_runnable_model(runnable, port_by_name, interface_by_name, type_resolver)
        for runnable in swc.runnables
    ]
    return {
        "name": swc.name,
        "category": swc.category,
        "header_guard": _header_guard(swc.name),
        "header_filename": f"{swc.name}.h",
        "source_filename": f"{swc.name}.c",
        "runnables": runnable_models,
    }


def _render_swc_files(project: Project, swc: Swc, template_dir: Path, backend: CodegenBackend) -> dict[Path, str]:
    env = _env(template_dir)
    swc_model = _build_swc_code_model(project, swc)
    header_template = env.get_template(backend.header_template)
    source_template = env.get_template(backend.source_template)
    return {
        Path(swc_model["header_filename"]): header_template.render(swc=swc_model, language=backend.language),
        Path(swc_model["source_filename"]): source_template.render(swc=swc_model, language=backend.language),
    }


def write_code_outputs(project: Project, template_dir: Path, out: Path, *, lang: str = "c") -> List[Path]:
    backend = BACKENDS.get(lang)
    if backend is None:
        raise ValueError(f"Unsupported code generation language: {lang}")

    project = _sort_project_for_export(project)
    out.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for swc in project.swcs:
        rendered = _render_swc_files(project, swc, template_dir, backend)
        for rel_path in [Path(f"{swc.name}.h"), Path(f"{swc.name}.c")]:
            target = out / rel_path
            target.write_text(rendered[rel_path], encoding="utf-8")
            written.append(target)
    return written
