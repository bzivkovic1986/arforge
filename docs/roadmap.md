# Roadmap

This roadmap reflects areas that are visible in the current repository direction and constraints.

## Near-term consolidation

- keep schemas, model, and semantic validation aligned as new modeling features are added
- maintain deterministic validation behavior and stable finding codes
- extend fixture coverage under `examples/invalid/*.yaml`

## Type-system evolution

Already implemented:

- split base/implementation/application types
- implementation structs
- units + linear compu methods

Likely next increments (not yet implemented in current code):

- richer compu method categories (beyond linear)
- additional unit metadata/dimensions
- deeper ARXML details for data type internals

## Tooling and authoring UX

Current repo already includes:

- VS Code schema mapping
- VS Code tasks and debug launch profiles
- fixture-driven pytest setup

Potential continuation:

- improve editor completions and diagnostics
- broaden CLI diagnostics/report output
