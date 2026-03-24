from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from .model import ComponentPrototype, Connection, Port, Project, Swc

class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


Severity = Literal["error", "warning", "info"]
CaseStatus = Literal["run", "skip"]
CaseOutcome = Literal["ok", "fail"]


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    severity: FindingSeverity | Severity = FindingSeverity.ERROR
    location: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", FindingSeverity(self.severity))


@dataclass(frozen=True)
class ValidationReport:
    ruleset: str
    case_results: List["CaseResult"]
    findings: List[Finding]

    def error_findings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == FindingSeverity.ERROR]

    def findings_with_severity(self, severity: FindingSeverity | Severity) -> List[Finding]:
        normalized = FindingSeverity(severity)
        return [f for f in self.findings if f.severity == normalized]

    def severity_counts(self) -> Dict[str, int]:
        return {
            FindingSeverity.ERROR.value: len(self.findings_with_severity(FindingSeverity.ERROR)),
            FindingSeverity.WARNING.value: len(self.findings_with_severity(FindingSeverity.WARNING)),
            FindingSeverity.INFO.value: len(self.findings_with_severity(FindingSeverity.INFO)),
        }

    def as_dict(self) -> Dict[str, object]:
        # This keeps a machine-readable report shape ready for future CLI output.
        return {
            "ruleset": self.ruleset,
            "summary": self.severity_counts(),
            "cases": [
                {
                    "case_id": c.case_id,
                    "name": c.name,
                    "description": c.description,
                    "status": c.status,
                    "outcome": c.outcome,
                    "reason": c.reason,
                    "duration_ms": c.duration_ms,
                    "finding_count": c.finding_count,
                }
                for c in self.case_results
            ],
            "findings": [
                {
                    "code": f.code,
                    "severity": f.severity.value,
                    "message": f.message,
                    "location": f.location,
                }
                for f in self.findings
            ],
        }


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    name: str
    description: str
    status: CaseStatus
    outcome: Optional[CaseOutcome]
    reason: Optional[str]
    duration_ms: float
    finding_count: int
    findings: List[Finding]


@dataclass(frozen=True)
class InstancePortConnectivity:
    instance_name: str
    swc_name: str
    port: Port
    incoming_connectors: Tuple[Connection, ...]
    outgoing_connectors: Tuple[Connection, ...]

    @property
    def endpoint_key(self) -> Tuple[str, str]:
        return (self.instance_name, self.port.name)

    @property
    def is_connected(self) -> bool:
        return bool(self.incoming_connectors or self.outgoing_connectors)


