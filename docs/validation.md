# Validation

Validation is layered:

1. JSON Schema validation (file shape, required keys, enums, primitive constraints)
2. Semantic validation (cross-file/cross-reference correctness)

## JSON Schema layer

Implemented in `arforge/validate.py` with `jsonschema`.

Schemas are in `schemas/`:

- aggregator, interfaces, swcs, system
- base/implementation/application types
- units and compu methods

## Semantic layer

Implemented via `ValidationCase` classes in `arforge/validation_cases.py`.

Current core rules include:

- uniqueness checks (types, interfaces, SWCs, units, compu methods, instances)
- base type checks:
  - per-base-type name uniqueness
  - metadata completeness and validity (`bitLength`, `signedness`)
- type graph checks (base/impl/app refs)
- struct checks (field rules, no app fields, cycle detection)
- compu method checks:
  - category must be supported (`linear` or `textTable`)
  - `linear`: known `unitRef`, non-zero `factor`, valid `physMin`/`physMax` ordering
  - `textTable`: at least one entry, unique `value`, non-empty `label` after trim
- application type + compu method checks:
  - unknown `compuMethodRef` is rejected
  - `linear` compu method requires `unitRef` on application type and exact unit match
  - `textTable` compu method allows optional `unitRef` with no unit-match enforcement
- application constraint checks:
  - integer constrained ranges are computed from base type metadata
  - if metadata is missing, explicit fallback is currently supported only for `uint8` and `uint16`
  - otherwise constrained integer range validation fails deterministically
- interface checks (SR data elements, CS operations/args/returns)
- runnable checks (reads/writes/calls)
- operation-invoked event checks
- runnable trigger policy checks
- port ComSpec checks:
  - senderReceiver: `mode` required, queued requires `queueLength >= 1`, non-queued must not define `queueLength`, CS fields not allowed
  - clientServer: `callMode` required (`synchronous | asynchronous`), `timeoutMs >= 0`, timeout only allowed for synchronous, SR fields not allowed
- system connector compatibility checks
- instantiated-port connectivity and runnable usage checks:
  - errors for runnable reads/writes/calls/events that reference unconnected instantiated ports
  - warnings for instantiated SR/CS ports with no connector
  - warnings for connected SR/CS ports that no runnable in the SWC type actually uses

Findings are deterministic:

- case execution sorted by case id
- findings sorted by severity, code, message, location

ComSpec validation is implemented in dedicated case `CORE-025` to keep the rule isolated and maintainable.

Runtime output from `arforge validate -v` shows each case code, name, result, timing, and finding count. `arforge validate -vv` also prints the matching one-line description shown below.

## Core Validation Cases

| Code | Name | Description |
|------|------|-------------|
| CORE-001 | GlobalUniqueness | Checks that globally named model elements remain unique. |
| CORE-002 | BaseTypeMetadata | Checks base type uniqueness and required metadata consistency. |
| CORE-010 | InterfaceSemantics | Checks interface structure and datatype references. |
| CORE-011 | ApplicationConstraints | Checks application datatype constraints against implementation types and compu methods. |
| CORE-020 | SwcStructure | Checks SWC-local uniqueness for runnables and ports. |
| CORE-021 | PortInterfaceReferences | Checks that each SWC port references an existing interface and uses the expected kind. |
| CORE-022 | RunnableAccessSemantics | Checks runnable reads, writes, and calls against SWC port and interface semantics. |
| CORE-023 | OperationInvokedEvents | Checks operation-invoked event bindings for provided client-server operations. |
| CORE-024 | RunnableTriggerPolicy | Checks that each runnable uses exactly one trigger style. |
| CORE-025 | PortComSpecSemantics | Checks sender-receiver and client-server ComSpec on SWC ports. |
| CORE-026 | RunnableRaisedErrors | Checks runnable raisesErrors declarations for provided client-server operations. |
| CORE-027 | DataReceiveEvents | Checks dataReceiveEvents bindings for required sender-receiver ports. |
| CORE-030 | SystemInstanceTypes | Checks that composition component prototypes reference known SWC types. |
| CORE-040 | ConnectionSemantics | Checks system connections and connector-level sender-receiver and client-server semantics. |
| CORE-041 | SenderReceiverConnectivity | Checks sender-receiver port connectivity against instantiated components and runnable behavior. |
| CORE-042 | SenderReceiverUsage | Checks whether connected sender-receiver ports are actually used by runnable behavior. |
| CORE-043 | ClientServerConnectivity | Checks client-server port connectivity against instantiated components and runnable behavior. |
| CORE-044 | ClientServerUsage | Checks whether connected client-server ports are actually used by runnable behavior. |

## Fixture-driven testing

`tests/test_examples.py`:

- validates main example must pass
- discovers all invalid project fixtures under `examples/invalid/*.yaml` (top-level `autosar` + `inputs`)
- each invalid fixture is a separate parametrized test id
