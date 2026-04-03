# Overview

## What ARForge does

ARForge takes a set of YAML files describing an AUTOSAR Classic project - data types, interfaces, mode declaration groups, SWC types, and a system composition - validates them against a semantic rule engine, exports standards-compliant ARXML, and generates derived developer artifacts such as C skeletons and architecture diagrams.

The full pipeline in one line:

```
YAML inputs -> schema validation -> semantic validation -> internal model -> rendered outputs
```

Everything that can be checked before generation is checked before generation. The ARXML and generated artifacts you get out have already passed 191 semantic rules.

## The problem it solves

AUTOSAR SWC design in GUI-based tools is expensive, opaque, and hostile to version control. A single SWC change produces an unreadable XML diff. Validation is manual. There is no CI integration story. Licenses are expensive and tied to workstations.

ARForge keeps the source model in plain YAML files. Each file is human-readable, diff-friendly, and reviewable in a pull request. Validation runs from the command line in under a second. Export is deterministic - the same inputs always produce the same ARXML, byte for byte. It runs on Linux and Windows without any license server.

## Where ARForge fits in a workflow

ARForge is a design and generation tool. It is not a full round-trip tool and does not replace the RTE generator or BSW configuration toolchain.

A typical workflow looks like this:

```
Engineer authors YAML
       ->
arforge validate   <- catches design errors early, in CI or locally
       ->
arforge export     <- produces ARXML for the integrator
or
arforge generate   <- produces derived artifacts for developers and reviewers
       ->
RTE generator / DaVinci Integrator consumes ARXML
```

ARForge owns the upstream part of that chain - the part where design decisions are made and where errors are cheapest to fix.

## Platform support

ARForge runs on Linux and Windows. Both platforms are supported for CLI usage, VS Code integration, and the test suite. The `.vscode/tasks.json` configuration includes platform-specific Python paths for both environments.

## VS Code integration

ARForge ships with a `.vscode/` configuration that activates YAML schema autocomplete and inline diagnostics automatically when you open the project in VS Code. Tasks for validate, export, diagram generation, code generation, init, and pytest are available without any manual setup. See the [README](../README.md#vs-code-integration) and [Project Structure](./project-structure.md#vs-code-setup) for details.

## What is currently supported

ARForge targets a practical AUTOSAR Classic 4.2 subset:

- base, implementation, and application data types with constraints, units, and compu methods
- sender-receiver interfaces with data elements and ComSpec (implicit, explicit, queued)
- client-server interfaces with operations, arguments, return types, possible errors, and sync/async ComSpec
- mode-switch interfaces with `ModeDeclarationGroup` references
- `ModeDeclarationGroup` definitions as first-class model artifacts
- SWC types with provides/requires ports, runnables, and all standard AUTOSAR event kinds
- runnable access definitions - reads, writes, calls, raised errors - validated against port and interface semantics
- system compositions with component prototypes and port-level assembly connectors for SR, CS, and mode-switch flows
- semantic validation with 191 stable finding codes across three severity levels
- Jinja2-based ARXML export, monolithic or split by SWC, with deterministic ordering
- template-driven C code skeleton generation for SWC runnables
- PlantUML diagram generation for architecture and behavior views

## Design principles

Deterministic by default. Validation findings are sorted. Export output is ordered. The same input always produces the same output. This makes CI integration and git history meaningful.

Validate before export. Generation is blocked when error-severity findings exist. You cannot generate broken ARXML or starter artifacts by accident.

Stable finding codes. Every semantic rule has a stable `CORE-XXX` identifier. Finding codes do not change between versions. CI scripts and suppression lists can rely on them.

Explicit scope. ARForge covers the SWC design layer. It deliberately does not model OS configuration, memory mapping, BSW modules, or RTE internals. Staying in scope keeps the tool maintainable and the outputs trustworthy.
