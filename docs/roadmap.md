# Roadmap

This roadmap describes the current capabilities of ARForge and the planned evolution of the project.
It is intended to communicate direction rather than strict release commitments.

# Current Feature Set

ARForge currently provides a working modeling subset for AUTOSAR Classic 4.2.x based on YAML inputs and ARXML export.

## Project and CLI

* project scaffolding (`arforge init`)
* YAML-based AUTOSAR modeling
* schema validation via JSON Schema
* semantic validation engine with rule IDs
* validation severity levels (error / warning / info)
* deterministic validation behavior
* CLI commands
  * `validate`
  * `export`
  * `init`
  * `inspect`

## AUTOSAR Modeling

### Software Components
- SWC type definitions
- SWC categories
  - `application`
  - `service`
  - `complexDeviceDriver`
- ports
  - provides
  - requires
- runnable definitions
- runnable access definitions
  - reads
  - writes
  - calls

### Runnable Events

Supported runnable triggers:
- `TimingEvent`
- `InitEvent`
- `OperationInvokedEvent`
- `DataReceiveEvent`
- `ModeSwitchEvent`

### Interfaces

Sender-Receiver Interfaces
- multiple data elements
- runnable read/write definitions
- communication specification
  - implicit
  - explicit
  - queued
- queue length validation

Client-Server Interfaces
- multiple operations
- operation arguments (`in`, `out`, `inout`)
- return types
- possible errors
- raised error declarations
- synchronous and asynchronous communication modes
- timeout configuration

### System Composition
- component prototypes (instances)
- SWC type references
- assembly connectors
- SR and C/S connections
- deterministic connector export

### Data Types
- base types
- implementation data types
- application data types

Supported constructs:
- scalar types
- array types
- struct types
- nested struct validation

Additional features:
- units
- compu methods
  - linear
  - textTable (enumerations)
- application type constraints

### Validation Framework
Validation includes:
- schema validation
- semantic validation rulesets
- stable rule IDs
- verbose diagnostics (-v, -vv)
- connectivity validation
- port usage validation
- timing mismatch analysis
- deterministic validation execution

### Export
- Jinja2-based ARXML export
- deterministic export ordering
- per-SWC export
- shared type export
- system export

### Developer Tooling
- pytest test coverage
- example projects
- invalid model fixtures
- VS Code schema support
- scaffolded example project

# Upcoming Features

These are the next planned improvements based on the current architecture.

## Connectivity and Integration Analysis
- deeper validation of component connectivity
- detection of unused ports and connectors
- detection of inconsistent runnable access patterns

## Authoring Experience
- improved scaffold templates
- clearer example projects
- enhanced JSON schema metadata
- improved editor autocompletion and diagnostics

## Visualization
- PlantUML architecture diagram generation
- system topology visualization
- runnable interaction views

## AUTOSAR Feature Expansion
Incrementally expand supported AUTOSAR Classic constructs:
- additional mode-related AUTOSAR Classic constructs beyond the current ModeDeclarationGroup and ModeSwitchEvent support

## Data Type Enhancements
- richer compu method categories
- improved physical unit metadata
- extended constraint support

## Export Improvements
- additional ARXML details for interfaces and types
- improved template coverage
- broader AUTOSAR Classic version compatibility

# Long-Term Direction

The long-term goal of ARForge is to provide a lightweight, developer-friendly alternative for AUTOSAR Classic modeling workflows.

Focus areas include:
- text-based AUTOSAR modeling
- CI/CD friendly validation
- deterministic ARXML generation
- modular and extensible validation rules
- strong developer tooling

ARForge aims to support practical AUTOSAR engineering workflows without requiring heavyweight proprietary modeling environments.
