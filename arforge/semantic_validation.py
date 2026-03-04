from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from .model import Port, Project

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    location: Optional[str] = None


@dataclass(frozen=True)
class ValidationReport:
    ruleset: str
    findings: List[Finding]

    def error_findings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    def as_dict(self) -> Dict[str, object]:
        # This keeps a machine-readable report shape ready for future CLI output.
        return {
            "ruleset": self.ruleset,
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


class ValidationContext:
    def __init__(self, project: Project):
        self.project = project
        self.datatype_by_name = {d.name: d for d in project.datatypes}
        self.iface_by_name = {i.name: i for i in project.interfaces}
        self.swc_by_name = {s.name: s for s in project.swcs}
        self.instance_by_name = {i.name: i for i in project.system.instances}

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

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        for case in sorted(self.cases, key=lambda c: c.case_id):
            findings.extend(case.run(ctx))
        return sorted(findings, key=_finding_sort_key)


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
