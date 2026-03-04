from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

@dataclass(frozen=True)
class DataType:
    name: str
    category: str
    baseType: str | None = None

@dataclass(frozen=True)
class DataElement:
    name: str
    typeRef: str

@dataclass(frozen=True)
class Operation:
    name: str

@dataclass(frozen=True)
class Interface:
    name: str
    type: str  # senderReceiver | clientServer
    dataElements: List[DataElement] | None = None
    operations: List[Operation] | None = None

@dataclass(frozen=True)
class Runnable:
    name: str
    timingEventMs: int
    reads: List["SrAccess"] = field(default_factory=list)
    writes: List["SrAccess"] = field(default_factory=list)
    calls: List["CsCall"] = field(default_factory=list)


@dataclass(frozen=True)
class SrAccess:
    port: str
    dataElement: str


@dataclass(frozen=True)
class CsCall:
    port: str
    operation: str

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
    datatypes: List[DataType]
    interfaces: List[Interface]
    swcs: List[Swc]
    system: System

    @property
    def connections(self) -> List[Connection]:
        return self.system.connections

def _split_endpoint(ep: str) -> Tuple[str, str]:
    swc, port = ep.split(".", 1)
    return swc, port

def from_dict(d: Dict[str, Any]) -> Project:
    autosar = d["autosar"]
    dts = [DataType(**dt) for dt in d.get("datatypes", [])]

    ifaces: List[Interface] = []
    for itf in d.get("interfaces", []):
        if itf["type"] == "senderReceiver":
            des = [DataElement(**de) for de in itf.get("dataElements", [])]
            ifaces.append(Interface(name=itf["name"], type=itf["type"], dataElements=des, operations=None))
        else:
            ops = [Operation(**op) for op in itf.get("operations", [])]
            ifaces.append(Interface(name=itf["name"], type=itf["type"], dataElements=None, operations=ops))

    iface_by_name = {i.name: i for i in ifaces}

    swcs: List[Swc] = []
    for s in d.get("swcs", []):
        runs = [
            Runnable(
                name=r["name"],
                timingEventMs=r["timingEventMs"],
                reads=[SrAccess(**acc) for acc in r.get("reads", [])],
                writes=[SrAccess(**acc) for acc in r.get("writes", [])],
                calls=[CsCall(**acc) for acc in r.get("calls", [])],
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
        datatypes=dts,
        interfaces=ifaces,
        swcs=swcs,
        system=system,
    )
