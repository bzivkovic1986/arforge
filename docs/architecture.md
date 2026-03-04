# Architecture

## Module layout

- `arforge/cli.py`
  - CLI commands and user-facing output.
- `arforge/validate.py`
  - file loading, glob expansion, schema validation, aggregator merge.
- `arforge/model.py`
  - immutable project IR dataclasses.
- `arforge/semantic_validation.py`
  - validation runner, findings model, context indexes.
- `arforge/validation_cases.py`
  - concrete semantic rules (`CORE-*`).
- `arforge/exporter.py`
  - render orchestration and output writing.
- `templates/*.j2`
  - ARXML rendering templates.
- `schemas/*.json`
  - authoring-time JSON schema constraints.

## Data flow

`project.yaml` -> `validate.load_aggregator_with_report()` -> merged dict -> `model.from_dict()` -> `Project` -> semantic validation -> exporter render/write.

The project loader supports:

- split type inputs (`baseTypes`, `implementationDataTypes`, `applicationDataTypes`)
- optional physical type inputs (`units`, `compuMethods`)
- legacy `datatypes` input (deprecated warning)

## Validation architecture

- Rules are class-based `ValidationCase` units.
- Rules are grouped into a ruleset (`core`) in `validation_registry.py`.
- `ValidationRunner` executes cases sorted by case id and returns deterministic sorted findings.

## Export architecture

- Shared artifacts:
  - `shared.arxml` (types + interfaces)
- Per-component artifacts:
  - `<SWC>.arxml`
- System artifact:
  - `system.arxml`

Or a monolithic output (`all_42.arxml.j2`) when split mode is disabled.
