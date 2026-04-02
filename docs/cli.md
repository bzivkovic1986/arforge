# CLI Reference

All ARForge commands are run as a Python module. The syntax is the same on Linux and Windows.

```bash
python -m arforge.cli <command> [options]
```

---

## `init`

Create a new project scaffold at the given path.

```bash
python -m arforge.cli init <path> [options]
```

**Options:**

| Option | Description |
|---|---|
| `--name NAME` | System name used in scaffolded files. Defaults to the directory name. |
| `--no-example` | Create the directory structure without the runnable example SWCs and interfaces. |
| `--force` | Allow scaffolding into an existing non-empty directory. |

**Examples:**

```bash
python -m arforge.cli init my-ecu
python -m arforge.cli init my-ecu --name MyEcu --no-example
```

The scaffold creates a ready-to-validate project with a working example — a `SpeedSensor` and `SpeedDisplay` SWC wired together through a sender-receiver and a mode-switch flow. Use `--no-example` if you want only the directory structure.

---

## `validate`

Load a project manifest and run full validation — schema validation followed by semantic validation.

```bash
python -m arforge.cli validate <project.yaml> [options]
```

**Options:**

| Option | Description |
|---|---|
| `-v` | Verbose — show per-case execution information. |
| `-vv` | Very verbose — show case descriptions and full execution detail. |

**Exit codes:**

| Code | Meaning |
|---|---|
| `0` | Validation passed — no error-severity findings |
| `1` | One or more error-severity findings exist |

Warnings and infos are always reported but never cause a non-zero exit.

**Examples:**

```bash
# Basic validation
python -m arforge.cli validate examples/autosar.project.yaml

# With verbose output
python -m arforge.cli validate examples/autosar.project.yaml -vv

# In CI — fail the pipeline on any error finding
python -m arforge.cli validate examples/autosar.project.yaml || exit 1
```

**Output format:**

```
[ERROR]   CORE-022-READ-UNKNOWN-PORT   Runnable 'Runnable_UseSpeed': read references unknown port 'Rp_Missing'
[WARNING] CORE-050                     SR consumer 'SpeedConsumer_1.Rp_VehicleSpeed' runs faster than producer

Summary: 1 error, 1 warning, 0 info
```

---

## `export`

Validate the project and, if validation passes, export ARXML.

```bash
python -m arforge.cli export <project.yaml> --out <path> [options]
```

**Options:**

| Option | Description |
|---|---|
| `--out PATH` | Output path. Required. For split export, a directory path. For monolithic export, a file path ending in `.arxml`. |
| `--split-by-swc` | Split output into shared types, one file per SWC, and a system file. |
| `--templates DIR` | Use an alternate Jinja2 template directory instead of the built-in templates. |
| `-v` | Verbose output. |
| `-vv` | Very verbose output. |

**Export is blocked if validation reports any error-severity findings.** Warnings do not block export.

**Split export:**

```bash
python -m arforge.cli export examples/autosar.project.yaml --out build/out --split-by-swc
```

Produces:

```
build/out/
├── DEMO_SharedTypes.arxml
├── SpeedSensor.arxml
├── SpeedDisplay.arxml
└── Composition_DemoSystem.arxml
```

**Monolithic export:**

```bash
python -m arforge.cli export examples/autosar.project.yaml --out build/all.arxml
```

**Custom templates** — for OEM-specific ARXML profiles:

```bash
python -m arforge.cli export examples/autosar.project.yaml --out build/out --templates my-templates/
```

The custom template directory must contain the same template filenames as the built-in `templates/` directory. This is the designed extension point for OEM-specific ARXML conventions without modifying ARForge core.

---

## `generate diagram`

Validate the project and generate the standard architecture diagram set.

```bash
python -m arforge.cli generate diagram <project.yaml> --out <dir>
```

**Options:**

| Option | Description |
|---|---|
| `--out DIR` | Output directory for generated diagram files. Required. |

**Generated views:**

| File pattern | Purpose |
|---|---|
| `composition_<System>.<ext>` | Composition / topology view with instances, ports, and connectors |
| `interfaces_wiring.<ext>` | Interface wiring view with component instances, instantiated ports, and referenced interfaces |
| `interfaces_contracts.<ext>` | Interface contract view with interfaces, referenced types, compu methods, and mode groups |
| `behavior_<SWC>.<ext>` | Behavior view per SWC type with ports, runnables, and behavior relations |

**Examples:**

```bash
python -m arforge.cli generate diagram examples/autosar.project.yaml --out build/diagrams_plantuml
```

The command generates the standard view set as PlantUML source files.

---

## `generate code`

Validate the project and generate starter SWC code skeletons.

```bash
python -m arforge.cli generate code <project.yaml> --out <dir> [options]
```

**Options:**

| Option | Description |
|---|---|
| `--out DIR` | Output directory for generated code files. Required. |
| `--lang TEXT` | Code generation backend. Currently `c`. |
| `--templates DIR` | Use an alternate Jinja2 template directory instead of the built-in templates. |

**Generated files:**

For each SWC type, ARForge writes:

| File pattern | Purpose |
|---|---|
| `<SwcName>.h` | Generated runnable declarations with include guard |
| `<SwcName>.c` | Generated runnable stubs with modeled trigger comments and RTE placeholder usage |

**Examples:**

```bash
python -m arforge.cli generate code examples/autosar.project.yaml --lang c --out build/code
```

The generated output is a deterministic starter skeleton, not a complete AUTOSAR RTE integration or application implementation.

---

## Running via VS Code tasks

If you are working in VS Code, all commands above are available as pre-configured tasks under `Terminal → Run Task`. The active project manifest is resolved from the `arforge.projectFile` setting in `.vscode/settings.json`.

See [Project Structure — VS Code setup](./project-structure.md#vs-code-setup) for details.

---

## CI integration

ARForge is designed to run in CI without modification. A minimal pipeline step:

```bash
# Validate on every pull request
python -m arforge.cli validate autosar.project.yaml

# Export on merge to main
python -m arforge.cli export autosar.project.yaml --out build/arxml --split-by-swc
```

Since validation findings are sorted deterministically and finding codes are stable across versions, CI output is consistent and finding codes can be used in suppression lists or pipeline conditions.
