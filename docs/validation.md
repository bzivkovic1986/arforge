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
- system connector compatibility checks

Findings are deterministic:

- case execution sorted by case id
- findings sorted by severity, code, message, location

## Fixture-driven testing

`tests/test_examples.py`:

- validates main example must pass
- discovers all invalid project fixtures under `examples/invalid/*.yaml` (top-level `autosar` + `inputs`)
- each invalid fixture is a separate parametrized test id
