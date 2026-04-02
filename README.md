# ARForge

> YAML-first AUTOSAR Classic SWC design. Version-controlled, CI-friendly, no license server.

![AUTOSAR Classic 4.2](https://img.shields.io/badge/AUTOSAR-Classic%204.2-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
![Python](https://img.shields.io/badge/python-3.x-lightgrey)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey)
![Tests](https://img.shields.io/badge/tests-pytest-yellow)

ARForge lets you design AUTOSAR Classic SWCs and compositions in plain YAML, validate them against semantic rules, and export standards-compliant ARXML — without a GUI tool or license server. It runs on Linux and Windows, integrates with Visual Studio Code, and fits naturally into any CI pipeline.

---

## Why ARForge

AUTOSAR SWC design in GUI-based tools is expensive, opaque, and hostile to version control. Diffs are unreadable, validation is manual, and the toolchain cannot run in CI. ARForge is designed from the ground up for the opposite: a YAML source of truth that is readable, diffable, and automatable.

| | |
|---|---|
| **Text-first design** | SWCs, compositions, interfaces, modes, and types — all in human-readable YAML |
| **Semantic validation** | 191 stable finding codes across all supported constructs. Catches design problems before export |
| **Clean ARXML export** | Deterministic, ordered output — git diffs on generated files are actually readable |
| **CI-ready CLI** | Validate and export in a pipeline with no GUI dependency or license server |
| **VS Code integration** | YAML schema autocomplete, inline diagnostics, and task runner built in |

---

## Who this is for

ARForge is aimed at AUTOSAR engineers, independent consultants, and teams who want SWC design to live in version control and run in CI — without a commercial toolchain. It works well for greenfield SWC development, architecture work done offline, and automated ARXML generation from a controlled source of truth.

---

## What ARForge covers

Current implementation targets a practical AUTOSAR Classic 4.2 subset:

| Area | Details |
|---|---|
| **Data types** | Base, implementation, and application types; scalar, array, and struct; units and compu methods (linear, text table) |
| **Sender-Receiver interfaces** | Data elements, implicit/explicit/queued ComSpec, queue length validation |
| **Client-Server interfaces** | Operations, in/out/inout arguments, return types, possible errors, sync/async call modes, timeout configuration |
| **Mode-Switch interfaces** | `ModeDeclarationGroup` definitions, mode manager and user ports, `ModeSwitchEvent` runnable triggers |
| **SWC types** | Provides/requires ports, runnables, `TimingEvent`, `InitEvent`, `OperationInvokedEvent`, `DataReceiveEvent`, `ModeSwitchEvent` |
| **Runnable access** | `reads`, `writes`, `calls`, `raisesErrors` — all validated against port direction and interface kind |
| **System composition** | Component prototypes, SWC type references, port-level assembly connectors for SR, CS, and mode-switch |
| **Validation** | 191 stable finding codes, three severity levels (error/warning/info), verbose diagnostics |
| **Export** | Jinja2-based ARXML, monolithic or split-by-SWC, deterministic ordering |
| **Diagrams** | Unified `generate diagram` command for PlantUML architecture views |

---

## Quickstart

### Install

**Linux / macOS**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows**
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### A minimal SWC in YAML

```yaml
# swcs/SpeedSensor.yaml
swc:
  name: "SpeedSensor"
  description: "Publishes the current vehicle speed."
  ports:
    - name: "Pp_VehicleSpeed"
      direction: "provides"
      interfaceRef: "If_VehicleSpeed"
    - name: "Pp_PowerState"
      direction: "provides"
      interfaceRef: "If_PowerState"
  runnables:
    - name: "Runnable_PublishVehicleSpeed"
      timingEventMs: 10
      writes:
        - port: "Pp_VehicleSpeed"
          dataElement: "VehicleSpeed"
```

### Typical workflow

```bash
# Initialize a new project scaffold
python -m arforge.cli init my-project

# Validate — stable finding codes on any semantic issue
python -m arforge.cli validate examples/autosar.project.yaml

# Export — monolithic or split by SWC
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc

# Generate architecture diagrams
python -m arforge.cli generate diagram examples/autosar.project.yaml --out build/diagrams
```

The diagram generator writes:
- `composition_<System>.puml`
- `interfaces_wiring.puml`
- `interfaces_contracts.puml`
- `behavior_<SWC>.puml`

### Run tests

```bash
pytest -q
```

> The test suite covers valid and invalid inputs across all supported AUTOSAR constructs. Every validation rule has explicit test cases for both correct and incorrect models.

---

## VS Code integration

ARForge includes a `.vscode/` configuration that enables YAML schema validation, autocompletion, and task runner integration out of the box.

**Required VS Code extensions:**
- [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
- [YAML](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) (Red Hat)

Once installed, open the repository root in VS Code. Schema-backed autocompletion and inline diagnostics activate automatically for all ARForge YAML files.

**Built-in tasks** (accessible via `Terminal → Run Task`):

| Task | Description |
|---|---|
| `arforge: validate project` | Validate the configured project manifest |
| `arforge: export project (split by swc)` | Export ARXML, one file per SWC |
| `arforge: export project (monolithic)` | Export ARXML as a single file |
| `arforge: init project` | Scaffold a new project |
| `arforge: pytest` | Run the full test suite |

**Configuring the project file** — set the active project manifest in `.vscode/settings.json`:

```jsonc
"arforge.projectFile": "examples/autosar.project.yaml"
```

All tasks resolve this path at runtime, so switching between projects requires changing only this one setting.

---

## Documentation

Start with [docs/index.md](docs/index.md).

| Doc | Contents |
|---|---|
| [Overview](docs/overview.md) | What ARForge does and where it fits in a workflow |
| [Project Structure](docs/project-structure.md) | Project manifest, scaffold layout, and build output |
| [Modeling Concepts](docs/modeling-concepts.md) | Full YAML modeling reference with examples |
| [Validation](docs/validation.md) | All 191 finding codes explained |
| [CLI](docs/cli.md) | All commands and options |
| [Architecture](docs/architecture.md) | Internal pipeline, for contributors |
| [Roadmap](docs/roadmap.md) | Current capabilities and planned features |

---

## Contributing

Issues and pull requests are welcome. See `CONTRIBUTING.md` for contribution expectations and the maintainer-led project model.

---

## License

Apache-2.0. See `DISCLAIMER.md` for project independence and affiliation notes.

---

## Contact

**Bojan Zivkovic** — questions, feedback, collaboration, or consulting inquiries welcome via [LinkedIn](https://www.linkedin.com/in/bojanzivkovic86) or GitHub Issues.
