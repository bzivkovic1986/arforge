from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from time import perf_counter
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from .model import Port, Project

Severity = Literal["error", "warning", "info"]
CaseStatus = Literal["run", "skip"]
CaseOutcome = Literal["ok", "fail"]


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    location: Optional[str] = None


@dataclass(frozen=True)
class ValidationReport:
    ruleset: str
    case_results: List["CaseResult"]
    findings: List[Finding]

    def error_findings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    def as_dict(self) -> Dict[str, object]:
        # This keeps a machine-readable report shape ready for future CLI output.
        return {
            "ruleset": self.ruleset,
            "cases": [
                {
                    "case_id": c.case_id,
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
                    "severity": f.severity,
                    "message": f.message,
                    "location": f.location,
                }
                for f in self.findings
            ],
        }


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    description: str
    status: CaseStatus
    outcome: Optional[CaseOutcome]
    reason: Optional[str]
    duration_ms: float
    finding_count: int
    findings: List[Finding]


class ValidationContext:
    def __init__(self, project: Project):
        self.project = project
        self.base_type_by_name = {d.name: d for d in project.baseTypes}
        self.implementation_type_by_name = {d.name: d for d in project.implementationDataTypes}
        self.application_type_by_name = {d.name: d for d in project.applicationDataTypes}
        self.datatype_by_name = {**self.base_type_by_name, **self.implementation_type_by_name, **self.application_type_by_name}
        self.iface_by_name = {i.name: i for i in project.interfaces}
        self.swc_by_name = {s.name: s for s in project.swcs}
        self.instance_by_name = {i.name: i for i in project.system.composition.components}

        self.ports_by_swc: Dict[str, Dict[str, Port]] = {
            swc.name: {p.name: p for p in swc.ports} for swc in project.swcs
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

    def find_swc_port(self, swc_name: str, port_name: str) -> Optional[Port]:
        return self.ports_by_swc.get(swc_name, {}).get(port_name)


class ValidationCase(ABC):
    case_id: str = ""
    description: str = ""
    tags: Tuple[str, ...] = ()
    default_severity: Severity = "error"

    @abstractmethod
    def run(self, ctx: ValidationContext) -> List[Finding]:
        raise NotImplementedError

    def applicability(self, ctx: ValidationContext) -> Tuple[bool, Optional[str]]:
        return True, None

    def finding(self, message: str, *, location: Optional[str] = None, code: Optional[str] = None) -> Finding:
        return Finding(
            code=code or self.case_id,
            severity=self.default_severity,
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
            has_errors = any(f.severity == "error" for f in findings)
            case_results.append(
                CaseResult(
                    case_id=case.case_id,
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
    if severity == "error":
        return 0
    if severity == "warning":
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
