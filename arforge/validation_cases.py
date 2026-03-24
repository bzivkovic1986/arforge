from __future__ import annotations

from collections import Counter
from typing import List

from .semantic_validation import Finding, ValidationCase, ValidationContext


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


class InterfaceSemanticCase(ValidationCase):
    case_id = "CORE-010"
    name = "InterfaceSemantics"
    description = "Checks interface structure and datatype references."
    tags = ("core", "interfaces")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.interfaces:
            return False, "no interfaces defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        dt_names = set(ctx.datatype_by_name.keys())
        impl_by_name = {i.name: i for i in ctx.project.implementationDataTypes}

        def _duplicate_field_names(impl_name: str, field_names: List[str]) -> List[Finding]:
            duplicate_names = sorted({name for name in field_names if field_names.count(name) > 1})
            return [
                self.finding(
                    f"Struct ImplementationDataType '{impl_name}' has duplicate field name '{field_name}'.",
                    code="CORE-010-STRUCT-DUPLICATE-FIELD",
                )
                for field_name in duplicate_names
            ]

        def _resolve_nested_struct_ref(type_ref: str, visited_impls: set[str] | None = None) -> str | None:
            visited = set() if visited_impls is None else set(visited_impls)
            if type_ref in visited:
                return None

            impl = impl_by_name.get(type_ref)
            if impl is None:
                return None
            if impl.is_struct:
                return impl.name
            if impl.is_array and impl.elementTypeRef:
                visited.add(type_ref)
                return _resolve_nested_struct_ref(impl.elementTypeRef, visited)
            return None

        def _normalize_cycle(cycle: list[str]) -> list[str]:
            cycle_nodes = cycle[:-1]
            if not cycle_nodes:
                return cycle

            rotations = [cycle_nodes[idx:] + cycle_nodes[:idx] for idx in range(len(cycle_nodes))]
            normalized = min(rotations)
            return normalized + [normalized[0]]

        for impl in sorted(ctx.project.implementationDataTypes, key=lambda d: d.name):
            if impl.is_struct:
                if not impl.fields:
                    findings.append(
                        self.finding(
                            f"Struct ImplementationDataType '{impl.name}' must define at least one field.",
                            code="CORE-010-STRUCT-EMPTY",
                        )
                    )
                    continue
                field_names = [f.name for f in impl.fields]
                findings.extend(_duplicate_field_names(impl.name, field_names))
                for field in sorted(impl.fields, key=lambda f: f.name):
                    if field.typeRef not in ctx.datatype_by_name:
                        findings.append(
                            self.finding(
                                f"Struct ImplementationDataType '{impl.name}' field '{field.name}' references unknown typeRef '{field.typeRef}'.",
                                code="CORE-010-STRUCT-UNKNOWN-TYPE",
                            )
                        )
                        continue
                    if field.typeRef in ctx.application_type_by_name:
                        findings.append(
                            self.finding(
                                f"Struct ImplementationDataType '{impl.name}' field '{field.name}' must not reference application data type '{field.typeRef}'.",
                                code="CORE-010-STRUCT-APPLICATION-TYPE",
                            )
                        )
            elif impl.is_array:
                if not impl.elementTypeRef:
                    findings.append(
                        self.finding(
                            f"Array ImplementationDataType '{impl.name}' must define elementTypeRef.",
                            code="CORE-010-ARRAY-MISSING-ELEMENT-TYPE",
                        )
                    )
                elif impl.elementTypeRef not in ctx.datatype_by_name:
                    findings.append(
                        self.finding(
                            f"Array ImplementationDataType '{impl.name}' references unknown elementTypeRef '{impl.elementTypeRef}'.",
                            code="CORE-010-ARRAY-UNKNOWN-ELEMENT-TYPE",
                        )
                    )
                elif impl.elementTypeRef in ctx.application_type_by_name:
                    findings.append(
                        self.finding(
                            f"Array ImplementationDataType '{impl.name}' must not reference application data type '{impl.elementTypeRef}'.",
                            code="CORE-010-ARRAY-APPLICATION-TYPE",
                        )
                    )

                if impl.length is None:
                    findings.append(
                        self.finding(
                            f"Array ImplementationDataType '{impl.name}' must define length.",
                            code="CORE-010-ARRAY-MISSING-LENGTH",
                        )
                    )
                elif impl.length < 1:
                    findings.append(
                        self.finding(
                            f"Array ImplementationDataType '{impl.name}' has invalid length '{impl.length}'; expected integer >= 1.",
                            code="CORE-010-ARRAY-LENGTH",
                        )
                    )

                if impl.elementTypeRef == impl.name:
                    findings.append(
                        self.finding(
                            f"Array ImplementationDataType '{impl.name}' must not reference itself as elementTypeRef.",
                            code="CORE-010-ARRAY-SELF-REFERENCE",
                        )
                    )
            else:
                if not impl.baseTypeRef:
                    findings.append(
                        self.finding(
                            f"ImplementationDataType '{impl.name}' must define baseTypeRef.",
                            code="CORE-010-IMPLEMENTATION-MISSING-BASETYPE",
                        )
                    )
                elif impl.baseTypeRef not in ctx.base_type_by_name:
                    findings.append(
                        self.finding(
                            f"ImplementationDataType '{impl.name}' references unknown baseTypeRef '{impl.baseTypeRef}'.",
                            code="CORE-010-IMPLEMENTATION-UNKNOWN-BASETYPE",
                        )
                    )

        struct_ref_graph: dict[str, list[str]] = {}
        for impl in sorted(ctx.project.implementationDataTypes, key=lambda d: d.name):
            if not impl.is_struct:
                continue
            nested_struct_refs = {
                nested_ref
                for field in impl.fields
                for nested_ref in [_resolve_nested_struct_ref(field.typeRef)]
                if nested_ref is not None
            }
            struct_ref_graph[impl.name] = sorted(nested_struct_refs)

        visit_state: dict[str, str] = {}
        reported_cycles: set[tuple[str, ...]] = set()

        def _visit_struct(node: str, path: list[str]) -> None:
            visit_state[node] = "visiting"
            path.append(node)
            for target in struct_ref_graph.get(node, []):
                if visit_state.get(target) == "visiting":
                    cycle_start = path.index(target)
                    cycle = _normalize_cycle(path[cycle_start:] + [target])
                    cycle_key = tuple(cycle)
                    if cycle_key not in reported_cycles:
                        reported_cycles.add(cycle_key)
                        findings.append(
                            self.finding(
                                f"Struct implementation type cycle detected: {' -> '.join(cycle)}.",
                                code="CORE-010-STRUCT-CYCLE",
                            )
                        )
                    continue
                if visit_state.get(target) == "done":
                    continue
                _visit_struct(target, path)
            path.pop()
            visit_state[node] = "done"

        for struct_name in sorted(struct_ref_graph):
            if visit_state.get(struct_name) == "done":
                continue
            _visit_struct(struct_name, [])

        for app in sorted(ctx.project.applicationDataTypes, key=lambda d: d.name):
            if app.implementationTypeRef not in ctx.implementation_type_by_name:
                findings.append(
                    self.finding(
                        f"ApplicationDataType '{app.name}' references unknown implementationTypeRef '{app.implementationTypeRef}'.",
                        code="CORE-010-APPLICATION-UNKNOWN-IMPLEMENTATION",
                    )
                )
            if app.unitRef and app.unitRef not in ctx.unit_by_name:
                findings.append(
                    self.finding(
                        f"ApplicationDataType '{app.name}' references unknown unitRef '{app.unitRef}'.",
                        code="CORE-010-APPLICATION-UNKNOWN-UNIT",
                    )
                )
            compu = None
            if app.compuMethodRef:
                compu = ctx.compu_method_by_name.get(app.compuMethodRef)
                if compu is None:
                    findings.append(
                        self.finding(
                            f"ApplicationDataType '{app.name}' references unknown compuMethodRef '{app.compuMethodRef}'.",
                            code="CORE-010-APPLICATION-UNKNOWN-COMPU-METHOD",
                        )
                    )
                elif compu.category == "linear" and not app.unitRef:
                    findings.append(
                        self.finding(
                            f"ApplicationDataType '{app.name}' must define unitRef when compuMethodRef is set.",
                            code="CORE-010-APPLICATION-COMPU-REQUIRES-UNIT",
                        )
                    )
            if app.unitRef and compu and compu.category == "linear" and app.unitRef != compu.unitRef:
                findings.append(
                    self.finding(
                        f"ApplicationDataType '{app.name}' unitRef '{app.unitRef}' must match compuMethod '{compu.name}' unitRef '{compu.unitRef}'.",
                        code="CORE-010-APPLICATION-UNIT-MISMATCH",
                    )
                )

        for compu in sorted(ctx.project.compuMethods, key=lambda c: c.name):
            if compu.category not in {"linear", "textTable"}:
                findings.append(
                    self.finding(
                        f"CompuMethod '{compu.name}' has unsupported category '{compu.category}'.",
                        code="CORE-010-COMPU-CATEGORY",
                    )
                )
                continue

            if compu.category == "linear":
                if compu.unitRef not in ctx.unit_by_name:
                    findings.append(
                        self.finding(
                            f"CompuMethod '{compu.name}' references unknown unitRef '{compu.unitRef}'.",
                            code="CORE-010-COMPU-UNKNOWN-UNIT",
                        )
                    )
                if compu.factor == 0:
                    findings.append(
                        self.finding(
                            f"CompuMethod '{compu.name}' must have non-zero factor.",
                            code="CORE-010-COMPU-FACTOR-ZERO",
                        )
                    )
                if compu.physMin is not None and compu.physMax is not None and compu.physMin > compu.physMax:
                    findings.append(
                        self.finding(
                            f"CompuMethod '{compu.name}' has invalid physical range: physMin '{compu.physMin}' > physMax '{compu.physMax}'.",
                            code="CORE-010-COMPU-RANGE",
                        )
                    )
                continue

            if not compu.entries:
                findings.append(
                    self.finding(
                        f"CompuMethod '{compu.name}' must define at least one textTable entry.",
                        code="CORE-010-COMPU-TEXTTABLE-EMPTY",
                    )
                )
                continue

            seen_values: set[int] = set()
            for entry in sorted(compu.entries, key=lambda e: (e.value, e.label)):
                if entry.value in seen_values:
                    findings.append(
                        self.finding(
                            f"CompuMethod '{compu.name}' contains duplicate textTable value '{entry.value}'.",
                            code="CORE-010-COMPU-TEXTTABLE-DUPLICATE-VALUE",
                        )
                    )
                seen_values.add(entry.value)
                if not entry.label.strip():
                    findings.append(
                        self.finding(
                            f"CompuMethod '{compu.name}' has empty textTable label for value '{entry.value}'.",
                            code="CORE-010-COMPU-TEXTTABLE-EMPTY-LABEL",
                        )
                    )

        for itf in sorted(ctx.project.interfaces, key=lambda i: i.name):
            if itf.type == "senderReceiver":
                if itf.modeGroupRef is not None:
                    findings.append(
                        self.finding(
                            f"SenderReceiver interface '{itf.name}' must not define modeGroupRef.",
                            code="CORE-010-SR-MODE-GROUP-REF",
                        )
                    )
                if not itf.dataElements:
                    findings.append(
                        self.finding(
                            f"SenderReceiver interface '{itf.name}' must have dataElements.",
                            code="CORE-010-SR-MISSING-DATAELEMENTS",
                        )
                    )
                else:
                    for de in itf.dataElements:
                        if de.typeRef not in dt_names:
                            findings.append(
                                self.finding(
                                    f"Interface '{itf.name}' dataElement '{de.name}' references unknown datatype '{de.typeRef}'.",
                                    code="CORE-010-DATAELEMENT-UNKNOWN-DATATYPE",
                                )
                            )
            elif itf.type == "clientServer":
                if not itf.operations:
                    findings.append(
                        self.finding(
                            f"ClientServer interface '{itf.name}' must have operations.",
                            code="CORE-010-CS-MISSING-OPERATIONS",
                        )
                    )
                else:
                    op_names = [op.name for op in itf.operations]
                    if len(set(op_names)) != len(op_names):
                        findings.append(
                            self.finding(
                                f"ClientServer interface '{itf.name}' has duplicate operation names.",
                                code="CORE-010-CS-OPERATION-DUPLICATE",
                            )
                        )

                    for op in sorted(itf.operations, key=lambda o: o.name):
                        arg_names = [arg.name for arg in op.arguments]
                        if len(set(arg_names)) != len(arg_names):
                            findings.append(
                                self.finding(
                                    f"Interface '{itf.name}' operation '{op.name}' has duplicate argument names.",
                                    code="CORE-010-CS-ARGUMENT-DUPLICATE",
                                )
                            )

                        for arg in sorted(op.arguments, key=lambda a: a.name):
                            if arg.direction not in {"in", "out", "inout"}:
                                findings.append(
                                    self.finding(
                                        f"Interface '{itf.name}' operation '{op.name}' argument '{arg.name}' has invalid direction '{arg.direction}'.",
                                        code="CORE-010-CS-ARGUMENT-DIRECTION",
                                    )
                                )
                            if arg.typeRef not in dt_names:
                                findings.append(
                                    self.finding(
                                        f"Interface '{itf.name}' operation '{op.name}' argument '{arg.name}' references unknown datatype '{arg.typeRef}'.",
                                        code="CORE-010-CS-ARGUMENT-UNKNOWN-DATATYPE",
                                    )
                                )

                        if op.returnType != "void" and op.returnType not in dt_names:
                            findings.append(
                                self.finding(
                                    f"Interface '{itf.name}' operation '{op.name}' references unknown returnType '{op.returnType}'.",
                                    code="CORE-010-CS-RETURN-UNKNOWN-DATATYPE",
                                )
                            )

                        seen_error_names: set[str] = set()
                        seen_error_codes: set[int] = set()
                        for possible_error in sorted(
                            op.possibleErrors,
                            key=lambda e: (e.name, -1 if e.code is None else e.code),
                        ):
                            error_name = possible_error.name.strip()
                            if not error_name:
                                findings.append(
                                    self.finding(
                                        f"Interface '{itf.name}' operation '{op.name}' has possibleErrors entry with empty name.",
                                        code="CORE-010-CS-POSSIBLE-ERROR-NAME",
                                    )
                                )
                            if error_name in seen_error_names:
                                findings.append(
                                    self.finding(
                                        f"Interface '{itf.name}' operation '{op.name}' has duplicate possibleErrors name '{possible_error.name}'.",
                                        code="CORE-010-CS-POSSIBLE-ERROR-DUPLICATE-NAME",
                                    )
                                )
                            seen_error_names.add(error_name)

                            if possible_error.code is None:
                                continue
                            if not isinstance(possible_error.code, int) or isinstance(possible_error.code, bool):
                                findings.append(
                                    self.finding(
                                        f"Interface '{itf.name}' operation '{op.name}' has possibleErrors code '{possible_error.code}' that must be an integer.",
                                        code="CORE-010-CS-POSSIBLE-ERROR-CODE-TYPE",
                                    )
                                )
                                continue
                            if possible_error.code < 0:
                                findings.append(
                                    self.finding(
                                        f"Interface '{itf.name}' operation '{op.name}' has possibleErrors code '{possible_error.code}' that must be >= 0.",
                                        code="CORE-010-CS-POSSIBLE-ERROR-CODE-RANGE",
                                    )
                                )
                            if possible_error.code in seen_error_codes:
                                findings.append(
                                    self.finding(
                                        f"Interface '{itf.name}' operation '{op.name}' has duplicate possibleErrors code '{possible_error.code}'.",
                                        code="CORE-010-CS-POSSIBLE-ERROR-DUPLICATE-CODE",
                                    )
                            )
                            seen_error_codes.add(possible_error.code)
                if itf.modeGroupRef is not None:
                    findings.append(
                        self.finding(
                            f"ClientServer interface '{itf.name}' must not define modeGroupRef.",
                            code="CORE-010-CS-MODE-GROUP-REF",
                        )
                    )
            elif itf.type == "modeSwitch":
                if itf.dataElements:
                    findings.append(
                        self.finding(
                            f"ModeSwitch interface '{itf.name}' must not define dataElements.",
                            code="CORE-010-MS-DATAELEMENTS",
                        )
                    )
                if itf.operations:
                    findings.append(
                        self.finding(
                            f"ModeSwitch interface '{itf.name}' must not define operations.",
                            code="CORE-010-MS-OPERATIONS",
                        )
                    )
                if not itf.modeGroupRef:
                    findings.append(
                        self.finding(
                            f"ModeSwitch interface '{itf.name}' must define modeGroupRef.",
                            code="CORE-010-MS-MISSING-MODE-GROUP-REF",
                        )
                    )
                    continue
                if itf.modeGroupRef not in ctx.mode_declaration_group_by_name:
                    findings.append(
                        self.finding(
                            f"ModeSwitch interface '{itf.name}' references unknown ModeDeclarationGroup '{itf.modeGroupRef}'.",
                            code="CORE-010-MS-UNKNOWN-MODE-GROUP-REF",
                        )
                    )
            else:
                findings.append(
                    self.finding(
                        f"Unknown interface type '{itf.type}' on '{itf.name}'.",
                        code="CORE-010-UNKNOWN-INTERFACE-TYPE",
                    )
                )

        return findings


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


