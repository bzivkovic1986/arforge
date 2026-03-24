"""Connectivity and usage validation cases for instantiated ports.

This module contains rules that reason about system connectors together with
runtime port usage, including sender-receiver, client-server, and mode-switch
connectivity diagnostics.
"""

from __future__ import annotations

from typing import List

from ...semantic_validation import Finding, ValidationCase, ValidationContext


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
                                severity="warning",
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
            mode_switch_requires_analysis = {
                analysis.port.name: analysis
                for analysis in ctx.iter_mode_switch_requires_port_analysis(swc.name)
            }
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

                if port.interfaceType == "modeSwitch" and port.direction == "requires":
                    analysis = mode_switch_requires_analysis.get(port.name)
                    if analysis is None or analysis.usage.mode_switch_events:
                        continue
                    findings.append(
                        self.finding(
                            f"ModeSwitch requires port '{port_ref}' is declared but no runnable modeSwitchEvents uses it.",
                            code="CORE-046-MS-REQUIRES-DECLARED-UNUSED",
                        )
                    )
                # Provider-side mode behavior is not modeled in ARForge yet, so we intentionally
                # skip a declared-but-unused check for modeSwitch provides ports here.

        return findings


class ModeSwitchUsageCase(ValidationCase):
    case_id = "CORE-047"
    name = "ModeSwitchUsage"
    description = "Checks whether connected mode-switch requires ports are actually used by runnable modeSwitchEvents."
    tags = ("core", "system", "connections", "runnables", "mode-switch", "usage")
    default_severity = "warning"

    def applicability(self, ctx: ValidationContext) -> tuple[bool, str | None]:
        if not ctx.project.system.composition.connectors:
            return False, "no system connectors defined"
        has_mode_switch_requires_ports = any(
            ctx.iter_mode_switch_requires_port_analysis(swc.name)
            for swc in ctx.project.swcs
        )
        if not has_mode_switch_requires_ports:
            return False, "no modeSwitch requires ports defined"
        return True, None

    def run(self, ctx: ValidationContext) -> List[Finding]:
        findings: List[Finding] = []

        for swc in sorted(ctx.project.swcs, key=lambda s: s.name):
            for analysis in ctx.iter_mode_switch_requires_port_analysis(swc.name):
                if analysis.usage.mode_switch_events:
                    continue

                for connectivity in analysis.connected_instances:
                    findings.append(
                        self.finding(
                            f"Connected modeSwitch requires port '{connectivity.instance_name}.{analysis.port.name}' "
                            "is not used by any runnable modeSwitchEvents.",
                            code="CORE-047-MS-CONNECTED-REQUIRES-UNUSED",
                        )
                    )

        return findings
