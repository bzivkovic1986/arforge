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

        if len({d.name for d in project.datatypes}) != len(project.datatypes):
            findings.append(self.finding("Duplicate datatype names found.", code="CORE-001-DATATYPE-DUPLICATE"))
        if len({i.name for i in project.interfaces}) != len(project.interfaces):
            findings.append(self.finding("Duplicate interface names found.", code="CORE-001-INTERFACE-DUPLICATE"))
        if len({s.name for s in project.swcs}) != len(project.swcs):
            findings.append(self.finding("Duplicate SWC names found.", code="CORE-001-SWC-DUPLICATE"))
        if len({i.name for i in project.system.instances}) != len(project.system.instances):
            findings.append(self.finding("System has duplicate instance names.", code="CORE-001-INSTANCE-DUPLICATE"))

        return findings


class InterfaceSemanticCase(ValidationCase):
    case_id = "CORE-010"
    description = "Validate interface structure and datatype references."
    tags = ("core", "interfaces")

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        dt_names = set(ctx.datatype_by_name.keys())

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
                findings.append(
                    self.finding(
                        f"Unknown interface type '{itf.type}' on '{itf.name}'.",
                        code="CORE-010-UNKNOWN-INTERFACE-TYPE",
                    )
                )

        return findings


class SwcStructureCase(ValidationCase):
    case_id = "CORE-020"
    description = "Validate SWC internal uniqueness constraints."
    tags = ("core", "swc")

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


class SystemInstanceTypeCase(ValidationCase):
    case_id = "CORE-030"
    description = "Validate system instances reference known SWC types."
    tags = ("core", "system")

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        for inst in ctx.project.system.instances:
            if inst.typeRef not in ctx.swc_by_name:
                findings.append(
                    self.finding(
                        f"System instance '{inst.name}' references unknown SWC type '{inst.typeRef}'.",
                        code="CORE-030-UNKNOWN-SWC-TYPE",
                    )
                )
        return findings


class ConnectionSemanticCase(ValidationCase):
    case_id = "CORE-040"
    description = "Validate system connections and selector compatibility."
    tags = ("core", "system", "connections")

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []
        for conn in ctx.project.system.connections:
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
        InterfaceSemanticCase(),
        SwcStructureCase(),
        SwcPortInterfaceCase(),
        SystemInstanceTypeCase(),
        ConnectionSemanticCase(),
    ]
