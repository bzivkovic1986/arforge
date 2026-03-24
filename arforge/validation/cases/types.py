"""Datatype-focused validation cases.

This module contains rules for base type metadata and application datatype
constraints that depend on implementation/base type relationships.
"""

from __future__ import annotations

from typing import List

from ...semantic_validation import Finding, ValidationCase, ValidationContext


class BaseTypeMetadataCase(ValidationCase):
    case_id = "CORE-002"
    name = "BaseTypeMetadata"
    description = "Checks base type uniqueness and required metadata consistency."
    tags = ("core", "types", "base-types")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.baseTypes:
            return False, "no base types defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        seen_names: set[str] = set()

        for base_type in sorted(ctx.project.baseTypes, key=lambda d: d.name):
            if base_type.name in seen_names:
                findings.append(
                    self.finding(
                        f"Duplicate BaseType name '{base_type.name}' found.",
                        code="CORE-002-BASETYPE-DUPLICATE",
                    )
                )
            seen_names.add(base_type.name)

            has_bit_length = base_type.bitLength is not None
            has_signedness = base_type.signedness is not None
            if has_bit_length != has_signedness:
                findings.append(
                    self.finding(
                        f"BaseType '{base_type.name}' must define both bitLength and signedness together.",
                        code="CORE-002-BASETYPE-INCOMPLETE-METADATA",
                    )
                )

            if base_type.bitLength is not None and base_type.bitLength < 1:
                findings.append(
                    self.finding(
                        f"BaseType '{base_type.name}' has invalid bitLength '{base_type.bitLength}'; expected integer >= 1.",
                        code="CORE-002-BASETYPE-BITLENGTH",
                    )
                )

            if base_type.signedness is not None and base_type.signedness not in {"unsigned", "signed"}:
                findings.append(
                    self.finding(
                        f"BaseType '{base_type.name}' has invalid signedness '{base_type.signedness}'; expected 'unsigned' or 'signed'.",
                        code="CORE-002-BASETYPE-SIGNEDNESS",
                    )
                )

        return findings


class ApplicationConstraintCase(ValidationCase):
    case_id = "CORE-011"
    name = "ApplicationConstraints"
    description = "Checks application datatype constraints against implementation types and compu methods."
    tags = ("core", "types", "constraints")

    _FLOAT_BASE_TYPES = {"float32", "float64"}

    @staticmethod
    def _representable_range(bit_length: int, signedness: str) -> tuple[int, int]:
        if signedness == "unsigned":
            return 0, (2 ** bit_length) - 1
        return -(2 ** (bit_length - 1)), (2 ** (bit_length - 1)) - 1

    def _resolve_integer_base_metadata(self, base_type_name: str, base_type) -> tuple[int, str] | None:
        if base_type.bitLength is not None and base_type.signedness is not None:
            if base_type.bitLength >= 1 and base_type.signedness in {"unsigned", "signed"}:
                return base_type.bitLength, base_type.signedness
        return None

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        has_constraints = any(app.constraint is not None for app in ctx.project.applicationDataTypes)
        if not has_constraints:
            return False, "no application datatype constraints defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for app in sorted(ctx.project.applicationDataTypes, key=lambda d: d.name):
            if app.constraint is None:
                continue

            min_val = app.constraint.min
            max_val = app.constraint.max

            if min_val > max_val:
                findings.append(
                    self.finding(
                        f"ApplicationDataType '{app.name}' has invalid constraint range: min '{min_val}' > max '{max_val}'.",
                        code="CORE-011-CONSTRAINT-MIN-GT-MAX",
                    )
                )

            impl = ctx.implementation_type_by_name.get(app.implementationTypeRef)
            if impl is None:
                # Unknown implementation ref is reported by CORE-010.
                continue

            if impl.is_struct or impl.is_array:
                findings.append(
                    self.finding(
                        f"ApplicationDataType '{app.name}' uses implementation type '{impl.name}' of kind '{impl.kind or 'scalar'}'; constraints are only allowed for scalar numeric implementation types in v0.",
                        code="CORE-011-CONSTRAINT-NON-SCALAR",
                    )
                )
                continue

            if not impl.baseTypeRef:
                # Missing base type ref is reported by CORE-010.
                continue

            base_type = ctx.base_type_by_name.get(impl.baseTypeRef)
            if base_type is None:
                # Unknown base type ref is reported by CORE-010.
                continue

            base_name = base_type.name.lower()
            metadata = self._resolve_integer_base_metadata(base_name, base_type)
            if metadata is not None:
                if not isinstance(min_val, int) or not isinstance(max_val, int):
                    findings.append(
                        self.finding(
                            f"ApplicationDataType '{app.name}' constraints must be integers for integer base type '{base_type.name}'.",
                            code="CORE-011-CONSTRAINT-INTEGER-REQUIRED",
                        )
                    )
                    continue

                bit_length, signedness = metadata
                range_min, range_max = self._representable_range(bit_length, signedness)
                if min_val < range_min or min_val > range_max or max_val < range_min or max_val > range_max:
                    findings.append(
                        self.finding(
                            f"ApplicationDataType '{app.name}' constraints [{min_val}, {max_val}] are outside representable range [{range_min}, {range_max}] for base type '{base_type.name}'.",
                            code="CORE-011-CONSTRAINT-OUT-OF-RANGE",
                        )
                    )
                    continue
                continue

            if base_name in self._FLOAT_BASE_TYPES:
                # For v0 float32/float64, int and float bounds are both allowed without strict magnitude checks.
                continue

            if base_type.bitLength is None or base_type.signedness is None:
                findings.append(
                    self.finding(
                        f"ApplicationDataType '{app.name}' cannot validate constraints for base type '{base_type.name}' because bitLength/signedness metadata is missing.",
                        code="CORE-011-CONSTRAINT-MISSING-BASETYPE-METADATA",
                    )
                )
                continue

            findings.append(
                self.finding(
                    f"ApplicationDataType '{app.name}' uses unsupported constrained base type '{base_type.name}'.",
                    code="CORE-011-CONSTRAINT-UNSUPPORTED-BASETYPE",
                )
            )

        return findings
