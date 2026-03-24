# Invalid Validation Fixtures

## Purpose

This directory contains intentionally invalid YAML configurations used as validation test fixtures.

Each fixture represents a specific failure scenario for schema or, more commonly, semantic validation. These files are not user-facing modeling examples. They exist so ARForge can verify that validation rules produce the expected findings in a deterministic way.

## How Fixtures Are Used

Fixtures in this directory are exercised in two main ways:

- `pytest` loads them from [`tests/test_examples.py`](/d:/VMs/git/arforge/tests/test_examples.py) to check expected findings and stable finding codes.
- `arforge validate` can be run directly against a fixture to inspect the same validation behavior from the CLI.

Each fixture is expected to trigger a known validation outcome. That keeps validation rules honest as the codebase evolves and helps ensure:

- stable error and warning behavior
- deterministic findings
- reproducible test results

Typical project fixture shape:

```yaml
autosar:
  version: "4.2"
  rootPackage: "DEMO"

inputs:
  baseTypes: "../types/base_types.yaml"
  interfaces:
    - "../interfaces/*.yaml"
  swcs:
    - "../swcs/*.yaml"
  system: "system_bad_operation.yaml"
```

Many top-level files in this directory are small project aggregators like the example above. They usually reference supporting YAML from sibling folders such as `interfaces/`, `swcs/`, `types/`, or `support/`.

## Naming Convention

Use file names that describe both:

- the feature or validation area being exercised
- the specific problem that should fail

Preferred pattern:

- `project_<feature>_<error>.yaml`

Examples:

- `project_duplicate_instances.yaml`
- `project_bad_operation.yaml`
- `project_comspec_cs_async_with_timeout.yaml`

In practice, you may also see related support files such as `system_*.yaml` or shared inputs under subdirectories. The important part is that the name makes the failure scenario obvious to a new reader.

## How To Add A New Fixture

When adding a new validation rule:

1. Add at least one invalid YAML fixture that exercises the rule.
2. Make sure the fixture produces deterministic validation output.
3. Add corresponding `pytest` coverage for the expected findings.

Keep fixtures minimal and focused:

- include only the data needed to trigger the target rule
- avoid mixing multiple unrelated errors in one file
- prefer reusing shared support YAML when that keeps the scenario clear

If a rule needs extra supporting model data, add small helper files in the existing subdirectories instead of duplicating larger examples.

Example of a focused invalid fragment:

```yaml
operations:
  - name: Reset
    arguments:
      - name: status
        typeRef: "App_UnknownType"
```

## Relationship To `examples/`

The top-level [`examples/`](/d:/VMs/git/arforge/examples) directory contains valid modeling examples intended to validate and export successfully.

This `examples/invalid/` directory is different: it is the validation test corpus for scenarios that should fail or warn in well-defined ways.

## Future Note

These fixtures may eventually move to `tests/fixtures/` or a similar location. They are currently kept under `examples/invalid/` because that makes them easy to discover and review alongside the valid examples.
