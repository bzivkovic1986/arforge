from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

@dataclass(frozen=True)
class BaseType:
    name: str


@dataclass(frozen=True)
class ImplementationField:
    name: str
    typeRef: str


@dataclass(frozen=True)
class ImplementationDataType:
    name: str
    baseTypeRef: str | None = None
    kind: str | None = None
    fields: List[ImplementationField] = field(default_factory=list)

    @property
    def is_struct(self) -> bool:
        return bool(self.fields) or self.kind == "struct"


@dataclass(frozen=True)
class ApplicationDataType:
    name: str
    implementationTypeRef: str
    constraint: "ConstraintRange | None" = None
    unitRef: str | None = None
    compuMethodRef: str | None = None


@dataclass(frozen=True)
class ConstraintRange:
    min: float | int
    max: float | int


@dataclass(frozen=True)
class Unit:
    name: str
    displayName: str | None = None


@dataclass(frozen=True)
class TextTableEntry:
    value: int
    label: str


@dataclass(frozen=True)
class CompuMethod:
    name: str
    category: str
    unitRef: str | None = None
    factor: float | None = None
    offset: float | None = None
    physMin: float | None = None
    physMax: float | None = None
    entries: List[TextTableEntry] = field(default_factory=list)

@dataclass(frozen=True)
class DataElement:
    name: str
    typeRef: str

@dataclass(frozen=True)
class Operation:
    name: str
    arguments: List["OperationArgument"] = field(default_factory=list)
    returnType: str = "void"


@dataclass(frozen=True)
class OperationArgument:
    name: str
    direction: str
    typeRef: str

@dataclass(frozen=True)
class Interface:
    name: str
    type: str  # senderReceiver | clientServer
    dataElements: List[DataElement] | None = None
    operations: List[Operation] | None = None

@dataclass(frozen=True)
class Runnable:
    name: str
    timingEventMs: int | None = None
    reads: List["DataAccess"] = field(default_factory=list)
    writes: List["DataAccess"] = field(default_factory=list)
    calls: List["OperationCall"] = field(default_factory=list)
    operationInvokedEvents: List["OperationInvokedEvent"] = field(default_factory=list)


@dataclass(frozen=True)
class DataAccess:
    port: str
    dataElement: str


@dataclass(frozen=True)
class OperationCall:
    port: str
    operation: str


@dataclass(frozen=True)
class OperationInvokedEvent:
    port: str
    operation: str


# Backward-compatible aliases for earlier internal names.
SrAccess = DataAccess
CsCall = OperationCall

@dataclass(frozen=True)
class Port:
    name: str
    direction: str  # provides | requires
    interfaceRef: str
    interfaceType: str  # senderReceiver | clientServer

@dataclass(frozen=True)
class Swc:
    name: str
    runnables: List[Runnable]
    ports: List[Port]

@dataclass(frozen=True)
class Connection:
    from_instance: str
    from_port: str
    to_instance: str
    to_port: str
    dataElement: str | None = None
    operation: str | None = None

@dataclass(frozen=True)
class ComponentPrototype:
    name: str
    typeRef: str


@dataclass(frozen=True)
class Composition:
    name: str
    components: List[ComponentPrototype]
    connectors: List[Connection]


@dataclass(frozen=True)
class System:
    name: str
    composition: Composition

    @property
    def instances(self) -> List[ComponentPrototype]:
        return self.composition.components

    @property
    def connections(self) -> List[Connection]:
        return self.composition.connectors

@dataclass(frozen=True)
class Project:
    autosar_version: str
    rootPackage: str
    baseTypes: List[BaseType]
    implementationDataTypes: List[ImplementationDataType]
    applicationDataTypes: List[ApplicationDataType]
    units: List[Unit]
    compuMethods: List[CompuMethod]
    interfaces: List[Interface]
    swcs: List[Swc]
    system: System

    @property
    def datatypes(self) -> List[ImplementationDataType]:
        # Backward-compatibility alias used in parts of the codebase.
        return self.implementationDataTypes

    @property
    def connections(self) -> List[Connection]:
        return self.system.connections

def _split_endpoint(ep: str) -> Tuple[str, str]:
    swc, port = ep.split(".", 1)
    return swc, port