class SwcStructureCase(ValidationCase):
    case_id = "CORE-020"
    name = "SwcStructure"
    description = "Checks SWC-local uniqueness for runnables and ports."
    tags = ("core", "swc")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.swcs:
            return False, "no SWCs defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            port_names = [p.name for p in swc.ports]
            if len(set(port_names)) != len(port_names):
                findings.append(self.finding(f"SWC '{swc.name}' has duplicate port names.", code="CORE-020-PORT-DUPLICATE"))
            runnable_names = [r.name for r in swc.runnables]
            if len(set(runnable_names)) != len(runnable_names):
                findings.append(self.finding(f"SWC '{swc.name}' has duplicate runnable names.", code="CORE-020-RUNNABLE-DUPLICATE"))
        return findings


class SwcPortInterfaceCase(ValidationCase):
    case_id = "CORE-021"
    name = "PortInterfaceReferences"
    description = "Checks that each SWC port references an existing interface and uses the expected kind."
    tags = ("core", "swc", "interfaces")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.swcs:
            return False, "no SWCs defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            for port in sorted(swc.ports, key=lambda p: p.name):
                itf = ctx.iface_by_name.get(port.interfaceRef)
                if itf is None:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' references unknown interface '{port.interfaceRef}'.",
                            code="CORE-021-UNKNOWN-INTERFACE-REF",
                        )
                    )
                    continue

                if port.interfaceType != itf.type:
                    findings.append(
                        self.finding(
                            f"Internal mismatch: port '{swc.name}.{port.name}' interfaceType '{port.interfaceType}' != interface '{itf.type}'.",
                            code="CORE-021-INTERFACE-TYPE-MISMATCH",
                        )
                    )
        return findings


