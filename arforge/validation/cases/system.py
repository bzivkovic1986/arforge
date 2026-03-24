"""System composition and connector semantic validation cases.

This module contains rules that validate component prototype references and the
core semantics of connectors declared in the system composition.
"""

from __future__ import annotations

from typing import List

from ...semantic_validation import Finding, ValidationCase, ValidationContext


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