def from_dict(d: Dict[str, Any]) -> Project:
    autosar = d["autosar"]
    base_types = [BaseType(**bt) for bt in d.get("baseTypes", [])]
    impl_types = []
    for idt in d.get("implementationDataTypes", []):
        impl_types.append(
            ImplementationDataType(
                name=idt["name"],
                baseTypeRef=idt.get("baseTypeRef"),
                kind=idt.get("kind"),
                fields=[ImplementationField(**f) for f in idt.get("fields", [])],
            )
        )
    app_types = []
    for adt in d.get("applicationDataTypes", []):
        constraint_data = adt.get("constraint")
        constraint = ConstraintRange(**constraint_data) if constraint_data is not None else None
        app_types.append(
            ApplicationDataType(
                name=adt["name"],
                implementationTypeRef=adt["implementationTypeRef"],
                constraint=constraint,
                unitRef=adt.get("unitRef"),
                compuMethodRef=adt.get("compuMethodRef"),
            )
        )
    units = [Unit(**u) for u in d.get("units", [])]
    compu_methods = []
    for cm in d.get("compuMethods", []):
        compu_methods.append(
            CompuMethod(
                name=cm["name"],
                category=cm["category"],
                unitRef=cm.get("unitRef"),
                factor=cm.get("factor"),
                offset=cm.get("offset"),
                physMin=cm.get("physMin"),
                physMax=cm.get("physMax"),
                entries=[TextTableEntry(**entry) for entry in cm.get("entries", [])],
            )
        )

    ifaces: List[Interface] = []
    for itf in d.get("interfaces", []):
        if itf["type"] == "senderReceiver":
            des = [DataElement(**de) for de in itf.get("dataElements", [])]
            ifaces.append(Interface(name=itf["name"], type=itf["type"], dataElements=des, operations=None))
        else:
            ops = []
            for op in itf.get("operations", []):
                op_args = [OperationArgument(**arg) for arg in op.get("arguments", [])]
                ops.append(
                    Operation(
                        name=op["name"],
                        arguments=op_args,
                        returnType=op.get("returnType", "void"),
                    )
                )
            ifaces.append(Interface(name=itf["name"], type=itf["type"], dataElements=None, operations=ops))

    iface_by_name = {i.name: i for i in ifaces}

    swcs: List[Swc] = []
    for s in d.get("swcs", []):
        runs = [
            Runnable(
                name=r["name"],
                timingEventMs=r.get("timingEventMs"),
                reads=sorted(
                    [DataAccess(**acc) for acc in r.get("reads", [])],
                    key=lambda acc: (acc.port, acc.dataElement),
                ),
                writes=sorted(
                    [DataAccess(**acc) for acc in r.get("writes", [])],
                    key=lambda acc: (acc.port, acc.dataElement),
                ),
                calls=sorted(
                    [OperationCall(**acc) for acc in r.get("calls", [])],
                    key=lambda acc: (acc.port, acc.operation),
                ),
                operationInvokedEvents=sorted(
                    [OperationInvokedEvent(**e) for e in r.get("operationInvokedEvents", [])],
                    key=lambda e: (e.port, e.operation),
                ),
            )
            for r in s.get("runnables", [])
        ]
        ports: List[Port] = []
        for p in s.get("ports", []):
            it_name = p["interfaceRef"]
            it = iface_by_name.get(it_name)
            # interfaceType is used by templates; unknown handled by validation layer
            interfaceType = it.type if it else "senderReceiver"
            ports.append(Port(name=p["name"], direction=p["direction"], interfaceRef=it_name, interfaceType=interfaceType))
        swcs.append(Swc(name=s["name"], runnables=runs, ports=ports))

    system_data = d.get("system")
    if system_data:
        composition_data = system_data["composition"]
        instances = [ComponentPrototype(name=i["name"], typeRef=i["typeRef"]) for i in composition_data.get("components", [])]
        conns: List[Connection] = []
        for c in composition_data.get("connectors", []):
            fs, fp = _split_endpoint(c["from"])
            ts, tp = _split_endpoint(c["to"])
            conns.append(Connection(
                from_instance=fs, from_port=fp, to_instance=ts, to_port=tp,
                dataElement=c.get("dataElement"), operation=c.get("operation")
            ))
        composition = Composition(name=composition_data["name"], components=instances, connectors=conns)
        system = System(name=system_data["name"], composition=composition)
    else:
        # Backward-compatible mode: old connections.yaml where endpoint prefix is SWC type.
        conns = []
        for c in d.get("connections", []):
            fs, fp = _split_endpoint(c["from"])
            ts, tp = _split_endpoint(c["to"])
            conns.append(Connection(
                from_instance=fs, from_port=fp, to_instance=ts, to_port=tp,
                dataElement=c.get("dataElement"), operation=c.get("operation")
            ))
        instances = [ComponentPrototype(name=s.name, typeRef=s.name) for s in swcs]
        composition = Composition(name="Composition_System1", components=instances, connectors=conns)
        system = System(name="System1", composition=composition)

    return Project(
        autosar_version=autosar["version"],
        rootPackage=autosar["rootPackage"],
        baseTypes=base_types,
        implementationDataTypes=impl_types,
        applicationDataTypes=app_types,
        units=units,
        compuMethods=compu_methods,
        interfaces=ifaces,
        swcs=swcs,
        system=system,
    )
