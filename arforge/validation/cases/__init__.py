"""Central validation case registry for the domain-organized case modules.

This module re-exports the case classes and defines the ordered `core`
ruleset used by semantic validation.
"""

from __future__ import annotations

from typing import List

from ...semantic_validation import ValidationCase
from .common import DuplicateNameCase
from .connectivity import (
    CsPortConnectivityCase,
    CsPortUsageCase,
    DeclaredPortUsageCase,
    ModeSwitchConnectivityCase,
    ModeSwitchUsageCase,
    SrPortConnectivityCase,
    SrPortUsageCase,
)
from .interfaces import InterfaceSemanticCase
from .modes import (
    ModeDeclarationGroupInitialModeCase,
    ModeDeclarationGroupStructureCase,
    UnusedModeDeclarationGroupCase,
)
from .swc import (
    ComSpecSemanticCase,
    DataReceiveEventCase,
    ModeSwitchEventCase,
    OperationInvokedEventCase,
    RunnableAccessSemanticCase,
    RunnableRaisedErrorCase,
    RunnableTriggerPolicyCase,
    SwcPortInterfaceCase,
    SwcStructureCase,
)
from .system import ConnectionSemanticCase, SystemInstanceTypeCase
from .timing import SrConsumerFasterThanProducerCase, SrProducerFasterThanConsumerCase
from .types import ApplicationConstraintCase, BaseTypeMetadataCase

__all__ = [
    "ApplicationConstraintCase",
    "BaseTypeMetadataCase",
    "ComSpecSemanticCase",
    "ConnectionSemanticCase",
    "CsPortConnectivityCase",
    "CsPortUsageCase",
    "DataReceiveEventCase",
    "DeclaredPortUsageCase",
    "DuplicateNameCase",
    "InterfaceSemanticCase",
    "ModeDeclarationGroupInitialModeCase",
    "ModeDeclarationGroupStructureCase",
    "ModeSwitchConnectivityCase",
    "ModeSwitchEventCase",
    "ModeSwitchUsageCase",
    "OperationInvokedEventCase",
    "RunnableAccessSemanticCase",
    "RunnableRaisedErrorCase",
    "RunnableTriggerPolicyCase",
    "SrConsumerFasterThanProducerCase",
    "SrPortConnectivityCase",
    "SrPortUsageCase",
    "SrProducerFasterThanConsumerCase",
    "SwcPortInterfaceCase",
    "SwcStructureCase",
    "SystemInstanceTypeCase",
    "UnusedModeDeclarationGroupCase",
    "core_validation_cases",
]


def core_validation_cases() -> List[ValidationCase]:
    return [
        DuplicateNameCase(),
        BaseTypeMetadataCase(),
        InterfaceSemanticCase(),
        ModeDeclarationGroupStructureCase(),
        ModeDeclarationGroupInitialModeCase(),
        UnusedModeDeclarationGroupCase(),
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
        ModeSwitchUsageCase(),
        SrConsumerFasterThanProducerCase(),
        SrProducerFasterThanConsumerCase(),
    ]
