"""Timing analysis validation cases for cyclic sender-receiver communication.

This module contains warning-style rules that compare producer and consumer
timing periods on connected sender-receiver communication paths.
"""

from __future__ import annotations

from typing import List

from ...semantic_validation import Finding, ValidationCase, ValidationContext


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
