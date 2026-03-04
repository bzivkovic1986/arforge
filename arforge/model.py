from __future__ import annotations

from dataclasses import dataclass
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
    from_swc: str
    from_port: str
    to_swc: str
    to_port: str
    dataElement: str | None = None
    operation: str | None = None

@dataclass(frozen=True)
class Project:
    autosar_version: str
    rootPackage: str
    datatypes: List[DataType]
    interfaces: List[Interface]
    swcs: List[Swc]
    connections: List[Connection]

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
        runs = [Runnable(**r) for r in s.get("runnables", [])]
        ports: List[Port] = []
        for p in s.get("ports", []):
            it_name = p["interfaceRef"]
            it = iface_by_name.get(it_name)
            # interfaceType is used by templates; unknown handled by validation layer
            interfaceType = it.type if it else "senderReceiver"
            ports.append(Port(name=p["name"], direction=p["direction"], interfaceRef=it_name, interfaceType=interfaceType))
        swcs.append(Swc(name=s["name"], runnables=runs, ports=ports))

    conns: List[Connection] = []
    for c in d.get("connections", []):
        fs, fp = _split_endpoint(c["from"])
        ts, tp = _split_endpoint(c["to"])
        conns.append(Connection(
            from_swc=fs, from_port=fp, to_swc=ts, to_port=tp,
            dataElement=c.get("dataElement"), operation=c.get("operation")
        ))

    return Project(
        autosar_version=autosar["version"],
        rootPackage=autosar["rootPackage"],
        datatypes=dts,
        interfaces=ifaces,
        swcs=swcs,
        connections=conns,
    )
