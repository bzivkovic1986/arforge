# Validation

Validation in ARForge has two layers:

1. JSON Schema validation for file structure
2. semantic validation for model correctness across files and references

## Schema Validation

Schema validation is implemented in `arforge/validate.py` using the JSON schema files in `schemas/`.

Current schema coverage includes:

- aggregator project manifests
- interfaces
- SWCs
- system files
- base, implementation, and application data types
- units
- compu methods

## Semantic Validation

Semantic validation is implemented as separate `ValidationCase` units in `arforge/validation_cases.py`.

Each finding carries:

- `code`
- `message`
- `severity`

Supported severity values are:

- `error`
- `warning`
- `info`

`arforge validate` fails only when at least one `error` finding is present.

## Deterministic Behavior

Validation behavior is designed to be deterministic:

- validation cases run in sorted order
- findings are sorted deterministically
- example fixtures are used to lock expected behavior

This supports stable diffs, reliable tests, and predictable CI output.

## Current Rule Coverage

The current `core` ruleset covers:

- global and local uniqueness checks
- base type metadata checks
- datatype reference and type graph checks
- implementation struct and array checks
- application constraint checks
- compu method and unit consistency checks
- sender-receiver and client-server interface checks
- runnable access checks for reads, writes, calls, and raised errors
- event binding checks
- trigger policy checks
- ComSpec validation
- system component instance type checks
- connector compatibility checks
- instantiated-port connectivity and usage checks
- cyclic sender-receiver timing mismatch warnings

## Core Validation Cases

| ID | Name | Description | Severity |
|----|------|-------------|----------|
| CORE-001 | GlobalUniqueness | Checks that globally named model elements remain unique. | Error |
| CORE-002 | BaseTypeMetadata | Checks base type uniqueness and required metadata consistency. | Error |
| CORE-010 | InterfaceSemantics | Checks interface structure and datatype references, including implementation datatype structures and arrays. | Error |
| CORE-011 | ApplicationConstraints | Checks application datatype constraints against implementation types, units, and compu methods. | Error |
| CORE-020 | SwcStructure | Checks SWC-local uniqueness for runnables and ports. | Error |
| CORE-021 | PortInterfaceReferences | Checks that each SWC port references an existing interface and uses the expected kind. | Error |
| CORE-022 | RunnableAccessSemantics | Checks runnable reads, writes, and calls against SWC port and interface semantics. | Error |
| CORE-023 | OperationInvokedEvents | Checks operation-invoked event bindings for provided client-server operations. | Error |
| CORE-024 | RunnableTriggerPolicy | Checks that each runnable uses exactly one trigger style. | Error |
| CORE-025 | PortComSpecSemantics | Checks sender-receiver and client-server ComSpec on SWC ports. | Error |
| CORE-026 | RunnableRaisedErrors | Checks runnable `raisesErrors` declarations for provided client-server operations. | Error |
| CORE-027 | DataReceiveEvents | Checks `dataReceiveEvents` bindings for required sender-receiver ports. | Error |
| CORE-030 | SystemInstanceTypes | Checks that composition component prototypes reference known SWC types. | Error |
| CORE-040 | ConnectionSemantics | Checks system connections and connector-level sender-receiver and client-server semantics. | Error |
| CORE-041 | SenderReceiverConnectivity | Checks sender-receiver instantiated-port connectivity against connectors and runnable behavior. | Error or warning, depending on finding |
| CORE-042 | SenderReceiverUsage | Checks whether connected sender-receiver ports are actually used by runnable behavior. | Warning |
| CORE-043 | ClientServerConnectivity | Checks client-server instantiated-port connectivity against connectors and runnable behavior. | Error |
| CORE-044 | ClientServerUsage | Checks whether connected or unconnected client-server ports are actually used by runnable behavior. | Warning |
| CORE-050 | SRConsumerFasterThanProducer | Warns when a cyclic sender-receiver consumer runs faster than its cyclic producer. | Warning |
| CORE-051 | SRProducerFasterThanConsumer | Warns when a cyclic sender-receiver producer runs faster than its cyclic consumer. | Warning |

Severity in the table reflects the normal outcome pattern of each rule. Some cases, such as `CORE-041`, can emit both hard errors and design-quality warnings under different conditions.

## Timing Analysis Rules

`CORE-050` and `CORE-051` are design-quality rules, not structural validity errors.

They compare cyclic runnable periods when both sides of a connected sender-receiver flow use `timingEventMs`:

- `CORE-050`: consumer runs faster than producer and may read stale data
- `CORE-051`: producer runs faster than consumer and may overwrite intermediate values before consumption

Equal timing does not produce a finding.

## CLI Output

Normal `validate` output prints findings and a severity summary.

`-v` adds per-case execution information.

`-vv` also includes case descriptions and more detailed execution output.

## Tests and Fixtures

`tests/test_examples.py` uses the checked-in example project plus invalid fixtures under `examples/invalid/` to verify deterministic validation behavior and expected finding codes.
