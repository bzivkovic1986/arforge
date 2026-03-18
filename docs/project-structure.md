# Project Structure

ARForge projects are organized around a small set of YAML inputs referenced by an aggregator file.

## Repository Layout

At the repository level, the main implementation lives in:

- `arforge/` for CLI, loading, model, validation, export, and scaffolding
- `schemas/` for JSON schemas
- `templates/` for Jinja2 ARXML templates
- `examples/` for valid and invalid sample projects
- `tests/` for pytest coverage
- `docs/` for user and project documentation

## Project Scaffold Layout

`arforge init` currently creates a project with this shape:

- `autosar.project.yaml`
- `types/`
- `units/`
- `compu_methods/`
- `interfaces/`
- `swcs/`
- `system.yaml`

The aggregator file points to the inputs that make up the project.

## What Belongs Where

- `interfaces/`
  - interface definitions such as sender-receiver and client-server interfaces
- `swcs/`
  - SWC type definitions, including ports, runnables, events, and ComSpec
- `system.yaml`
  - composition component prototypes and port-level connectors
- `types/`
  - base, implementation, and application data types
- `units/`
  - physical unit definitions referenced by application data types and compu methods
- `compu_methods/`
  - compu method definitions such as `linear` and `textTable`

## Generated and Build Output

Export output is written to the location passed to `arforge export`, commonly under `build/`.

Typical outputs are:

- split export directory containing shared types, per-SWC files, and system ARXML
- a single monolithic ARXML file when split mode is not used

Generated export artifacts should generally stay out of the source model directories.