class RunnableAccessSemanticCase(ValidationCase):
    case_id = "CORE-022"
    name = "RunnableAccessSemantics"
    description = "Checks runnable reads, writes, and calls against SWC port and interface semantics."
    tags = ("core", "swc", "runnables", "interfaces")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.swcs:
            return False, "no SWCs defined"
        has_accesses = any(
            runnable.reads or runnable.writes or runnable.calls
            for swc in ctx.project.swcs
            for runnable in swc.runnables
        )
        if not has_accesses:
            return False, "no runnable accesses defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            for runnable in sorted(swc.runnables, key=lambda r: r.name):
                location_base = f"SWC '{swc.name}' runnable '{runnable.name}'"

                for read in sorted(runnable.reads, key=lambda a: (a.port, a.dataElement)):
                    port = ctx.find_swc_port(swc.name, read.port)
                    if port is None:
                        findings.append(
                            self.finding(
                                f"{location_base} reads unknown port '{read.port}'.",
                                code="CORE-022-READ-UNKNOWN-PORT",
                            )
                        )
                        continue
                    if port.direction != "requires":
                        findings.append(
                            self.finding(
                                f"{location_base} read on port '{read.port}' requires direction 'requires', found '{port.direction}'.",
                                code="CORE-022-READ-DIRECTION",
                            )
                        )
                    itf = ctx.iface_by_name.get(port.interfaceRef)
                    if itf is None:
                        # Unknown interface reference is reported by CORE-021.
                        continue
                    if itf.type != "senderReceiver":
                        findings.append(
                            self.finding(
                                f"{location_base} read on port '{read.port}' requires senderReceiver interface, found '{itf.type}'.",
                                code="CORE-022-READ-INTERFACE-TYPE",
                            )
                        )
                        continue
                    if read.dataElement not in ctx.sr_data_elements_by_iface.get(itf.name, set()):
                        findings.append(
                            self.finding(
                                f"{location_base} reads unknown dataElement '{read.dataElement}' from interface '{itf.name}'.",
                                code="CORE-022-READ-UNKNOWN-DATAELEMENT",
                            )
                        )

                for write in sorted(runnable.writes, key=lambda a: (a.port, a.dataElement)):
                    port = ctx.find_swc_port(swc.name, write.port)
                    if port is None:
                        findings.append(
                            self.finding(
                                f"{location_base} writes unknown port '{write.port}'.",
                                code="CORE-022-WRITE-UNKNOWN-PORT",
                            )
                        )
                        continue
                    if port.direction != "provides":
                        findings.append(
                            self.finding(
                                f"{location_base} write on port '{write.port}' requires direction 'provides', found '{port.direction}'.",
                                code="CORE-022-WRITE-DIRECTION",
                            )
                        )
                    itf = ctx.iface_by_name.get(port.interfaceRef)
                    if itf is None:
                        # Unknown interface reference is reported by CORE-021.
                        continue
                    if itf.type != "senderReceiver":
                        findings.append(
                            self.finding(
                                f"{location_base} write on port '{write.port}' requires senderReceiver interface, found '{itf.type}'.",
                                code="CORE-022-WRITE-INTERFACE-TYPE",
                            )
                        )
                        continue
                    if write.dataElement not in ctx.sr_data_elements_by_iface.get(itf.name, set()):
                        findings.append(
                            self.finding(
                                f"{location_base} writes unknown dataElement '{write.dataElement}' to interface '{itf.name}'.",
                                code="CORE-022-WRITE-UNKNOWN-DATAELEMENT",
                            )
                        )

                for call in sorted(
                    runnable.calls,
                    key=lambda a: (a.port, a.operation, -1 if a.timeoutMs is None else a.timeoutMs),
                ):
                    port = ctx.find_swc_port(swc.name, call.port)
                    if port is None:
                        findings.append(
                            self.finding(
                                f"{location_base} calls unknown port '{call.port}'.",
                                code="CORE-022-CALL-UNKNOWN-PORT",
                            )
                        )
                        continue
                    if port.direction != "requires":
                        findings.append(
                            self.finding(
                                f"{location_base} call on port '{call.port}' requires direction 'requires', found '{port.direction}'.",
                                code="CORE-022-CALL-DIRECTION",
                            )
                        )
                    itf = ctx.iface_by_name.get(port.interfaceRef)
                    if itf is None:
                        # Unknown interface reference is reported by CORE-021.
                        continue
                    if itf.type != "clientServer":
                        findings.append(
                            self.finding(
                                f"{location_base} call on port '{call.port}' requires clientServer interface, found '{itf.type}'.",
                                code="CORE-022-CALL-INTERFACE-TYPE",
                            )
                        )
                        continue
                    if call.operation not in ctx.cs_operations_by_iface.get(itf.name, set()):
                        findings.append(
                            self.finding(
                                f"{location_base} calls unknown operation '{call.operation}' on interface '{itf.name}'.",
                                code="CORE-022-CALL-UNKNOWN-OPERATION",
                            )
                        )

                    if call.timeoutMs is not None and call.timeoutMs < 0:
                        findings.append(
                            self.finding(
                                f"{location_base} call '{call.port}.{call.operation}' timeoutMs must be >= 0, found '{call.timeoutMs}'.",
                                code="CORE-022-CALL-TIMEOUT-RANGE",
                            )
                        )

                    call_mode = "synchronous"
                    if port.comSpec is not None and port.comSpec.callMode is not None:
                        call_mode = port.comSpec.callMode
                    if call_mode == "asynchronous" and call.timeoutMs is not None:
                        findings.append(
                            self.finding(
                                f"{location_base} call '{call.port}.{call.operation}' timeoutMs is not allowed when port callMode is asynchronous.",
                                code="CORE-022-CALL-ASYNC-TIMEOUT",
                            )
                        )

        return findings


