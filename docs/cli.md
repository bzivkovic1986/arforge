# CLI

ARForge currently provides three CLI commands:

- `init`
- `validate`
- `export`

There is no `inspect` command in the current implementation.

## `init`

Create a new project scaffold:

```bash
python -m arforge.cli init demo-system
```

Useful options:

- `--name` to set the system name used in scaffolded files
- `--no-example` to create structure without the runnable example
- `--force` to allow scaffolding into an existing non-empty directory

## `validate`

Validate a project manifest and its referenced YAML inputs:

```bash
python -m arforge.cli validate examples/autosar.project.yaml
```

Verbose modes:

```bash
python -m arforge.cli validate examples/autosar.project.yaml -v
python -m arforge.cli validate examples/autosar.project.yaml -vv
```

Behavior:

- schema validation runs during loading
- semantic validation runs with the `core` ruleset
- exit code is non-zero only when `error` findings exist
- warnings and infos are reported but do not fail the command on their own

## `export`

Validate first, then export ARXML.

Split export:

```bash
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc
```

Monolithic export:

```bash
python -m arforge.cli export examples/autosar.project.yaml --out build/all.arxml
```

Verbose modes:

```bash
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc -v
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc -vv
```

Behavior:

- export fails if validation reports semantic errors
- split export writes shared types, per-SWC files, and a system file
- monolithic export expects a file path
- `--templates` can be used to point to an alternate template directory
