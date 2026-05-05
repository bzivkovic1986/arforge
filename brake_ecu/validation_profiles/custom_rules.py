from __future__ import annotations

from arforge.model import SWC_CATEGORY_COMPLEX_DEVICE_DRIVER
from arforge.semantic_validation import Finding, validation_rule


@validation_rule(
    code="BRK-101",
    name="DriverCategoryConvention",
    description="Checks that Brake ECU driver-style SWCs use the complexDeviceDriver category.",
    tags=("brake-ecu", "drivers", "category"),
    default_severity="warning",
)
def rule_placeholder_naming(context):
    findings: list[Finding] = []
    for swc in sorted(context.project.swcs, key=lambda item: item.name):
        if not swc.name.endswith("Driver"):
            continue
        if swc.category == SWC_CATEGORY_COMPLEX_DEVICE_DRIVER:
            continue
        findings.append(
            Finding(
                code="BRK-101-DRIVER-CATEGORY",
                severity="warning",
                message=(
                    f"SWC '{swc.name}' ends with 'Driver' and should use category "
                    f"'{SWC_CATEGORY_COMPLEX_DEVICE_DRIVER}'."
                ),
                location=f"swc:{swc.name}",
            )
        )
    return findings