class OperationInvokedEventCase(ValidationCase):
    case_id = "CORE-023"
    name = "OperationInvokedEvents"
    description = "Checks operation-invoked event bindings for provided client-server operations."
    tags = ("core", "swc", "runnables", "interfaces")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.swcs:
            return False, "no SWCs defined"
        has_cs_provider = any(
            port.direction == "provides"
            and ((itf := ctx.iface_by_name.get(port.interfaceRef)) is not None)
            and itf.type == "clientServer"
            for swc in ctx.project.swcs
            for port in swc.ports
        )
        has_events = any(
            runnable.operationInvokedEvents
            for swc in ctx.project.swcs
            for runnable in swc.runnables
        )
        if not has_cs_provider and not has_events:
            return False, "no provided clientServer ports or operationInvokedEvents"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        valid_bindings: set[tuple[str, str, str]] = set()

        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            for runnable in sorted(swc.runnables, key=lambda r: r.name):
                location_base = f"SWC '{swc.name}' runnable '{runnable.name}'"
                for event in sorted(runnable.operationInvokedEvents, key=lambda e: (e.port, e.operation)):
                    port = ctx.find_swc_port(swc.name, event.port)
                    if port is None:
                        findings.append(
                            self.finding(
                                f"{location_base} operationInvokedEvents references unknown port '{event.port}'.",
                                code="CORE-023-OIE-UNKNOWN-PORT",
                            )
                        )
                        continue
                    if port.direction != "provides":
                        findings.append(
                            self.finding(
                                f"{location_base} operationInvokedEvents on port '{event.port}' requires direction 'provides', found '{port.direction}'.",
                                code="CORE-023-OIE-DIRECTION",
                            )
                        )
                    itf = ctx.iface_by_name.get(port.interfaceRef)
                    if itf is None:
                        # Unknown interface reference is reported by CORE-021.
                        continue
                    if itf.type != "clientServer":
                        findings.append(
                            self.finding(
                                f"{location_base} operationInvokedEvents on port '{event.port}' requires clientServer interface, found '{itf.type}'.",
                                code="CORE-023-OIE-INTERFACE-TYPE",
                            )
                        )
                        continue
                    operations = ctx.cs_operations_by_iface.get(itf.name, set())
                    if event.operation not in operations:
                        findings.append(
                            self.finding(
                                f"{location_base} operationInvokedEvents references unknown operation '{event.operation}' on interface '{itf.name}'.",
                                code="CORE-023-OIE-UNKNOWN-OPERATION",
                            )
                        )
                        continue
                    valid_bindings.add((swc.name, event.port, event.operation))

            for port in sorted(swc.ports, key=lambda p: p.name):
                if port.direction != "provides":
                    continue
                itf = ctx.iface_by_name.get(port.interfaceRef)
                if itf is None or itf.type != "clientServer":
                    continue
                port_usage = ctx.find_swc_port_usage(swc.name, port.name)
                if not port_usage.operation_invoked_events:
                    continue
                for op in sorted(itf.operations or [], key=lambda o: o.name):
                    if (swc.name, port.name, op.name) not in valid_bindings:
                        findings.append(
                            self.finding(
                                f"SWC '{swc.name}' provides-port '{port.name}' is missing operationInvokedEvents binding for operation '{op.name}'.",
                                code="CORE-023-CS-UNBOUND-OPERATION",
                            )
                        )

        return findings


class RunnableTriggerPolicyCase(ValidationCase):
    case_id = "CORE-024"
    name = "RunnableTriggerPolicy"
    description = "Checks that each runnable uses exactly one trigger style."
    tags = ("core", "swc", "runnables")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.swcs:
            return False, "no SWCs defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            for runnable in sorted(swc.runnables, key=lambda r: r.name):
                has_timing = runnable.timingEventMs is not None
                has_oie = bool(runnable.operationInvokedEvents)
                has_dre = bool(runnable.dataReceiveEvents)
                has_mse = bool(runnable.modeSwitchEvents)
                has_init = runnable.initEvent
                trigger_count = sum([has_timing, has_oie, has_dre, has_mse, has_init])
                if trigger_count > 1:
                    findings.append(
                        self.finding(
                            f"Runnable '{runnable.name}' must define exactly one trigger style among timingEventMs, operationInvokedEvents, dataReceiveEvents, modeSwitchEvents, and initEvent.",
                            code="CORE-024-MULTIPLE-TRIGGERS",
                        )
                    )
                if trigger_count == 0:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' runnable '{runnable.name}' must define at least one trigger: timingEventMs, operationInvokedEvents, dataReceiveEvents, modeSwitchEvents, or initEvent.",
                            code="CORE-024-MISSING-TRIGGER",
                        )
                    )
        return findings


class ComSpecSemanticCase(ValidationCase):
    case_id = "CORE-025"
    name = "PortComSpecSemantics"
    description = "Checks sender-receiver and client-server ComSpec on SWC ports."
    tags = ("core", "swc", "ports", "comspec")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.swcs:
            return False, "no SWCs defined"
        has_comspec = any(
            port.comSpec is not None
            for swc in ctx.project.swcs
            for port in swc.ports
        )
        if not has_comspec:
            return False, "no port comSpec defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        sr_modes = {"implicit", "explicit", "queued"}
        cs_call_modes = {"synchronous", "asynchronous"}
        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            for port in sorted(swc.ports, key=lambda p: p.name):
                com_spec = port.comSpec
                if com_spec is None:
                    continue

                itf = ctx.iface_by_name.get(port.interfaceRef)
                if itf is None:
                    # Unknown interface reference is reported by CORE-021.
                    continue

                if itf.type == "senderReceiver":
                    if com_spec.callMode is not None:
                        findings.append(
                            self.finding(
                                f"SWC '{swc.name}' port '{port.name}' senderReceiver comSpec must not define callMode.",
                                code="CORE-025-SR-COMSPEC-CALLMODE",
                            )
                        )
                    if com_spec.timeoutMs is not None:
                        findings.append(
                            self.finding(
                                f"SWC '{swc.name}' port '{port.name}' senderReceiver comSpec must not define timeoutMs.",
                                code="CORE-025-SR-COMSPEC-TIMEOUT",
                            )
                        )

                    if com_spec.mode is None:
                        findings.append(
                            self.finding(
                                f"SWC '{swc.name}' port '{port.name}' senderReceiver comSpec must define mode.",
                                code="CORE-025-SR-COMSPEC-MISSING-MODE",
                            )
                        )
                        continue
                    if com_spec.mode not in sr_modes:
                        findings.append(
                            self.finding(
                                f"SWC '{swc.name}' port '{port.name}' senderReceiver comSpec has invalid mode '{com_spec.mode}'.",
                                code="CORE-025-SR-COMSPEC-MODE",
                            )
                        )
                        continue

                    if com_spec.mode == "queued":
                        if com_spec.queueLength is None:
                            findings.append(
                                self.finding(
                                    f"SWC '{swc.name}' port '{port.name}' queued comSpec must define queueLength.",
                                    code="CORE-025-COMSPEC-QUEUED-MISSING-QUEUE-LENGTH",
                                )
                            )
                        elif com_spec.queueLength < 1:
                            findings.append(
                                self.finding(
                                    f"SWC '{swc.name}' port '{port.name}' queued comSpec queueLength must be >= 1, found '{com_spec.queueLength}'.",
                                    code="CORE-025-COMSPEC-QUEUED-QUEUE-LENGTH-RANGE",
                                )
                            )
                        continue

                    if com_spec.queueLength is not None:
                        findings.append(
                            self.finding(
                                f"SWC '{swc.name}' port '{port.name}' comSpec mode '{com_spec.mode}' must not define queueLength.",
                                code="CORE-025-COMSPEC-NONQUEUED-QUEUE-LENGTH",
                            )
                        )
                    continue

                if itf.type == "modeSwitch":
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' modeSwitch interfaces do not support comSpec.",
                            code="CORE-025-MS-COMSPEC-UNSUPPORTED",
                        )
                    )
                    continue

                if itf.type != "clientServer":
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' comSpec uses unsupported interface type '{itf.type}'.",
                            code="CORE-025-COMSPEC-INTERFACE-TYPE",
                        )
                    )
                    continue

                if com_spec.mode is not None:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' clientServer comSpec must not define mode.",
                            code="CORE-025-CS-COMSPEC-MODE",
                        )
                    )
                if com_spec.callMode is None:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' clientServer comSpec must define callMode.",
                            code="CORE-025-CS-COMSPEC-MISSING-CALLMODE",
                        )
                    )
                    continue

                if com_spec.callMode not in cs_call_modes:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' clientServer comSpec has invalid callMode '{com_spec.callMode}'.",
                            code="CORE-025-CS-COMSPEC-CALLMODE",
                        )
                    )
                    continue

                if com_spec.callMode == "asynchronous" and port.direction != "requires":
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' clientServer asynchronous comSpec requires direction 'requires', found '{port.direction}'.",
                            code="CORE-025-CS-COMSPEC-ASYNC-DIRECTION",
                        )
                    )

                # queueLength for asynchronous client-server is intentionally not supported yet.
                if com_spec.callMode == "asynchronous" and com_spec.queueLength is not None:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' clientServer asynchronous comSpec queueLength is not yet supported.",
                            code="CORE-025-CS-COMSPEC-ASYNC-QUEUE-LENGTH-UNSUPPORTED",
                        )
                    )
                elif com_spec.queueLength is not None:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' clientServer comSpec must not define queueLength.",
                            code="CORE-025-CS-COMSPEC-QUEUE-LENGTH",
                        )
                    )

                if com_spec.timeoutMs is not None and com_spec.timeoutMs < 0:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' clientServer comSpec timeoutMs must be >= 0, found '{com_spec.timeoutMs}'.",
                            code="CORE-025-CS-COMSPEC-TIMEOUT-RANGE",
                        )
                    )

                if com_spec.callMode == "asynchronous" and com_spec.timeoutMs is not None:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' clientServer asynchronous comSpec must not define timeoutMs.",
                            code="CORE-025-CS-COMSPEC-ASYNC-TIMEOUT",
                        )
                    )

        return findings


