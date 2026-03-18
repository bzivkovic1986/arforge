# Overview

ARForge is a lightweight AUTOSAR Classic modeling tool that uses YAML as the primary authoring format and ARXML as the export target.

It is intended for repository-based workflows where developers want readable inputs, deterministic validation, stable diffs, and automation-friendly export.

## What Problem It Solves

Traditional AUTOSAR authoring workflows can be difficult to review and automate in normal software development pipelines. ARForge keeps the source model in plain YAML, validates it before export, and produces predictable outputs that fit well into CI/CD and version control.

## Current Scope

The current repository supports a focused AUTOSAR Classic 4.2 subset, including:

- aggregator project manifests (`*.project.yaml`)
- split type inputs for base, implementation, and application data types
- units and compu methods
- sender-receiver and client-server interfaces
- SWC types with ports, runnables, events, and ComSpec
- system composition instances and port-level connectors
- semantic validation with stable finding codes
- Jinja2-based ARXML export

The project is intentionally incremental. The current implementation is aimed at a practical, maintainable subset rather than full AUTOSAR coverage.

## Main Entry Points

- `python -m arforge.cli init <path>`
- `python -m arforge.cli validate <project.yaml>`
- `python -m arforge.cli export <project.yaml> --out <path> [--split-by-swc]`

## Project Characteristics

- YAML-first authoring
- deterministic validation behavior
- deterministic export ordering
- examples-driven tests under `examples/` and `tests/`
- validation split into schema and semantic stages
