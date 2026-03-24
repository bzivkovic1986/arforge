# Validation

Validation in ARForge has two layers:

1. JSON Schema validation for file structure
2. semantic validation for model correctness across files and references

## Schema Validation

Schema validation is implemented in `arforge/validate.py` using the JSON schema files in `schemas/`.

Current schema coverage includes:

- aggregator project manifests
- mode declaration groups
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
- mode declaration group checks
- compu method and unit consistency checks
- sender-receiver, client-server, and mode-switch interface checks
- runnable access checks for reads, writes, calls, and raised errors
- event binding checks
- mode-switch event binding checks
- trigger policy checks
- ComSpec validation
- system component instance type checks
- SWC-local declared-but-unused port warnings
- connector compatibility checks
- instantiated-port connectivity and usage checks
- cyclic sender-receiver timing mismatch warnings

## Core Validation Cases

| ID | Name | Description | Severity |
|----|------|-------------|----------|
| CORE-001 | GlobalUniqueness | Checks that globally named model elements remain unique. | Error |
| CORE-002 | BaseTypeMetadata | Checks base type uniqueness and required metadata consistency. | Error |
| CORE-010 | InterfaceSemantics | Checks interface structure and datatype references, including implementation datatype structures and arrays, plus mode-switch `modeGroupRef` rules. | Error |
| CORE-011 | ApplicationConstraints | Checks application datatype constraints against implementation types, units, and compu methods. | Error |
| CORE-012 | ModeDeclarationGroupStructure | Checks mode declaration group uniqueness and local mode naming rules. | Error |
| CORE-013 | ModeDeclarationGroupInitialMode | Checks that each mode declaration group `initialMode` references one of its declared modes. | Error |
| CORE-014 | UnusedModeDeclarationGroups | Checks for mode declaration groups that are declared but never referenced by mode-switch interfaces. | Warning |
| CORE-020 | SwcStructure | Checks SWC-local uniqueness for runnables and ports. | Error |
| CORE-021 | PortInterfaceReferences | Checks that each SWC port references an existing interface and uses the expected kind. | Error |
| CORE-022 | RunnableAccessSemantics | Checks runnable reads, writes, and calls against SWC port and interface semantics. | Error |
| CORE-023 | OperationInvokedEvents | Checks operation-invoked event bindings for provided client-server operations. | Error |
| CORE-024 | RunnableTriggerPolicy | Checks that each runnable uses exactly one trigger style. | Error |
| CORE-025 | PortComSpecSemantics | Checks sender-receiver and client-server ComSpec on SWC ports. | Error |
| CORE-026 | RunnableRaisedErrors | Checks runnable `raisesErrors` declarations for provided client-server operations. | Error |
| CORE-027 | DataReceiveEvents | Checks `dataReceiveEvents` bindings for required sender-receiver ports. | Error |
| CORE-028 | ModeSwitchEvents | Checks `modeSwitchEvents` bindings for required mode-switch ports and declared modes. | Error |
| CORE-030 | SystemInstanceTypes | Checks that composition component prototypes reference known SWC types. | Error |
| CORE-040 | ConnectionSemantics | Checks system connections and connector-level sender-receiver and client-server semantics. | Error |
| CORE-041 | SenderReceiverConnectivity | Checks sender-receiver instantiated-port connectivity against connectors and runnable behavior. | Error or warning, depending on finding |
| CORE-042 | SenderReceiverUsage | Checks whether connected sender-receiver ports are actually used by runnable behavior. | Warning |
| CORE-043 | ClientServerConnectivity | Checks client-server instantiated-port connectivity against connectors and runnable behavior. | Error or warning, depending on finding |
| CORE-044 | ClientServerUsage | Checks whether connected or unconnected client-server ports are actually used by runnable behavior. | Warning |
| CORE-045 | ModeSwitchConnectivity | Checks mode-switch instantiated-port connectivity against connectors. | Warning |
| CORE-046 | DeclaredPortUsage | Checks whether declared SWC ports are actually used by runnable behavior before or regardless of system connectivity. | Warning |
| CORE-050 | SRConsumerFasterThanProducer | Warns when a cyclic sender-receiver consumer runs faster than its cyclic producer. | Warning |
| CORE-051 | SRProducerFasterThanConsumer | Warns when a cyclic sender-receiver producer runs faster than its cyclic consumer. | Warning |

Severity in the table reflects the normal outcome pattern of each rule. Some cases, such as `CORE-041` and `CORE-043`, can emit both hard errors and integration-quality warnings under different conditions.

## Declared Vs Connected Usage

`CORE-046` is SWC-local and warns when a declared port has no runnable-side usage yet:

- sender-receiver provides ports with no writes
- sender-receiver requires ports with no reads and no `dataReceiveEvents`
- client-server requires ports with no calls
- client-server provides ports with no `operationInvokedEvents`
- mode-switch requires ports with no `modeSwitchEvents`

This is distinct from the integration-oriented checks in `CORE-042`, `CORE-044`, and `CORE-045`, which still describe instantiated or connected system behavior.

Mode-switch provides ports are intentionally skipped by `CORE-046` because provider-side mode behavior is not modeled in ARForge yet.

## Unused Mode Declaration Groups

`CORE-014` warns when a `ModeDeclarationGroup` is declared in the project but no `modeSwitch` interface references it via `modeGroupRef`.

This is a model-quality signal only: validation still succeeds unless some separate semantic error is also present.

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
