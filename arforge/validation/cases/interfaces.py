"""Interface and datatype-reference validation cases.

This module groups the structural rules that validate interfaces, implementation
types, application types, and related datatype references used by interfaces.
"""

from __future__ import annotations

from typing import List

from ...semantic_validation import Finding, ValidationCase, ValidationContext


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
