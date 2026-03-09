from __future__ import annotations

from typing import List

from .semantic_validation import Finding, ValidationCase, ValidationContext


class DuplicateNameCase(ValidationCase):
    case_id = "CORE-001"
    description = "Check global uniqueness constraints."
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
    description = "Validate base type metadata and per-base-type uniqueness."
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
    description = "Validate interface structure and datatype references."
    tags = ("core", "interfaces")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.interfaces:
            return False, "no interfaces defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        dt_names = set(ctx.datatype_by_name.keys())

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
                if len(set(field_names)) != len(field_names):
                    findings.append(
                        self.finding(
                            f"Struct ImplementationDataType '{impl.name}' has duplicate field names.",
                            code="CORE-010-STRUCT-DUPLICATE-FIELD",
                        )
                    )
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

        impl_by_name = {i.name: i for i in ctx.project.implementationDataTypes}

        def _detect_impl_cycle(start: str, node: str, visiting: set[str], path: list[str]) -> list[str] | None:
            if node in visiting:
                cycle_start = path.index(node) if node in path else 0
                return path[cycle_start:] + [node]
            it = impl_by_name.get(node)
            if it is None or not it.is_struct:
                return None
            visiting.add(node)
            path.append(node)
            for f in sorted(it.fields, key=lambda x: x.name):
                if f.typeRef in impl_by_name:
                    cycle = _detect_impl_cycle(start, f.typeRef, visiting, path)
                    if cycle:
                        return cycle
            path.pop()
            visiting.remove(node)
            return None

        reported_cycles: set[str] = set()
        for impl in sorted(ctx.project.implementationDataTypes, key=lambda d: d.name):
            if not impl.is_struct:
                continue
            cycle = _detect_impl_cycle(impl.name, impl.name, set(), [])
            if cycle:
                cycle_txt = " -> ".join(cycle)
                cycle_key = "->".join(sorted(set(cycle[:-1])))
                if cycle_key in reported_cycles:
                    continue
                reported_cycles.add(cycle_key)
                findings.append(
                    self.finding(
                        f"Struct type cycle detected: {cycle_txt}.",
                        code="CORE-010-STRUCT-CYCLE",
                    )
                )

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

                        if any(possible_error.code is None for possible_error in op.possibleErrors):
                            findings.append(
                                Finding(
                                    code="CORE-010-CS-POSSIBLE-ERROR-LEGACY-FORMAT",
                                    severity="warning",
                                    message=(
                                        f"Interface '{itf.name}' operation '{op.name}' uses legacy possibleErrors string entries; "
                                        "prefer structured entries with {name, code}."
                                    ),
                                )
                            )

                        seen_error_names: set[str] = set()
                        seen_error_codes: set[int] = set()
                        for possible_error in sorted(
                            op.possibleErrors,
                            key=lambda e: (e.name, e.code is None, -1 if e.code is None else e.code),
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
            else:
                findings.append(
                    self.finding(
                        f"Unknown interface type '{itf.type}' on '{itf.name}'.",
                        code="CORE-010-UNKNOWN-INTERFACE-TYPE",
                    )
                )

        return findings


class ApplicationConstraintCase(ValidationCase):
    case_id = "CORE-011"
    description = "Validate ApplicationDataType constraint ranges and compatibility with implementation types."
    tags = ("core", "types", "constraints")

    _LEGACY_INTEGER_BASE_METADATA = {
        "uint8": {"bitLength": 8, "signedness": "unsigned"},
        "uint16": {"bitLength": 16, "signedness": "unsigned"},
    }
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

        legacy = self._LEGACY_INTEGER_BASE_METADATA.get(base_type_name.lower())
        if legacy is None:
            return None
        return legacy["bitLength"], legacy["signedness"]

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

            if impl.is_struct or (impl.kind is not None and impl.kind != "struct"):
                findings.append(
                    self.finding(
                        f"ApplicationDataType '{app.name}' uses implementation type '{impl.name}' of kind '{impl.kind or 'struct'}'; constraints are only allowed for scalar numeric implementation types in v0.",
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
    description = "Validate SWC internal uniqueness constraints."
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
    description = "Validate SWC ports against interface model."
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
    description = "Validate runnable reads/writes/calls against SWC port and interface semantics."
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

                for call in sorted(runnable.calls, key=lambda a: (a.port, a.operation)):
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

        return findings


class OperationInvokedEventCase(ValidationCase):
    case_id = "CORE-023"
    description = "Validate operation-invoked event bindings for provided clientServer operations."
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
    description = "Enforce runnable trigger policy: exactly one trigger style per runnable."
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
                if has_timing and has_oie:
                    findings.append(
                        self.finding(
                            f"Runnable '{runnable.name}' must not define timingEventMs when operationInvokedEvents is used.",
                            code="CORE-024-MULTIPLE-TRIGGERS",
                        )
                    )
                if not has_timing and not has_oie:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' runnable '{runnable.name}' must define at least one trigger: timingEventMs or operationInvokedEvents.",
                            code="CORE-024-MISSING-TRIGGER",
                        )
                    )
        return findings


class ComSpecSemanticCase(ValidationCase):
    case_id = "CORE-025"
    description = "Validate sender-receiver and client-server ComSpec on SWC ports."
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
                if com_spec.queueLength is not None:
                    findings.append(
                        self.finding(
                            f"SWC '{swc.name}' port '{port.name}' clientServer comSpec must not define queueLength.",
                            code="CORE-025-CS-COMSPEC-QUEUE-LENGTH",
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
    description = "Validate runnable raisesErrors declarations for provided clientServer operations."
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


class SystemInstanceTypeCase(ValidationCase):
    case_id = "CORE-030"
    description = "Validate composition component prototypes reference known SWC types."
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


class ConnectionSemanticCase(ValidationCase):
    case_id = "CORE-040"
    description = "Validate system connections and selector compatibility."
    tags = ("core", "system", "connections")

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.connectors:
            return False, "no system connectors defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        connectors = sorted(
            ctx.project.system.composition.connectors,
            key=lambda c: (
                c.from_instance,
                c.from_port,
                c.to_instance,
                c.to_port,
                c.dataElement or "",
                c.operation or "",
            ),
        )
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
                data_elements = ctx.sr_data_elements_by_iface.get(itf.name, set())
                if not conn.dataElement:
                    findings.append(
                        self.finding(
                            "SR connector must specify dataElement (required by arforge policy).",
                            code="CORE-040-SR-MISSING-DATAELEMENT",
                        )
                    )
                if conn.dataElement and conn.dataElement not in data_elements:
                    findings.append(
                        self.finding(
                            f"Connection dataElement '{conn.dataElement}' not found in interface '{itf.name}'.",
                            code="CORE-040-SR-UNKNOWN-DATAELEMENT",
                        )
                    )
            else:
                if conn.dataElement:
                    findings.append(
                        self.finding(
                            f"ClientServer connection {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} cannot set dataElement.",
                            code="CORE-040-CS-INVALID-DATAELEMENT",
                        )
                    )
                operations = ctx.cs_operations_by_iface.get(itf.name, set())
                if not conn.operation:
                    findings.append(
                        self.finding(
                            f"ClientServer connector {conn.from_instance}.{conn.from_port} -> {conn.to_instance}.{conn.to_port} must set operation.",
                            code="CORE-040-CS-MISSING-OPERATION",
                        )
                    )
                if conn.operation and conn.operation not in operations:
                    findings.append(
                        self.finding(
                            f"Connection operation '{conn.operation}' not found in interface '{itf.name}'.",
                            code="CORE-040-CS-UNKNOWN-OPERATION",
                        )
                    )

        return findings


def core_validation_cases() -> List[ValidationCase]:
    return [
        DuplicateNameCase(),
        BaseTypeMetadataCase(),
        InterfaceSemanticCase(),
        ApplicationConstraintCase(),
        SwcStructureCase(),
        SwcPortInterfaceCase(),
        RunnableAccessSemanticCase(),
        OperationInvokedEventCase(),
        RunnableTriggerPolicyCase(),
        ComSpecSemanticCase(),
        RunnableRaisedErrorCase(),
        SystemInstanceTypeCase(),
        ConnectionSemanticCase(),
    ]