@dataclass(frozen=True)
class SwcPortUsage:
    swc_name: str
    port_name: str
    reads: Tuple[Tuple[str, str], ...] = ()
    writes: Tuple[Tuple[str, str], ...] = ()
    calls: Tuple[Tuple[str, str], ...] = ()
    data_receive_events: Tuple[Tuple[str, str], ...] = ()
    mode_switch_events: Tuple[Tuple[str, str], ...] = ()
    operation_invoked_events: Tuple[Tuple[str, str], ...] = ()
    raises_errors: Tuple[Tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class DeclaredPortUsage:
    swc_name: str
    port: Port
    usage: SwcPortUsage


@dataclass(frozen=True)
class SrTimingCommunication:
    provider_swc_name: str
    provider_port_name: str
    provider_runnable_name: str
    consumer_swc_name: str
    consumer_port_name: str
    consumer_runnable_name: str
    data_element: str
    producer_period_ms: int
    consumer_period_ms: int


class ValidationContext:
    def __init__(self, project: Project):
        self.project = project
        self.base_type_by_name = {d.name: d for d in project.baseTypes}
        self.implementation_type_by_name = {d.name: d for d in project.implementationDataTypes}
        self.application_type_by_name = {d.name: d for d in project.applicationDataTypes}
        self.unit_by_name = {u.name: u for u in project.units}
        self.compu_method_by_name = {c.name: c for c in project.compuMethods}
        self.mode_declaration_group_by_name = {g.name: g for g in project.modeDeclarationGroups}
        self.declared_mode_declaration_groups = tuple(
            sorted(group.name for group in project.modeDeclarationGroups)
        )
        self.referenced_mode_declaration_groups = tuple(
            sorted(
                {
                    interface.modeGroupRef
                    for interface in project.interfaces
                    if interface.type == "modeSwitch" and interface.modeGroupRef
                }
            )
        )
        self.datatype_by_name = {**self.base_type_by_name, **self.implementation_type_by_name, **self.application_type_by_name}
        self.iface_by_name = {i.name: i for i in project.interfaces}
        self.swc_by_name = {s.name: s for s in project.swcs}
        self.instance_by_name = {i.name: i for i in project.system.composition.components}
        self.instances_by_swc_name: Dict[str, List[ComponentPrototype]] = {}
        for instance in sorted(project.system.composition.components, key=lambda c: (c.typeRef, c.name)):
            self.instances_by_swc_name.setdefault(instance.typeRef, []).append(instance)

        self.ports_by_swc: Dict[str, Dict[str, Port]] = {
            swc.name: {p.name: p for p in swc.ports} for swc in project.swcs
        }
        self.runnable_by_swc: Dict[str, Dict[str, object]] = {
            swc.name: {runnable.name: runnable for runnable in swc.runnables}
            for swc in project.swcs
        }
        self.sr_data_elements_by_iface: Dict[str, set[str]] = {
            itf.name: {de.name for de in (itf.dataElements or [])}
            for itf in project.interfaces
            if itf.type == "senderReceiver"
        }
        self.cs_operations_by_iface: Dict[str, set[str]] = {
            itf.name: {op.name for op in (itf.operations or [])}
            for itf in project.interfaces
            if itf.type == "clientServer"
        }
        self.connectors_by_port_pair: Dict[tuple[str, str, str, str], List[Connection]] = {}
        self.outgoing_connectors_by_endpoint: Dict[tuple[str, str], List[Connection]] = {}
        self.incoming_connectors_by_endpoint: Dict[tuple[str, str], List[Connection]] = {}
        for connector in project.system.composition.connectors:
            self.connectors_by_port_pair.setdefault(connector.port_pair_key, []).append(connector)
            self.outgoing_connectors_by_endpoint.setdefault(
                (connector.from_instance, connector.from_port),
                [],
            ).append(connector)
            self.incoming_connectors_by_endpoint.setdefault(
                (connector.to_instance, connector.to_port),
                [],
            ).append(connector)

        self.instantiated_port_connections: Dict[tuple[str, str], InstancePortConnectivity] = {}
        self.instantiated_port_connections_by_interface_type: Dict[str, List[InstancePortConnectivity]] = {}
        for instance in sorted(project.system.composition.components, key=lambda c: (c.name, c.typeRef)):
            swc = self.swc_by_name.get(instance.typeRef)
            if swc is None:
                continue
            for port in sorted(swc.ports, key=lambda p: p.name):
                endpoint = (instance.name, port.name)
                connectivity = InstancePortConnectivity(
                    instance_name=instance.name,
                    swc_name=swc.name,
                    port=port,
                    incoming_connectors=tuple(self.incoming_connectors_by_endpoint.get(endpoint, [])),
                    outgoing_connectors=tuple(self.outgoing_connectors_by_endpoint.get(endpoint, [])),
                )
                self.instantiated_port_connections[endpoint] = connectivity
                self.instantiated_port_connections_by_interface_type.setdefault(port.interfaceType, []).append(connectivity)

        swc_port_usage: Dict[tuple[str, str], Dict[str, List[tuple[str, ...]]]] = {}
        for swc in sorted(project.swcs, key=lambda s: s.name):
            for runnable in sorted(swc.runnables, key=lambda r: r.name):
                for read in sorted(runnable.reads, key=lambda a: (a.port, a.dataElement)):
                    swc_port_usage.setdefault((swc.name, read.port), {}).setdefault("reads", []).append(
                        (runnable.name, read.dataElement)
                    )
                for write in sorted(runnable.writes, key=lambda a: (a.port, a.dataElement)):
                    swc_port_usage.setdefault((swc.name, write.port), {}).setdefault("writes", []).append(
                        (runnable.name, write.dataElement)
                    )
                for call in sorted(runnable.calls, key=lambda a: (a.port, a.operation)):
                    swc_port_usage.setdefault((swc.name, call.port), {}).setdefault("calls", []).append(
                        (runnable.name, call.operation)
                    )
                for event in sorted(runnable.dataReceiveEvents, key=lambda e: (e.port, e.dataElement)):
                    swc_port_usage.setdefault((swc.name, event.port), {}).setdefault("data_receive_events", []).append(
                        (runnable.name, event.dataElement)
                    )
                for event in sorted(runnable.modeSwitchEvents, key=lambda e: (e.port, e.mode)):
                    swc_port_usage.setdefault((swc.name, event.port), {}).setdefault("mode_switch_events", []).append(
                        (runnable.name, event.mode)
                    )
                for event in sorted(runnable.operationInvokedEvents, key=lambda e: (e.port, e.operation)):
                    swc_port_usage.setdefault((swc.name, event.port), {}).setdefault("operation_invoked_events", []).append(
                        (runnable.name, event.operation)
                    )

                oie_ports_by_operation: Dict[str, List[str]] = {}
                for event in sorted(runnable.operationInvokedEvents, key=lambda e: (e.operation, e.port)):
                    oie_ports_by_operation.setdefault(event.operation, []).append(event.port)
                for raised_error in sorted(runnable.raisesErrors, key=lambda e: (e.operation, e.error)):
                    for port_name in sorted(oie_ports_by_operation.get(raised_error.operation, [])):
                        swc_port_usage.setdefault((swc.name, port_name), {}).setdefault("raises_errors", []).append(
                            (runnable.name, raised_error.operation, raised_error.error)
                        )

        self.runnable_port_usage_by_swc_port: Dict[tuple[str, str], SwcPortUsage] = {}
        for key in sorted(swc_port_usage.keys()):
            usage = swc_port_usage[key]
            self.runnable_port_usage_by_swc_port[key] = SwcPortUsage(
                swc_name=key[0],
                port_name=key[1],
                reads=tuple(usage.get("reads", [])),
                writes=tuple(usage.get("writes", [])),
                calls=tuple(usage.get("calls", [])),
                data_receive_events=tuple(usage.get("data_receive_events", [])),
                mode_switch_events=tuple(usage.get("mode_switch_events", [])),
                operation_invoked_events=tuple(usage.get("operation_invoked_events", [])),
                raises_errors=tuple(usage.get("raises_errors", [])),
            )
        self.declared_port_usage_by_swc: Dict[str, Tuple[DeclaredPortUsage, ...]] = {}
        for swc in sorted(project.swcs, key=lambda s: s.name):
            declared_usage: List[DeclaredPortUsage] = []
            for port in sorted(swc.ports, key=lambda p: p.name):
                usage = self.runnable_port_usage_by_swc_port.get(
                    (swc.name, port.name),
                    SwcPortUsage(swc_name=swc.name, port_name=port.name),
                )
                declared_usage.append(
                    DeclaredPortUsage(
                        swc_name=swc.name,
                        port=port,
                        usage=usage,
                    )
                )
            self.declared_port_usage_by_swc[swc.name] = tuple(declared_usage)
        self.sr_timing_communications = tuple(self._build_sr_timing_communications())

    def find_swc_port(self, swc_name: str, port_name: str) -> Optional[Port]:
        return self.ports_by_swc.get(swc_name, {}).get(port_name)

    def find_instance_swc(self, instance_name: str) -> Optional[Swc]:
        instance = self.instance_by_name.get(instance_name)
        if instance is None:
            return None
        return self.swc_by_name.get(instance.typeRef)

    def find_instance_port_connectivity(self, instance_name: str, port_name: str) -> Optional[InstancePortConnectivity]:
        return self.instantiated_port_connections.get((instance_name, port_name))

    def find_swc_port_usage(self, swc_name: str, port_name: str) -> SwcPortUsage:
        return self.runnable_port_usage_by_swc_port.get(
            (swc_name, port_name),
            SwcPortUsage(swc_name=swc_name, port_name=port_name),
        )

    def iter_declared_port_usage(self, swc_name: str) -> Tuple[DeclaredPortUsage, ...]:
        return self.declared_port_usage_by_swc.get(swc_name, ())

    def _build_sr_timing_communications(self) -> List[SrTimingCommunication]:
        communications: List[SrTimingCommunication] = []
        seen: set[tuple[str, str, str, str, str, str, str, int, int]] = set()

        for connector in sorted(self.project.system.composition.connectors, key=_connection_sort_key):
            provider_swc = self.find_instance_swc(connector.from_instance)
            consumer_swc = self.find_instance_swc(connector.to_instance)
            if provider_swc is None or consumer_swc is None:
                continue

            provider_port = self.find_swc_port(provider_swc.name, connector.from_port)
            consumer_port = self.find_swc_port(consumer_swc.name, connector.to_port)
            if provider_port is None or consumer_port is None:
                continue
            if provider_port.interfaceType != "senderReceiver" or consumer_port.interfaceType != "senderReceiver":
                continue

            provider_accesses = []
            for runnable in sorted(provider_swc.runnables, key=lambda r: r.name):
                if not _is_pure_cyclic_runnable(runnable):
                    continue
                for access in sorted(runnable.writes, key=lambda a: (a.port, a.dataElement)):
                    if access.port == connector.from_port:
                        provider_accesses.append((runnable, access.dataElement))

            consumer_accesses = []
            for runnable in sorted(consumer_swc.runnables, key=lambda r: r.name):
                if not _is_pure_cyclic_runnable(runnable):
                    continue
                for access in sorted(runnable.reads, key=lambda a: (a.port, a.dataElement)):
                    if access.port == connector.to_port:
                        consumer_accesses.append((runnable, access.dataElement))

            for provider_runnable, data_element in provider_accesses:
                for consumer_runnable, consumer_data_element in consumer_accesses:
                    if consumer_data_element != data_element:
                        continue

                    producer_period_ms = provider_runnable.timingEventMs
                    consumer_period_ms = consumer_runnable.timingEventMs
                    if producer_period_ms is None or consumer_period_ms is None:
                        continue

                    identity = (
                        provider_swc.name,
                        connector.from_port,
                        provider_runnable.name,
                        consumer_swc.name,
                        connector.to_port,
                        consumer_runnable.name,
                        data_element,
                        producer_period_ms,
                        consumer_period_ms,
                    )
                    if identity in seen:
                        continue
                    seen.add(identity)
                    communications.append(
                        SrTimingCommunication(
                            provider_swc_name=provider_swc.name,
                            provider_port_name=connector.from_port,
                            provider_runnable_name=provider_runnable.name,
                            consumer_swc_name=consumer_swc.name,
                            consumer_port_name=connector.to_port,
                            consumer_runnable_name=consumer_runnable.name,
                            data_element=data_element,
                            producer_period_ms=producer_period_ms,
                            consumer_period_ms=consumer_period_ms,
                        )
                    )

        return communications


def _connection_sort_key(connector: Connection) -> tuple[str, str, str, str, str, str]:
    return (
        connector.from_instance,
        connector.from_port,
        connector.to_instance,
        connector.to_port,
        connector.dataElement or "",
        connector.operation or "",
    )


def _is_pure_cyclic_runnable(runnable) -> bool:
    return (
        runnable.timingEventMs is not None
        and not runnable.operationInvokedEvents
        and not runnable.dataReceiveEvents
        and not runnable.modeSwitchEvents
        and not runnable.initEvent
    )


class ValidationCase(ABC):
    case_id: str = ""
    name: str = ""
    description: str = ""
    tags: Tuple[str, ...] = ()
    default_severity: Severity = "error"

    @abstractmethod
    def run(self, ctx: ValidationContext) -> List[Finding]:
        raise NotImplementedError

    def applicability(self, ctx: ValidationContext) -> Tuple[bool, Optional[str]]:
        return True, None

    def finding(
        self,
        message: str,
        *,
        location: Optional[str] = None,
        code: Optional[str] = None,
        severity: Optional[Severity] = None,
    ) -> Finding:
        return Finding(
            code=code or self.case_id,
            severity=severity or self.default_severity,
            message=message,
            location=location,
        )


class ValidationRunner:
    def __init__(self, cases: Sequence[ValidationCase]):
        self.cases = list(cases)

    def run_report(self, ctx: ValidationContext, *, ruleset: str) -> ValidationReport:
        all_findings: List[Finding] = []
        case_results: List[CaseResult] = []
        for case in sorted(self.cases, key=lambda c: c.case_id):
            applicable, reason = case.applicability(ctx)
            if not applicable:
                case_results.append(
                    CaseResult(
                        case_id=case.case_id,
                        name=case.name,
                        description=case.description,
                        status="skip",
                        outcome=None,
                        reason=reason or "not applicable",
                        duration_ms=0.0,
                        finding_count=0,
                        findings=[],
                    )
                )
                continue

            started = perf_counter()
            findings = sorted(case.run(ctx), key=_finding_sort_key)
            duration_ms = (perf_counter() - started) * 1000.0
            all_findings.extend(findings)
            has_errors = any(f.severity == FindingSeverity.ERROR for f in findings)
            case_results.append(
                CaseResult(
                    case_id=case.case_id,
                    name=case.name,
                    description=case.description,
                    status="run",
                    outcome="fail" if has_errors else "ok",
                    reason=None,
                    duration_ms=duration_ms,
                    finding_count=len(findings),
                    findings=findings,
                )
            )

        return ValidationReport(
            ruleset=ruleset,
            case_results=case_results,
            findings=sorted(all_findings, key=_finding_sort_key),
        )

    def run(self, ctx: ValidationContext) -> List[Finding]:
        return self.run_report(ctx, ruleset="core").findings


def _severity_rank(severity: Severity) -> int:
    normalized = FindingSeverity(severity)
    if normalized == FindingSeverity.ERROR:
        return 0
    if normalized == FindingSeverity.WARNING:
        return 1
    return 2


def _finding_sort_key(finding: Finding) -> Tuple[int, str, str, str]:
    return (
        _severity_rank(finding.severity),
        finding.code,
        finding.message,
        finding.location or "",
    )


def format_finding(finding: Finding) -> str:
    if finding.location:
        return f"{finding.location}: {finding.message}"
    return finding.message
