"""SWC-local validation cases for ports, runnables, events, and ComSpec.

This module groups checks that are primarily evaluated within a software
component definition before instantiated system connectivity is considered.
"""

from __future__ import annotations

from typing import List

from ...semantic_validation import Finding, ValidationCase, ValidationContext


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
