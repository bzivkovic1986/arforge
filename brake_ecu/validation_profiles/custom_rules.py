from __future__ import annotations

from arforge.semantic_validation import validation_rule


@validation_rule(
    code="BRK-101",
    name="PlaceholderNamingRule",
    description="Placeholder custom validation rule for the Brake ECU profile.",
    tags=("brake-ecu", "placeholder", "naming"),
    default_severity="warning",
)
def rule_placeholder_naming(context):
    return []