class RunnableRaisedErrorCase(ValidationCase):
    case_id = "CORE-026"
    name = "RunnableRaisedErrors"
    description = "Checks runnable raisesErrors declarations for provided client-server operations."
    tags = ("core", "swc", "runnables", "interfaces", "errors")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        has_raises_errors = any(
            runnable.raisesErrors
            for swc in ctx.project.swcs
            for runnable in swc.runnables
        )
        if not has_raises_errors:
            return False, "no runnable raisesErrors declarations"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            provided_cs_ports: dict[str, object] = {}
            for port in sorted(swc.ports, key=lambda p: p.name):
                if port.direction != "provides":
                    continue
                itf = ctx.iface_by_name.get(port.interfaceRef)
                if itf is None or itf.type != "clientServer":
                    continue
                provided_cs_ports[port.name] = itf

            for runnable in sorted(swc.runnables, key=lambda r: r.name):
                if not runnable.raisesErrors:
                    continue

                location_base = f"SWC '{swc.name}' runnable '{runnable.name}'"
                valid_oie_bindings = {
                    (event.port, event.operation)
                    for event in runnable.operationInvokedEvents
                }

                for raised_error in sorted(runnable.raisesErrors, key=lambda e: (e.operation, e.error)):
                    candidate_ports = sorted(
                        [
                            (port_name, itf)
                            for port_name, itf in provided_cs_ports.items()
                            if raised_error.operation in ctx.cs_operations_by_iface.get(itf.name, set())
                        ],
                        key=lambda item: item[0],
                    )
                    if not candidate_ports:
                        findings.append(
                            self.finding(
                                f"{location_base} raisesErrors references unknown operation '{raised_error.operation}' on provided clientServer interfaces.",
                                code="CORE-026-RAISE-UNKNOWN-OPERATION",
                            )
                        )
                        continue

                    bound_ports = sorted(
                        [
                            (port_name, itf)
                            for port_name, itf in candidate_ports
                            if (port_name, raised_error.operation) in valid_oie_bindings
                        ],
                        key=lambda item: item[0],
                    )
                    if not bound_ports:
                        findings.append(
                            self.finding(
                                f"{location_base} raisesErrors operation '{raised_error.operation}' is not bound via operationInvokedEvents.",
                                code="CORE-026-RAISE-UNBOUND-OPERATION",
                            )
                        )
                        continue
                    if len(bound_ports) > 1:
                        bound_port_names = ", ".join(port_name for port_name, _ in bound_ports)
                        findings.append(
                            self.finding(
                                f"{location_base} raisesErrors operation '{raised_error.operation}' is ambiguous; bound on multiple provides ports: {bound_port_names}.",
                                code="CORE-026-RAISE-AMBIGUOUS-BINDING",
                            )
                        )
                        continue

                    _, interface_obj = bound_ports[0]
                    operation_obj = next(
                        (
                            op
                            for op in sorted(interface_obj.operations or [], key=lambda op: op.name)
                            if op.name == raised_error.operation
                        ),
                        None,
                    )
                    if operation_obj is None:
                        findings.append(
                            self.finding(
                                f"{location_base} raisesErrors references unknown operation '{raised_error.operation}' on interface '{interface_obj.name}'.",
                                code="CORE-026-RAISE-UNKNOWN-OPERATION",
                            )
                        )
                        continue
                    possible_error_names = {possible_error.name for possible_error in operation_obj.possibleErrors}
                    if raised_error.error not in possible_error_names:
                        findings.append(
                            self.finding(
                                f"{location_base} raisesErrors references unknown error '{raised_error.error}' for operation '{raised_error.operation}' on interface '{interface_obj.name}'.",
                                code="CORE-026-RAISE-UNKNOWN-ERROR",
                            )
                        )

        return findings


class DataReceiveEventCase(ValidationCase):
    case_id = "CORE-027"
    name = "DataReceiveEvents"
    description = "Checks dataReceiveEvents bindings for required sender-receiver ports."
    tags = ("core", "swc", "runnables", "interfaces")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.swcs:
            return False, "no SWCs defined"
        has_events = any(
            runnable.dataReceiveEvents
            for swc in ctx.project.swcs
            for runnable in swc.runnables
        )
        if not has_events:
            return False, "no dataReceiveEvents declarations"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            for runnable in sorted(swc.runnables, key=lambda r: r.name):
                if not runnable.dataReceiveEvents:
                    continue

                location_base = f"SWC '{swc.name}' runnable '{runnable.name}'"
                for event in sorted(runnable.dataReceiveEvents, key=lambda e: (e.port, e.dataElement)):
                    port = ctx.find_swc_port(swc.name, event.port)
                    if port is None:
                        findings.append(
                            self.finding(
                                f"{location_base} dataReceiveEvents references unknown port '{event.port}'.",
                                code="CORE-027-DRE-UNKNOWN-PORT",
                            )
                        )
                        continue
                    if port.direction != "requires":
                        findings.append(
                            self.finding(
                                f"{location_base} dataReceiveEvents on port '{event.port}' requires direction 'requires', found '{port.direction}'.",
                                code="CORE-027-DRE-DIRECTION",
                            )
                        )
                    itf = ctx.iface_by_name.get(port.interfaceRef)
                    if itf is None:
                        # Unknown interface reference is reported by CORE-021.
                        continue
                    if itf.type != "senderReceiver":
                        findings.append(
                            self.finding(
                                f"{location_base} dataReceiveEvents on port '{event.port}' requires senderReceiver interface, found '{itf.type}'.",
                                code="CORE-027-DRE-INTERFACE-TYPE",
                            )
                        )
                        continue
                    if event.dataElement not in ctx.sr_data_elements_by_iface.get(itf.name, set()):
                        findings.append(
                            self.finding(
                                f"{location_base} dataReceiveEvents references unknown dataElement '{event.dataElement}' on interface '{itf.name}'.",
                                code="CORE-027-DRE-UNKNOWN-DATAELEMENT",
                            )
                        )

        return findings


class ModeSwitchEventCase(ValidationCase):
    case_id = "CORE-028"
    name = "ModeSwitchEvents"
    description = "Checks modeSwitchEvents bindings for required mode-switch ports and declared modes."
    tags = ("core", "swc", "runnables", "interfaces", "mode-switch")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.swcs:
            return False, "no SWCs defined"
        has_events = any(
            runnable.modeSwitchEvents
            for swc in ctx.project.swcs
            for runnable in swc.runnables
        )
        if not has_events:
            return False, "no modeSwitchEvents declarations"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            for runnable in sorted(swc.runnables, key=lambda r: r.name):
                if not runnable.modeSwitchEvents:
                    continue

                location_base = f"SWC '{swc.name}' runnable '{runnable.name}'"
                for event in sorted(runnable.modeSwitchEvents, key=lambda e: (e.port, e.mode)):
                    port = ctx.find_swc_port(swc.name, event.port)
                    if port is None:
                        findings.append(
                            self.finding(
                                f"{location_base} modeSwitchEvents references unknown port '{event.port}'.",
                                code="CORE-028-MSE-UNKNOWN-PORT",
                            )
                        )
                        continue
                    if port.direction != "requires":
                        findings.append(
                            self.finding(
                                f"{location_base} modeSwitchEvents on port '{event.port}' requires direction 'requires', found '{port.direction}'.",
                                code="CORE-028-MSE-DIRECTION",
                            )
                        )
                    itf = ctx.iface_by_name.get(port.interfaceRef)
                    if itf is None:
                        continue
                    if itf.type != "modeSwitch":
                        findings.append(
                            self.finding(
                                f"{location_base} modeSwitchEvents on port '{event.port}' requires modeSwitch interface, found '{itf.type}'.",
                                code="CORE-028-MSE-INTERFACE-TYPE",
                            )
                        )
                        continue
                    if not itf.modeGroupRef:
                        findings.append(
                            self.finding(
                                f"{location_base} modeSwitchEvents on interface '{itf.name}' requires modeGroupRef.",
                                code="CORE-028-MSE-MISSING-MODE-GROUP",
                            )
                        )
                        continue
                    group = ctx.mode_declaration_group_by_name.get(itf.modeGroupRef)
                    if group is None:
                        findings.append(
                            self.finding(
                                f"{location_base} modeSwitchEvents interface '{itf.name}' references unknown ModeDeclarationGroup '{itf.modeGroupRef}'.",
                                code="CORE-028-MSE-UNKNOWN-MODE-GROUP",
                            )
                        )
                        continue
                    mode_names = {mode.name for mode in group.modes}
                    if event.mode not in mode_names:
                        findings.append(
                            self.finding(
                                f"{location_base} modeSwitchEvents references unknown mode '{event.mode}' on ModeDeclarationGroup '{group.name}'.",
                                code="CORE-028-MSE-UNKNOWN-MODE",
                            )
                        )

        return findings


