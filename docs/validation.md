# Validation

Validation is layered:

1. JSON Schema validation (file shape, required keys, enums, primitive constraints)
2. Semantic validation (cross-file/cross-reference correctness)

## JSON Schema layer

Implemented in `arforge/validate.py` with `jsonschema`.

Schemas are in `schemas/`:

- aggregator, interfaces, swcs, system, connections
- base/implementation/application types
- units and compu methods

## Semantic layer

Implemented via `ValidationCase` classes in `arforge/validation_cases.py`.

Current core rules include:

- uniqueness checks (types, interfaces, SWCs, units, compu methods, instances)
- type graph checks (base/impl/app refs)
- struct checks (field rules, no app fields, cycle detection)
- interface checks (SR data elements, CS operations/args/returns)
- runnable checks (reads/writes/calls)
- operation-invoked event checks
- runnable trigger policy checks
- system connector compatibility checks

Findings are deterministic:

- case execution sorted by case id
- findings sorted by severity, code, message, location

## Fixture-driven testing

`tests/test_examples.py`:

- validates main example must pass
- discovers all invalid project fixtures under `examples/invalid/*.yaml` (top-level `autosar` + `inputs`)
- each invalid fixture is a separate parametrized test id
