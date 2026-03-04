# Overview

ARForge is a YAML-first AUTOSAR Classic 4.2 modeling tool.

Current pipeline:

1. Load `*.project.yaml` aggregator input.
2. Expand input globs for interfaces, SWCs, units, and compu methods.
3. Run JSON Schema validation for each input file.
4. Build internal Python model (`arforge/model.py`).
5. Run semantic validation rules (`core` ruleset).
6. Render ARXML via Jinja2 templates.

Main CLI entry points:

- `python -m arforge.cli validate <project.yaml>`
- `python -m arforge.cli export <project.yaml> --out <path> [--split-by-swc]`

Primary focus of the current implementation:

- deterministic validation findings and stable rule codes
- version-specific templates (AUTOSAR Classic 4.2)
- examples-driven development under `examples/`
- fixture-based pytest coverage under `tests/test_examples.py`