class SystemInstanceTypeCase(ValidationCase):
    case_id = "CORE-030"
    name = "SystemInstanceTypes"
    description = "Checks that composition component prototypes reference known SWC types."
    tags = ("core", "system")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.components:
            return False, "no system component prototypes defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        for inst in sorted(ctx.project.system.composition.components, key=lambda c: c.name):
            if inst.typeRef not in ctx.swc_by_name:
                findings.append(
                    self.finding(
                        f"System component prototype '{inst.name}' references unknown SWC type '{inst.typeRef}'.",
                        code="CORE-030-UNKNOWN-SWC-TYPE",
                    )
                )
        return findings


def _connection_sort_key(conn) -> tuple[str, str, str, str, str, str]:
    return (
        conn.from_instance,
        conn.from_port,
        conn.to_instance,
        conn.to_port,
        conn.dataElement or "",
        conn.operation or "",
    )


class ConnectionSemanticCase(ValidationCase):
    case_id = "CORE-040"
    name = "ConnectionSemantics"
    description = "Checks system connections and connector-level sender-receiver, client-server, and mode-switch semantics."
    tags = ("core", "system", "connections")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.connectors:
            return False, "no system connectors defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        seen_sr_port_pairs: set[tuple[str, str, str, str]] = set()
        seen_cs_port_pairs: set[tuple[str, str, str, str]] = set()
        seen_ms_port_pairs: set[tuple[str, str, str, str]] = set()
        connectors = sorted(ctx.project.system.composition.connectors, key=_connection_sort_key)
        for conn in connectors:
            from_inst = ctx.instance_by_name.get(conn.from_instance)
            if from_inst is None:
                findings.append(
                    self.finding(
                        f"Connection references unknown from instance '{conn.from_instance}'.",
                        code="CORE-040-UNKNOWN-FROM-INSTANCE",
                    )
                )
                continue

            to_inst = ctx.instance_by_name.get(conn.to_instance)
            if to_inst is None:
                findings.append(
                    self.finding(
                        f"Connection references unknown to instance '{conn.to_instance}'.",
                        code="CORE-040-UNKNOWN-TO-INSTANCE",
                    )
                )
                continue

            from_swc = ctx.swc_by_name.get(from_inst.typeRef)
            to_swc = ctx.swc_by_name.get(to_inst.typeRef)
            if from_swc is None or to_swc is None:
                # Missing instance.typeRef issues are reported by CORE-030.
                continue

            from_port = ctx.find_swc_port(from_swc.name, conn.from_port)
            to_port = ctx.find_swc_port(to_swc.name, conn.to_port)

            if from_port is None:
                findings.append(
                    self.finding(
                        f"Connection from '{conn.from_instance}.{conn.from_port}' references unknown port on type '{from_swc.name}'.",
                        code="CORE-040-UNKNOWN-FROM-PORT",
                    )
                )
                continue
            if to_port is None:
                findings.append(
                    self.finding(
                        f"Connection to '{conn.to_instance}.{conn.to_port}' references unknown port on type '{to_swc.name}'.",
                        code="CORE-040-UNKNOWN-TO-PORT",
                    )
                )
                continue

            if from_port.direction != "provides":
                findings.append(
                    self.finding(
                        f"Connection from '{conn.from_instance}.{conn.from_port}' must be a provides-port.",
                        code="CORE-040-FROM-DIRECTION",
                    )
                )
            if to_port.direction != "requires":
                findings.append(
                    self.finding(
                        f"Connection to '{conn.to_instance}.{conn.to_port}' must be a requires-port.",
                        code="CORE-040-TO-DIRECTION",
                    )
                )

            if from_port.interfaceRef != to_port.interfaceRef:
                findings.append(
                    self.finding(
                        f"Connection interface mismatch: '{conn.from_instance}.{conn.from_port}' uses '{from_port.interfaceRef}' but "
                        f"'{conn.to_instance}.{conn.to_port}' uses '{to_port.interfaceRef}'.",
                        code="CORE-040-INTERFACE-MISMATCH",
                    )
                )
                continue

            itf = ctx.iface_by_name.get(from_port.interfaceRef)
            if not itf:
                # Unknown interface reference issues are reported by CORE-021.
                continue

            if conn.dataElement and conn.operation:
                findings.append(
                    self.finding(
                        f"Connection {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} must not define both dataElement and operation.",
                        code="CORE-040-MULTIPLE-SELECTORS",
                    )
                )
                continue

            if itf.type == "senderReceiver":
                if conn.operation:
                    findings.append(
                        self.finding(
                            f"SenderReceiver connection {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} cannot set operation.",
                            code="CORE-040-SR-INVALID-OPERATION",
                        )
                    )
                if conn.port_pair_key in seen_sr_port_pairs:
                    findings.append(
                        self.finding(
                            f"Duplicate senderReceiver connector '{conn.from_instance}.{conn.from_port}' -> "
                            f"'{conn.to_instance}.{conn.to_port}' is not allowed; SR connectors are unique per port pair.",
                            code="CORE-040-SR-DUPLICATE-PORT-PAIR",
                        )
                    )
                else:
                    seen_sr_port_pairs.add(conn.port_pair_key)
            elif itf.type == "clientServer":
                if from_port.interfaceType != "clientServer" or to_port.interfaceType != "clientServer":
                    findings.append(
                        self.finding(
                            f"ClientServer connector {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} "
                            "must connect ports typed by clientServer interfaces.",
                            code="CORE-040-CS-INTERFACE-TYPE",
                        )
                    )
                if conn.dataElement:
                    findings.append(
                        self.finding(
                            f"ClientServer connection {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} cannot set dataElement.",
                            code="CORE-040-CS-INVALID-DATAELEMENT",
                        )
                    )
                if conn.port_pair_key in seen_cs_port_pairs:
                    findings.append(
                        self.finding(
                            f"Duplicate clientServer connector '{conn.from_instance}.{conn.from_port}' -> "
                            f"'{conn.to_instance}.{conn.to_port}' is not allowed; C/S connectors are unique per port pair.",
                            code="CORE-040-CS-DUPLICATE-PORT-PAIR",
                        )
                    )
                else:
                    seen_cs_port_pairs.add(conn.port_pair_key)
                if conn.operation:
                    findings.append(
                        self.finding(
                            f"ClientServer connector {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} "
                            "must not set operation; C/S connectors are port-level and operation usage belongs in runnable behavior.",
                            code="CORE-040-CS-INVALID-OPERATION",
                        )
                    )
            elif itf.type == "modeSwitch":
                if from_port.interfaceType != "modeSwitch" or to_port.interfaceType != "modeSwitch":
                    findings.append(
                        self.finding(
                            f"ModeSwitch connector {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} "
                            "must connect ports typed by modeSwitch interfaces.",
                            code="CORE-040-MS-INTERFACE-TYPE",
                        )
                    )
                if conn.dataElement:
                    findings.append(
                        self.finding(
                            f"ModeSwitch connection {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} cannot set dataElement.",
                            code="CORE-040-MS-INVALID-DATAELEMENT",
                        )
                    )
                if conn.port_pair_key in seen_ms_port_pairs:
                    findings.append(
                        self.finding(
                            f"Duplicate modeSwitch connector '{conn.from_instance}.{conn.from_port}' -> "
                            f"'{conn.to_instance}.{conn.to_port}' is not allowed; mode-switch connectors are unique per port pair.",
                            code="CORE-040-MS-DUPLICATE-PORT-PAIR",
                        )
                    )
                else:
                    seen_ms_port_pairs.add(conn.port_pair_key)
                if conn.operation:
                    findings.append(
                        self.finding(
                            f"ModeSwitch connector {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} must not set operation.",
                            code="CORE-040-MS-INVALID-OPERATION",
                        )
                    )
            else:
                findings.append(
                    self.finding(
                        f"Connection {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} uses unsupported interface type '{itf.type}'.",
                        code="CORE-040-UNKNOWN-INTERFACE-TYPE",
                    )
                )

        return findings


