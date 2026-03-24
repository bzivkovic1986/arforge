# Architecture

ARForge follows a straightforward pipeline:

`YAML -> schema validation -> semantic validation -> internal model -> ARXML export`

## Processing Pipeline

1. Load the aggregator project file (`*.project.yaml`).
2. Expand file patterns for interfaces, SWCs, units, compu methods, and mode declaration groups.
3. Validate each input file against JSON schema.
4. Merge the parsed data into the internal project model.
5. Run semantic validation cases from the `core` ruleset.
6. Render ARXML through Jinja2 templates and write outputs.

## Module Responsibilities

- `arforge/cli.py`
  - user-facing CLI commands and console output
- `arforge/validate.py`
  - project loading, glob expansion, schema validation, and aggregation
- `arforge/model.py`
  - internal data model used after parsing
- `arforge/semantic_validation.py`
  - validation runner, finding model, and validation context/indexes
- `arforge/validation/cases/`
  - domain-organized semantic validation cases (`CORE-*`)
- `arforge/validation_cases.py`
  - compatibility export surface for validation case imports
- `arforge/exporter.py`
  - export orchestration, rendering, and file writing
- `arforge/scaffold.py`
  - project scaffold generation used by `arforge init`
- `templates/*.j2`
  - ARXML rendering templates
- `schemas/*.json`
  - schema constraints for YAML inputs

## Internal Responsibilities

- The loader is responsible for finding files, parsing YAML, and enforcing schema shape.
- The model layer is responsible for turning merged input into a consistent internal representation.
- The semantic validation layer is responsible for cross-file and cross-reference rules that JSON Schema cannot express cleanly.
- The exporter is responsible for deterministic rendering and writing of ARXML artifacts.

## Data Flow

`project.yaml` -> `load_aggregator_with_report()` -> merged input -> model build -> semantic validation -> exporter render/write

The loader currently supports:

- `baseTypes`
- `implementationDataTypes`
- `applicationDataTypes`
- `units`
- `compuMethods`
- `modeDeclarationGroups`
- `interfaces`
- `swcs`
- `system`

## Validation Architecture

- Each semantic rule is implemented as a separate validation case.
- Cases are organized by domain under `arforge/validation/cases/`.
- Cases are grouped into the `core` ruleset in `arforge/validation_registry.py`.
- Findings are sorted deterministically by severity, code, message, and location.

## Export Architecture

ARForge currently supports two export layouts:

- split export:
  - `<RootPackage>_SharedTypes.arxml`
  - one `<SWC>.arxml` per SWC type
  - one `<System>.arxml` for the composition
- monolithic export:
  - one combined ARXML file

Objects are ordered deterministically where needed so repeated exports produce stable output.
