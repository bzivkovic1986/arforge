# ARForge

ARForge is a developer-oriented AUTOSAR Classic modeling tool that lets you define software components in human-friendly **YAML** (with editor validation) and generate **ARXML** using **Jinja2** templates.

It’s intentionally built around a simple pipeline:

**YAML → JSON-Schema validation → semantic checks → internal model → Jinja2 → ARXML**

## What you get today

- AUTOSAR Classic **4.2**
- One YAML per SWC (`swcs/*.yaml`)
- One YAML per interface (`interfaces/*.yaml`)
- One system YAML (`system.yaml`) with explicit composition (component prototypes + connectors)
- Legacy `connections.yaml` is still accepted for migration (implicit one-instance-per-SWC behavior)
- Sender-Receiver interfaces + ports
- Client-Server interfaces + ports
- Glob support in `autosar.project.yaml`
- Export split into:
  - `shared.arxml` (datatypes + interfaces)
  - `<SWC>.arxml` (one per component)
  - `system.arxml` (system + connectors)

## Repo layout

```
arforge/                 # Python package
schemas/                 # JSON Schemas for YAML authoring
templates/               # Jinja2 ARXML templates
examples/                # example AUTOSAR project
.vscode/                 # VS Code schema mapping + tasks
requirements.txt
README.md
```

## Setup (Windows + Linux)

### 1) Create venv and install deps
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2) Validate the example project
```bash
python -m arforge.cli validate examples/autosar.project.yaml
```

Verbose validation:
```bash
# Show validation case execution (RUN/SKIP/FAIL)
python -m arforge.cli validate examples/autosar.project.yaml -v

# Add per-case timing and finding counts
python -m arforge.cli validate examples/autosar.project.yaml -vv
```

### 3) Export ARXML (split output)
```bash
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc
```

Outputs:
- `build/out/shared.arxml`
- `build/out/<SWC>.arxml`
- `build/out/system.arxml`

Verbose export:
```bash
# Show resolved input files, layout, and templates
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc -v

# Add model counts, stage timings, and output sizes
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc -vv
```

## YAML model examples

### Sender-Receiver interface
```yaml
interface:
  name: "If_VehicleSpeed"
  type: "senderReceiver"
  dataElements:
    - name: "VehicleSpeed"
      typeRef: "UInt16"
```

### Client-Server interface
```yaml
interface:
  name: "If_Diagnostics"
  type: "clientServer"
  operations:
    - name: "ReadDTC"
```

### SWC port referencing an interface
```yaml
ports:
  - name: "Pp_Diag"
    direction: "provides"
    interfaceRef: "If_Diagnostics"
```

### System (composition-based)
`from`/`to` endpoints are `INSTANCE.PORT`.
`dataElement` and `operation` are optional selectors validated against interface type.

```yaml
system:
  name: "DemoSystem"
  composition:
    name: "Composition_DemoSystem"
    components:
      - name: "SpeedSensor_1"
        typeRef: "SpeedSensor"
      - name: "SpeedConsumer_1"
        typeRef: "SpeedConsumer"
    connectors:
      - from: "SpeedSensor_1.Pp_VehicleSpeed"
        to: "SpeedConsumer_1.Rp_VehicleSpeed"
        dataElement: "VehicleSpeed"
      - from: "SpeedSensor_1.Pp_Diag"
        to: "SpeedConsumer_1.Rp_Diag"
        operation: "ReadDTC"
```

## VS Code
Install:
- **YAML** extension (Red Hat)
- **Python** extension (Microsoft)

This repo includes `.vscode/settings.json` which maps schemas to the YAML files, so you get validation and autocomplete while editing.

## Contact

For questions, ideas or commerical usage of this project, feel free to reach out:
- Email: bojan.zivkovic.ns@gmail.com
- Linkedin: [Bojan Zivkovic](https://www.linkedin.com/in/bojanzivkovic86)