class CsPortConnectivityCase(ValidationCase):
    case_id = "CORE-043"
    name = "ClientServerConnectivity"
    description = "Checks client-server port connectivity against instantiated components and runnable behavior."
    tags = ("core", "system", "connections", "runnables", "client-server")
    default_severity = "error"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.components:
            return False, "no system component prototypes defined"
        has_cs_ports = any(
            port.interfaceType == "clientServer"
            for swc in ctx.project.swcs
            for port in swc.ports
        )
        if not has_cs_ports:
            return False, "no clientServer ports defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        for instance in sorted(ctx.project.system.composition.components, key=lambda c: c.name):
            swc = ctx.swc_by_name.get(instance.typeRef)
            if swc is None:
                continue

            for port in sorted(swc.ports, key=lambda p: p.name):
                if port.interfaceType != "clientServer":
                    continue

                connectivity = ctx.find_instance_port_connectivity(instance.name, port.name)
                if connectivity is None:
                    continue
                usage = ctx.find_swc_port_usage(swc.name, port.name)

                for runnable_name, operation in usage.calls:
                    if not connectivity.incoming_connectors:
                        findings.append(
                            self.finding(
                                f"SWC instance '{instance.name}' runnable '{runnable_name}' calls operation '{operation}' "
                                f"through unconnected clientServer requires port '{port.name}'.",
                                code="CORE-043-CS-CALL-UNCONNECTED",
                            )
                        )

                for runnable_name, operation in usage.operation_invoked_events:
                    if not connectivity.outgoing_connectors:
                        findings.append(
                            self.finding(
                                f"SWC instance '{instance.name}' runnable '{runnable_name}' operationInvokedEvents waits on operation "
                                f"'{operation}' from unconnected clientServer provides port '{port.name}'.",
                                code="CORE-043-CS-OIE-UNCONNECTED",
                            )
                        )

                for runnable_name, operation, error_name in usage.raises_errors:
                    if not connectivity.outgoing_connectors:
                        findings.append(
                            self.finding(
                                f"SWC instance '{instance.name}' runnable '{runnable_name}' raises error '{error_name}' for operation "
                                f"'{operation}' on unconnected clientServer provides port '{port.name}'.",
                                code="CORE-043-CS-RAISE-UNCONNECTED",
                            )
                        )

        return findings


class CsPortUsageCase(ValidationCase):
    case_id = "CORE-044"
    name = "ClientServerUsage"
    description = "Checks whether connected client-server ports are actually used by runnable behavior."
    tags = ("core", "system", "connections", "runnables", "client-server")
    default_severity = "warning"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.components:
            return False, "no system component prototypes defined"
        has_cs_ports = any(
            port.interfaceType == "clientServer"
            for swc in ctx.project.swcs
            for port in swc.ports
        )
        if not has_cs_ports:
            return False, "no clientServer ports defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for instance in sorted(ctx.project.system.composition.components, key=lambda c: c.name):
            swc = ctx.swc_by_name.get(instance.typeRef)
            if swc is None:
                continue

            for port in sorted(swc.ports, key=lambda p: p.name):
                if port.interfaceType != "clientServer":
                    continue

                connectivity = ctx.find_instance_port_connectivity(instance.name, port.name)
                if connectivity is None:
                    continue
                usage = ctx.find_swc_port_usage(swc.name, port.name)

                if port.direction == "provides" and not connectivity.outgoing_connectors:
                    findings.append(
                        self.finding(
                            f"ClientServer provides port '{instance.name}.{port.name}' has no connector.",
                            code="CORE-044-CS-PROVIDES-NO-CONNECTOR",
                        )
                    )
                if port.direction == "requires" and not connectivity.incoming_connectors:
                    findings.append(
                        self.finding(
                            f"ClientServer requires port '{instance.name}.{port.name}' has no connector.",
                            code="CORE-044-CS-REQUIRES-NO-CONNECTOR",
                        )
                    )

                if not connectivity.is_connected:
                    continue

                if port.direction == "provides" and not usage.operation_invoked_events:
                    findings.append(
                        self.finding(
                            f"Connected clientServer provides port '{instance.name}.{port.name}' is never used by any runnable operationInvokedEvent.",
                            code="CORE-044-CS-CONNECTED-PROVIDES-UNUSED",
                        )
                    )
                if port.direction == "requires" and not usage.calls:
                    findings.append(
                        self.finding(
                            f"Connected clientServer requires port '{instance.name}.{port.name}' is never used by any runnable call.",
                            code="CORE-044-CS-CONNECTED-REQUIRES-UNUSED",
                        )
                    )

        return findings


class ModeSwitchConnectivityCase(ValidationCase):
    case_id = "CORE-045"
    name = "ModeSwitchConnectivity"
    description = "Checks mode-switch instantiated-port connectivity against connectors."
    tags = ("core", "system", "connections", "mode-switch")
    default_severity = "warning"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.components:
            return False, "no system component prototypes defined"
        has_mode_switch_ports = any(
            port.interfaceType == "modeSwitch"
            for swc in ctx.project.swcs
            for port in swc.ports
        )
        if not has_mode_switch_ports:
            return False, "no modeSwitch ports defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for instance in sorted(ctx.project.system.composition.components, key=lambda c: c.name):
            swc = ctx.swc_by_name.get(instance.typeRef)
            if swc is None:
                continue

            for port in sorted(swc.ports, key=lambda p: p.name):
                if port.interfaceType != "modeSwitch":
                    continue

                port_ref = f"{instance.name}.{port.name}"
                connectivity = ctx.find_instance_port_connectivity(instance.name, port.name)
                if connectivity is None:
                    continue

                if port.direction == "provides" and not connectivity.outgoing_connectors:
                    findings.append(
                        self.finding(
                            f"ModeSwitch provides port '{port_ref}' has no outgoing connector.",
                            code="CORE-045-MS-PROVIDES-NO-OUTGOING",
                        )
                    )
                if port.direction == "requires" and not connectivity.incoming_connectors:
                    findings.append(
                        self.finding(
                            f"ModeSwitch requires port '{port_ref}' has no incoming connector.",
                            code="CORE-045-MS-REQUIRES-NO-INCOMING",
                        )
                    )

        return findings


class DeclaredPortUsageCase(ValidationCase):
    case_id = "CORE-046"
    name = "DeclaredPortUsage"
    description = "Checks whether declared SWC ports are ever used by runnable behavior, even before system connectors exist."
    tags = ("core", "swc", "runnables", "usage", "analysis")
    default_severity = "warning"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        has_relevant_ports = any(
            port.interfaceType in {"senderReceiver", "clientServer", "modeSwitch"}
            for swc in ctx.project.swcs
            for port in swc.ports
        )
        if not has_relevant_ports:
            return False, "no senderReceiver, clientServer, or modeSwitch ports defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            for declared_usage in ctx.iter_declared_port_usage(swc.name):
                port = declared_usage.port
                usage = declared_usage.usage
                port_ref = f"{swc.name}.{port.name}"

                if port.interfaceType == "senderReceiver":
                    if port.direction == "provides" and not usage.writes:
                        findings.append(
                            self.finding(
                                f"SenderReceiver provides port '{port_ref}' is declared but no runnable writes to it.",
                                code="CORE-046-SR-PROVIDES-DECLARED-UNUSED",
                            )
                        )
                    if port.direction == "requires" and not usage.reads and not usage.data_receive_events:
                        findings.append(
                            self.finding(
                                f"SenderReceiver requires port '{port_ref}' is declared but no runnable reads from it and no dataReceiveEvent references it.",
                                code="CORE-046-SR-REQUIRES-DECLARED-UNUSED",
                            )
                        )
                    continue

                if port.interfaceType == "clientServer":
                    if port.direction == "requires" and not usage.calls:
                        findings.append(
                            self.finding(
                                f"ClientServer requires port '{port_ref}' is declared but no runnable call uses it.",
                                code="CORE-046-CS-REQUIRES-DECLARED-UNUSED",
                            )
                        )
                    if port.direction == "provides" and not usage.operation_invoked_events:
                        findings.append(
                            self.finding(
                                f"ClientServer provides port '{port_ref}' is declared but no runnable operationInvokedEvent binds any exposed operation on it.",
                                code="CORE-046-CS-PROVIDES-DECLARED-UNUSED",
                            )
                        )
                    continue

                if port.interfaceType == "modeSwitch" and port.direction == "requires" and not usage.mode_switch_events:
                    findings.append(
                        self.finding(
                            f"ModeSwitch requires port '{port_ref}' is declared but no runnable modeSwitchEvents uses it.",
                            code="CORE-046-MS-REQUIRES-DECLARED-UNUSED",
                        )
                    )
                # Provider-side mode behavior is not modeled in ARForge yet, so we intentionally
                # skip a declared-but-unused check for modeSwitch provides ports here.

        return findings


