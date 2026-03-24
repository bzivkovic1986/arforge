# Roadmap

This roadmap describes what ARForge currently supports and where it is going. It communicates direction, not release commitments.

---

## Current capabilities

ARForge currently provides a complete SWC design and ARXML export pipeline for AUTOSAR Classic 4.2, running on Linux and Windows with VS Code integration.

### CLI and tooling

- `arforge init` — project scaffold generation with working example
- `arforge validate` — schema + semantic validation with verbose modes (`-v`, `-vv`)
- `arforge export` — validated ARXML export, monolithic or split by SWC
- VS Code integration — YAML schema autocomplete, inline diagnostics, and task runner
- pytest suite with valid and invalid fixtures covering all supported constructs

### Data types

- base types with bit length, signedness, and native declaration
- implementation data types — scalar, array, struct with nested struct validation and cycle detection
- application data types with physical constraints, unit references, and compu method references
- units and compu methods — `linear` and `textTable` (enumeration) categories
- constraint validation against base type ranges

### Interfaces

- sender-receiver interfaces with data elements
- client-server interfaces with operations, in/out/inout arguments, return types, possible errors
- mode-switch interfaces with `ModeDeclarationGroup` references
- `ModeDeclarationGroup` definitions as first-class model artifacts

### SWC types

- SWC categories: `application`, `service`, `complexDeviceDriver`
- provides and requires ports for all three interface kinds
- ComSpec — SR implicit/explicit/queued with queue length validation; CS synchronous/asynchronous with timeout configuration
- runnable definitions with all standard AUTOSAR event triggers: `TimingEvent`, `InitEvent`, `OperationInvokedEvent`, `DataReceiveEvent`, `ModeSwitchEvent`
- runnable access definitions: `reads`, `writes`, `calls`, `raisesErrors` — all validated against port direction and interface kind

### System composition

- component prototypes with SWC type references
- port-level assembly connectors for SR, CS, and mode-switch flows
- deterministic connector export ordering

### Validation

- two-stage validation: JSON Schema + semantic
- 191 stable `CORE-*` finding codes organized in domain modules
- three severity levels: `error`, `warning`, `info`
- connectivity validation for SR, CS, and mode-switch ports
- port usage analysis — warnings for connected but unused ports
- declared port usage analysis (`CORE-046`) — warns when SWC ports are never accessed by any runnable, independent of system connectors
- mode-switch usage analysis (`CORE-047`) — warns when connected mode-switch ports are never used by runnable `modeSwitchEvents`
- unused mode declaration group detection (`CORE-014`)
- SR timing mismatch analysis — warns when consumer runs faster or slower than producer
- deterministic finding order — stable CI output across runs

### Export

- Jinja2-based ARXML templates
- deterministic output ordering — repeated exports produce identical output
- monolithic and split-by-SWC export layouts
- custom template directory support (`--templates`) for OEM-specific ARXML profiles

---

## Near-term

**C code skeleton generation**
Generate `.c` and `.h` implementation templates from the validated SWC model. Runnable stubs with correct `Rte_Read_`, `Rte_Write_`, `Rte_Call_`, and `Rte_Receive_` signatures derived from port definitions, ComSpec, and CS argument directions. This turns ARForge from a design tool into a development tool and is entirely derivable from the existing validated model — no new YAML syntax required.

**PlantUML / Mermaid diagram generation**
Generate system topology diagrams showing component instances and their port connections, and per-SWC diagrams showing provides/requires ports with interface names. Mermaid output renders natively in GitHub markdown, making generated diagrams first-class repository artifacts alongside the YAML.

**Deeper connectivity and usage reporting**
A structured `arforge report` command producing a human-readable summary of what is connected, what is dangling, and what is defined but unused across the full project. Useful for architecture reviews and integration handoffs.

**Improved authoring experience**
Enhanced JSON Schema metadata for better editor autocomplete and inline diagnostics. Clearer scaffold templates and improved error messages for common mistakes.

---

## Medium-term

**AUTOSAR 4.3 / 4.4 support**
Versioned template and schema architecture (`--schema-version` flag) to support multiple AUTOSAR Classic schema targets. The internal model and validation layer are designed to be version-agnostic; the version-specific work is in the templates and schema files.

**Nested composition support**
Compositions within compositions — sub-compositions referenced as component prototypes in a parent composition. Required for real-world project scale beyond flat single-level designs.

**OEM / project profile system**
A profile mechanism allowing project-specific or OEM-specific constraints to be expressed as configuration rather than code changes — naming convention enforcement, mandatory port prefixes, required SWC categories, restricted compu method types. Profiles extend the validation ruleset and export templates without modifying ARForge core.

**VS Code extension**
A dedicated VS Code extension providing YAML schema autocomplete, inline validation diagnostics, and model preview for ARForge projects. The JSON schemas in `schemas/` are the foundation — the extension makes them accessible without manual schema configuration in any project.

---

## Longer-term

**ARXML import (partial, best-effort)**
Import of interface definitions and data type packages from supplier-provided ARXML into ARForge YAML. Scoped to the shared type and interface layer — not full round-trip import of compositions or OEM-extended ARXMLs. The goal is to eliminate the manual retyping of supplier interfaces, not to solve full ARXML round-trip.

**Adaptive Platform (AP) support**
Experimental support for selected AUTOSAR Adaptive Platform constructs. The Classic Platform remains the primary focus; AP support would be additive and clearly scoped.

---

## What is deliberately out of scope

ARForge covers the SWC design layer. The following are intentionally not modeled:

- RTE contract header generation — tightly coupled to BSW and RTE vendor configuration, outside the SWC design boundary
- OS task and alarm configuration
- BSW module configuration (COM, DCM, NvM, etc.)
- Memory mapping and linker configuration
- ECU extract generation

Staying within this scope keeps ARForge's outputs trustworthy and its maintenance tractable.
