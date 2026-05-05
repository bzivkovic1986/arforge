# Brake ECU Showcase

This project is the richest end-to-end ARForge showcase in the repository. It stays readable on purpose, but it now demonstrates a wider slice of the supported feature set than the smaller examples.

It covers:

- external package layout via [packages/brake_ecu_layout.yaml](/d:/dev/arforge/brake_ecu/packages/brake_ecu_layout.yaml)
- explicit package assignment on selected SWCs, interfaces, datatypes, mode groups, and the reusable subcomposition
- runnable `modeConditions` on timing, data-receive, and operation-invoked runnables
- one multi-element sender-receiver interface in [interfaces/If_BrakeStatus.yaml](/d:/dev/arforge/brake_ecu/interfaces/If_BrakeStatus.yaml)
- richer client-server signatures in [interfaces/If_BrakeDiagnostics.yaml](/d:/dev/arforge/brake_ecu/interfaces/If_BrakeDiagnostics.yaml), including `out`, `inout`, and omitted `returnType` for `void`
- one realistic `complexDeviceDriver` SWC in [swcs/WheelSpeedCaptureDriver.yaml](/d:/dev/arforge/brake_ecu/swcs/WheelSpeedCaptureDriver.yaml)

Practical notes:

- `If_BrakeStatus` is intentionally multi-element and therefore its required ports avoid `comSpec`, because current ARForge export supports `comSpec` only when the referenced SR interface has exactly one data element.
- queued SR coverage is still exercised through `StatusLogger.Rp_BrakeTorqueRequestQueued`, so the project keeps explicit, implicit, and queued receiver examples without mixing unsupported combinations.
- the validation profile in [validation_profiles/naming.yaml](/d:/dev/arforge/brake_ecu/validation_profiles/naming.yaml) includes one small custom rule that checks driver-style SWCs use the `complexDeviceDriver` category.
