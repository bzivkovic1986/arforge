# Modeling Concepts

This page explains the main modeling concepts used by ARForge as they exist in the current repository.

## SWC Type vs Component Prototype

ARForge models SWC definitions and system instances separately.

- A file in `swcs/` defines an SWC type: ports, runnables, and behavior.
- `system.yaml` defines component prototypes inside the composition by referencing those SWC types with `typeRef`.

In other words:

- `SpeedSensor` is an SWC type
- `SpeedSensor_1` is a component prototype or instance in the system composition

This distinction matters because connectors are created between instantiated ports in `system.yaml`, not directly between SWC type definitions.

## Sender-Receiver vs Client-Server Interfaces

ARForge currently supports three interface kinds:

- `senderReceiver`
- `clientServer`
- `modeSwitch`

Sender-receiver interfaces define `dataElements`. They are used for data flow between ports and for runnable `reads` and `writes`.

Client-server interfaces define `operations`, including arguments, optional possible errors, and optional return types. They are used for runnable `calls`, `operationInvokedEvents`, and `raisesErrors`.

Mode-switch interfaces define `modeGroupRef`. They are used by provides/requires ports to reference a shared `ModeDeclarationGroup`.

## Mode Declaration Groups

ARForge now supports AUTOSAR `ModeDeclarationGroup` definitions as a first-class shared model artifact.

Mode declaration groups are defined in `modes/*.yaml` and currently include:

- the group `name`
- `initialMode`
- an ordered list of `modes`

Mode declaration groups are now also referenced by `modeSwitch` interfaces and the ports bound to those interfaces.

Mode-related runnable events such as `ModeSwitchEvent` are not yet modeled.

## Runnables and Events

Runnables are defined inside an SWC and capture the executable behavior relevant to validation and export.

Current runnable/event patterns include:

- cyclic runnables using `timingEventMs`
- initialization runnables using `initEvent`
- operation-triggered runnables using `operationInvokedEvents`
- data-triggered runnables using `dataReceiveEvents`

Runnable access definitions belong on the runnable itself:

- `reads`
- `writes`
- `calls`
- `raisesErrors`

ARForge validates that these accesses match the referenced port direction, interface kind, and interface members.

## Port-Level Connectors

System connectors are defined in `system.yaml` using `Instance.Port` endpoints.

Example:

```yaml
connectors:
  - from: "SpeedSensor_1.Pp_VehicleSpeed"
    to: "SpeedDisplay_1.Rp_VehicleSpeed"
```

Connectors are port-level only. They do not carry sender-receiver data element selection or client-server operation selection.

## Where `dataElement` Usage Belongs

`dataElement` usage belongs in runnable behavior, not in connectors.

Examples:

- sender-receiver reads: `runnables[*].reads[*].dataElement`
- sender-receiver writes: `runnables[*].writes[*].dataElement`
- data-triggered events: `runnables[*].dataReceiveEvents[*].dataElement`

This keeps the connector definition about wiring and keeps data usage on the runnable that actually consumes or produces the element.

## Where `operation` Usage Belongs

For client-server communication, operation usage also belongs in runnable behavior.

Examples:

- client calls: `runnables[*].calls[*].operation`
- server-triggered execution: `runnables[*].operationInvokedEvents[*].operation`
- raised server errors: `runnables[*].raisesErrors[*].operation`

Connectors only describe which instantiated required and provided ports are wired together.

## ComSpec

Port communication details belong on `ports[*].comSpec`.

Current supported rules include:

- sender-receiver modes: `implicit`, `explicit`, `queued`
- queued sender-receiver ports require `queueLength >= 1`
- client-server ports use `callMode`
- synchronous client calls may define `timeoutMs`

These rules are validated semantically and are also reflected in export behavior.
