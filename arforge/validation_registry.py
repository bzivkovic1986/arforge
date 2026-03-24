"""Validation ruleset lookup for semantic validation execution.

This module maps ruleset names to their ordered validation case instances and
returns copies of those lists for execution.
"""

from __future__ import annotations

from typing import Dict, List

from .semantic_validation import ValidationCase
from .validation.cases import core_validation_cases

_RULESETS: Dict[str, List[ValidationCase]] = {
    "core": core_validation_cases(),
}


def get_ruleset(name: str = "core") -> List[ValidationCase]:
    try:
        return list(_RULESETS[name])
    except KeyError as exc:
        known = ", ".join(sorted(_RULESETS.keys()))
        raise ValueError(f"Unknown validation ruleset '{name}'. Known rulesets: {known}") from exc

