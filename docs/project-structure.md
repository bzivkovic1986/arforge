# Project Structure

An ARForge project is a set of YAML files referenced by a single aggregator manifest. The manifest tells ARForge where to find each input category. Everything else — validation, export — flows from that manifest.

## Scaffold layout

Running `arforge init my-project` produces this layout:

```
my-project/
├── autosar.project.yaml       ← aggregator manifest
├── types/
│   ├── base_types.yaml
│   ├── implementation_types.yaml
│   └── application_types.yaml
├── units/
│   └── units.yaml
├── compu_methods/
│   └── compu_methods.yaml
├── modes/
│   └── power_state.yaml
├── interfaces/
│   ├── If_VehicleSpeed.yaml
│   └── If_PowerState.yaml
├── swcs/
│   ├── SpeedSensor.yaml
│   └── SpeedDisplay.yaml
└── system.yaml
```

This is a convention, not a constraint. The manifest can point to files in any layout. Glob patterns are supported for interfaces, SWCs, units, compu methods, and mode declaration groups.

## The aggregator manifest

The manifest is the single entry point for all ARForge commands. It declares the AUTOSAR version, the root ARXML package name, and the location of every input file.

```yaml
# autosar.project.yaml
autosar:
  version: "4.2"
  rootPackage: "MY_PROJECT"

inputs:
  baseTypes: "types/base_types.yaml"
  implementationDataTypes: "types/implementation_types.yaml"
  applicationDataTypes: "types/application_types.yaml"
  units:
    - "units/units.yaml"
  compuMethods:
    - "compu_methods/compu_methods.yaml"
  modeDeclarationGroups:
    - "modes/*.yaml"
  interfaces:
    - "interfaces/*.yaml"
  swcs:
    - "swcs/*.yaml"
  system: "system.yaml"
```

All paths are resolved relative to the manifest file. This means the manifest and its inputs can live anywhere in a repository as long as the relative paths are correct.

## What belongs where

**`types/`** — data type definitions, split across three files by convention.

- `base_types.yaml` — platform-level types (`uint8`, `uint16`, etc.)
- `implementation_types.yaml` — implementation data types backed by base types; scalars, arrays, structs
- `application_types.yaml` — application data types with optional constraints, unit references, and compu method references

**`units/`** — physical unit definitions referenced by application types and compu methods.

**`compu_methods/`** — computation method definitions (`linear`, `textTable`) that describe physical scaling for application types.

**`modes/`** — `ModeDeclarationGroup` definitions. Each group defines a named set of modes with an initial mode. Groups are referenced by mode-switch interfaces and resolved transitively through mode-switch ports to `modeSwitchEvents` on runnables. Unused mode groups are flagged by `CORE-014`.

**`interfaces/`** — one file per interface. Each file defines a single sender-receiver, client-server, or mode-switch interface. Keeping one interface per file makes diffs clean and makes glob patterns in the manifest work well.

**`swcs/`** — one file per SWC type. Each file defines a single SWC type with its ports, runnables, events, and ComSpec.

**`system.yaml`** — the system composition. Declares component prototypes (instances of SWC types) and the port-level assembly connectors between them. There is one system file per project.

## Build output

Export output is written to the path passed to `arforge export`. By convention this lives under `build/` and should not be committed to source control if it is generated in CI.

Split export (`--split-by-swc`) produces one file per SWC plus shared types and the system composition:

```
build/
├── MY_PROJECT_SharedTypes.arxml
├── SpeedSensor.arxml
├── SpeedDisplay.arxml
└── Composition_DemoSystem.arxml
```

Monolithic export produces a single combined file:

```
build/all.arxml
```

## VS Code setup

ARForge ships with a `.vscode/` directory that configures the editor automatically when you open the repository root in VS Code.

**Required extensions:**
- [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
- [YAML](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) (Red Hat)

Once both extensions are installed, YAML schema autocomplete and inline validation diagnostics activate for all ARForge YAML files without any manual configuration.

**Configuring the active project file:**

The VS Code tasks resolve the project manifest from a single setting in `.vscode/settings.json`:

```jsonc
"arforge.projectFile": "examples/autosar.project.yaml"
```

Change this path to point to your own project manifest. All tasks — validate, export, init, pytest — pick it up automatically.

**Available tasks** (`Terminal → Run Task`):

| Task | What it runs |
|---|---|
| `arforge: validate project` | `arforge validate <projectFile> -vv` |
| `arforge: export project (split by swc)` | `arforge export <projectFile> --out build --split-by-swc -vv` |
| `arforge: export project (monolithic)` | `arforge export <projectFile> --out build/DemoProject.arxml -vv` |
| `arforge: init project` | `arforge init demo-project` |
| `arforge: pytest` | `pytest -q` |

Tasks resolve the correct Python executable for both Linux and Windows using VS Code's `${workspaceFolder}` variable, so no manual path editing is needed on either platform.

## Repository-level layout

At the repository level, the ARForge implementation itself is organized as follows. This is relevant for contributors.

```
arforge/                    ← CLI, loader, model, validation, export, scaffold
arforge/validation/cases/   ← domain-organized semantic validation cases
schemas/                    ← JSON Schema files for all input categories
templates/                  ← Jinja2 ARXML templates
examples/                   ← valid example project
examples/invalid/           ← invalid model fixtures used by the test suite
tests/                      ← pytest coverage
docs/                       ← this documentation
.vscode/                    ← VS Code schema, task, and settings configuration
```
