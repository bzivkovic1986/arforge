"""Common validation cases shared across the model.

This module holds cross-cutting rules that do not belong to a single AUTOSAR
domain, such as global uniqueness checks spanning multiple model sections.
"""

from __future__ import annotations

from typing import List

from ...semantic_validation import Finding, ValidationCase, ValidationContext


class DuplicateNameCase(ValidationCase):
    case_id = "CORE-001"
    name = "GlobalUniqueness"
    description = "Checks that globally named model elements remain unique."
    tags = ("core", "structure", "uniqueness")

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        project = ctx.project

        type_names = (
            [d.name for d in project.baseTypes]
            + [d.name for d in project.implementationDataTypes]
            + [d.name for d in project.applicationDataTypes]
        )
        if len(set(type_names)) != len(type_names):
            findings.append(self.finding("Duplicate datatype names found.", code="CORE-001-DATATYPE-DUPLICATE"))
        if len({i.name for i in project.interfaces}) != len(project.interfaces):
            findings.append(self.finding("Duplicate interface names found.", code="CORE-001-INTERFACE-DUPLICATE"))
        if len({s.name for s in project.swcs}) != len(project.swcs):
            findings.append(self.finding("Duplicate SWC names found.", code="CORE-001-SWC-DUPLICATE"))
        if len({u.name for u in project.units}) != len(project.units):
            findings.append(self.finding("Duplicate unit names found.", code="CORE-001-UNIT-DUPLICATE"))
        if len({c.name for c in project.compuMethods}) != len(project.compuMethods):
            findings.append(self.finding("Duplicate compu method names found.", code="CORE-001-COMPU-METHOD-DUPLICATE"))
        if len({c.name for c in project.system.composition.components}) != len(project.system.composition.components):
            findings.append(self.finding("System composition has duplicate component prototype names.", code="CORE-001-INSTANCE-DUPLICATE"))

        return findings
