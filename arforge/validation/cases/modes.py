"""Mode-declaration validation cases.

This module keeps the rules that validate mode declaration groups, their local
consistency, their initial modes, and whether declared groups are referenced.
"""

from __future__ import annotations

from collections import Counter
from typing import List

from ...semantic_validation import Finding, ValidationCase, ValidationContext


class ModeDeclarationGroupStructureCase(ValidationCase):
    case_id = "CORE-012"
    name = "ModeDeclarationGroupStructure"
    description = "Checks mode declaration group uniqueness and local mode naming rules."
    tags = ("core", "modes")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.modeDeclarationGroups:
            return False, "no mode declaration groups defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        group_name_counts = Counter(group.name for group in ctx.project.modeDeclarationGroups)

        for group_name in sorted(name for name, count in group_name_counts.items() if count > 1):
            findings.append(
                self.finding(
                    f"ModeDeclarationGroup '{group_name}' is defined more than once.",
                    code="CORE-012-MDG-DUPLICATE-GROUP",
                )
            )

        for group in sorted(ctx.project.modeDeclarationGroups, key=lambda group: group.name):
            mode_name_counts = Counter(mode.name for mode in group.modes)
            for mode_name in sorted(mode_name for mode_name, count in mode_name_counts.items() if count > 1):
                findings.append(
                    self.finding(
                        f"ModeDeclarationGroup '{group.name}' contains duplicate mode name '{mode_name}'.",
                        code="CORE-012-MDG-DUPLICATE-MODE",
                    )
                )

            for mode in group.modes:
                if mode.name.strip():
                    continue
                findings.append(
                    self.finding(
                        f"ModeDeclarationGroup '{group.name}' contains an empty mode name.",
                        code="CORE-012-MDG-EMPTY-MODE",
                    )
                )

        return findings


class ModeDeclarationGroupInitialModeCase(ValidationCase):
    case_id = "CORE-013"
    name = "ModeDeclarationGroupInitialMode"
    description = "Checks that each mode declaration group initialMode references one of its declared modes."
    tags = ("core", "modes")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.modeDeclarationGroups:
            return False, "no mode declaration groups defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for group in sorted(ctx.project.modeDeclarationGroups, key=lambda group: group.name):
            declared_modes = {mode.name for mode in group.modes}
            if group.initialMode in declared_modes:
                continue
            findings.append(
                self.finding(
                    f"ModeDeclarationGroup '{group.name}' initialMode '{group.initialMode}' does not match any declared mode.",
                    code="CORE-013-MDG-INITIAL-MODE",
                )
            )

        return findings


class UnusedModeDeclarationGroupCase(ValidationCase):
    case_id = "CORE-014"
    name = "UnusedModeDeclarationGroups"
    description = "Checks for mode declaration groups that are declared but never referenced by mode-switch interfaces."
    tags = ("core", "modes", "analysis", "usage")
    default_severity = "warning"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.declared_mode_declaration_groups:
            return False, "no mode declaration groups defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        referenced_groups = set(ctx.referenced_mode_declaration_groups)

        for group_name in ctx.declared_mode_declaration_groups:
            if group_name in referenced_groups:
                continue
            findings.append(
                self.finding(
                    f"ModeDeclarationGroup '{group_name}' is declared but not referenced by any ModeSwitchInterface.",
                    code="CORE-014-MDG-DECLARED-UNUSED",
                )
            )

        return findings