class SrPortConnectivityCase(ValidationCase):
    case_id = "CORE-041"
    name = "SenderReceiverConnectivity"
    description = "Checks sender-receiver port connectivity against instantiated components and runnable behavior."
    tags = ("core", "system", "connections", "runnables", "sender-receiver")
    default_severity = "error"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.components:
            return False, "no system component prototypes defined"
        has_sr_ports = any(
            port.interfaceType == "senderReceiver"
            for swc in ctx.project.swcs
            for port in swc.ports
        )
        if not has_sr_ports:
            return False, "no senderReceiver ports defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for instance in sorted(ctx.project.system.composition.components, key=lambda c: c.name):
            swc = ctx.swc_by_name.get(instance.typeRef)
            if swc is None:
                continue

            for port in sorted(swc.ports, key=lambda p: p.name):
                if port.interfaceType != "senderReceiver":
                    continue

                port_ref = f"{instance.name}.{port.name}"
                connectivity = ctx.find_instance_port_connectivity(instance.name, port.name)
                if connectivity is None:
                    continue
                usage = ctx.find_swc_port_usage(swc.name, port.name)

                if port.direction == "provides" and not connectivity.outgoing_connectors:
                    findings.append(
                        self.finding(
                            f"SenderReceiver provides port '{port_ref}' has no outgoing connector.",
                            code="CORE-041-SR-PROVIDES-NO-OUTGOING",
                            severity="warning",
                        )
                    )
                if port.direction == "requires" and not connectivity.incoming_connectors:
                    findings.append(
                        self.finding(
                            f"SenderReceiver requires port '{port_ref}' has no incoming connector.",
                            code="CORE-041-SR-REQUIRES-NO-INCOMING",
                            severity="warning",
                        )
                    )

                for runnable_name, data_element in usage.reads:
                    if not connectivity.incoming_connectors:
                        findings.append(
                            self.finding(
                                f"SWC instance '{instance.name}' runnable '{runnable_name}' reads dataElement '{data_element}' "
                                f"from unconnected senderReceiver requires port '{port.name}'.",
                                code="CORE-041-SR-READ-UNCONNECTED",
                            )
                        )

                for runnable_name, data_element in usage.data_receive_events:
                    if not connectivity.incoming_connectors:
                        findings.append(
                            self.finding(
                                f"SWC instance '{instance.name}' runnable '{runnable_name}' dataReceiveEvents waits on dataElement "
                                f"'{data_element}' from unconnected senderReceiver requires port '{port.name}'.",
                                code="CORE-041-SR-DRE-UNCONNECTED",
                            )
                        )

                for runnable_name, data_element in usage.writes:
                    if not connectivity.outgoing_connectors:
                        findings.append(
                            self.finding(
                                f"SWC instance '{instance.name}' runnable '{runnable_name}' writes dataElement '{data_element}' "
                                f"to unconnected senderReceiver provides port '{port.name}'.",
                                code="CORE-041-SR-WRITE-UNCONNECTED",
                            )
                        )

        return findings


class SrPortUsageCase(ValidationCase):
    case_id = "CORE-042"
    name = "SenderReceiverUsage"
    description = "Checks whether connected sender-receiver ports are actually used by runnable behavior."
    tags = ("core", "system", "connections", "runnables", "sender-receiver")
    default_severity = "warning"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.connectors:
            return False, "no system connectors defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for instance in sorted(ctx.project.system.composition.components, key=lambda c: c.name):
            swc = ctx.swc_by_name.get(instance.typeRef)
            if swc is None:
                continue

            for port in sorted(swc.ports, key=lambda p: p.name):
                if port.interfaceType != "senderReceiver":
                    continue

                connectivity = ctx.find_instance_port_connectivity(instance.name, port.name)
                if connectivity is None or not connectivity.is_connected:
                    continue
                usage = ctx.find_swc_port_usage(swc.name, port.name)

                if port.direction == "provides" and not usage.writes:
                    findings.append(
                        self.finding(
                            f"Connected senderReceiver provides port '{instance.name}.{port.name}' is never used by any runnable write.",
                            code="CORE-042-SR-CONNECTED-PROVIDES-UNUSED",
                        )
                    )
                if port.direction == "requires" and not usage.reads and not usage.data_receive_events:
                    findings.append(
                        self.finding(
                            f"Connected senderReceiver requires port '{instance.name}.{port.name}' is never used by any runnable read or dataReceiveEvent.",
                            code="CORE-042-SR-CONNECTED-REQUIRES-UNUSED",
                        )
                    )

        return findings


class SrConsumerFasterThanProducerCase(ValidationCase):
    case_id = "CORE-050"
    name = "SRConsumerFasterThanProducer"
    description = "Warns when a cyclic sender-receiver consumer runs faster than its cyclic producer."
    tags = ("core", "system", "connections", "runnables", "sender-receiver", "timing", "analysis")
    default_severity = "warning"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.connectors:
            return False, "no system connectors defined"
        has_sr_connector = any(
            ctx.find_swc_port(provider_swc.name, connector.from_port) is not None
            and ctx.find_swc_port(consumer_swc.name, connector.to_port) is not None
            and ctx.find_swc_port(provider_swc.name, connector.from_port).interfaceType == "senderReceiver"
            and ctx.find_swc_port(consumer_swc.name, connector.to_port).interfaceType == "senderReceiver"
            for connector in ctx.project.system.composition.connectors
            for provider_swc in [ctx.find_instance_swc(connector.from_instance)]
            for consumer_swc in [ctx.find_instance_swc(connector.to_instance)]
            if provider_swc is not None and consumer_swc is not None
        )
        if not has_sr_connector:
            return False, "no senderReceiver connectors defined"
        if not ctx.sr_timing_communications:
            return False, "no cyclic senderReceiver producer/consumer timing pairs found"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for communication in ctx.sr_timing_communications:
            if communication.consumer_period_ms >= communication.producer_period_ms:
                continue
            findings.append(
                self.finding(
                    f"Consumer runnable '{communication.consumer_runnable_name}' in SWC '{communication.consumer_swc_name}' "
                    f"({communication.consumer_period_ms} ms) reads from port '{communication.consumer_port_name}' faster than "
                    f"producer '{communication.provider_runnable_name}' in SWC '{communication.provider_swc_name}' "
                    f"({communication.producer_period_ms} ms). Data may be stale.",
                )
            )

        return findings


class SrProducerFasterThanConsumerCase(ValidationCase):
    case_id = "CORE-051"
    name = "SRProducerFasterThanConsumer"
    description = "Warns when a cyclic sender-receiver producer runs faster than its cyclic consumer."
    tags = ("core", "system", "connections", "runnables", "sender-receiver", "timing", "analysis")
    default_severity = "warning"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        consumer_case = SrConsumerFasterThanProducerCase()
        return consumer_case.applicability(ctx)

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for communication in ctx.sr_timing_communications:
            if communication.producer_period_ms >= communication.consumer_period_ms:
                continue
            findings.append(
                self.finding(
                    f"Producer runnable '{communication.provider_runnable_name}' in SWC '{communication.provider_swc_name}' "
                    f"({communication.producer_period_ms} ms) writes to port '{communication.provider_port_name}' faster than "
                    f"consumer '{communication.consumer_runnable_name}' in SWC '{communication.consumer_swc_name}' "
                    f"({communication.consumer_period_ms} ms). Intermediate values may be overwritten before consumption.",
                )
            )

        return findings


def core_validation_cases() -> List[ValidationCase]:
    return [
        DuplicateNameCase(),
        BaseTypeMetadataCase(),
        InterfaceSemanticCase(),
        ModeDeclarationGroupStructureCase(),
        ModeDeclarationGroupInitialModeCase(),
        ApplicationConstraintCase(),
        SwcStructureCase(),
        SwcPortInterfaceCase(),
        RunnableAccessSemanticCase(),
        OperationInvokedEventCase(),
        RunnableTriggerPolicyCase(),
        ComSpecSemanticCase(),
        RunnableRaisedErrorCase(),
        DataReceiveEventCase(),
        ModeSwitchEventCase(),
        SystemInstanceTypeCase(),
        ConnectionSemanticCase(),
        SrPortConnectivityCase(),
        SrPortUsageCase(),
        CsPortConnectivityCase(),
        CsPortUsageCase(),
        ModeSwitchConnectivityCase(),
        DeclaredPortUsageCase(),
        SrConsumerFasterThanProducerCase(),
        SrProducerFasterThanConsumerCase(),
    ]
