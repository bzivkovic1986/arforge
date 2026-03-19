from __future__ import annotations

from pathlib import Path
from typing import Dict


def _with_header(*header_lines: str, body: str) -> str:
    header = "\n".join(f"# {line}" for line in header_lines)
    return f"{header}\n{body}"


def project_yaml(system_name: str) -> str:
    return _with_header(
        "ARForge: Project input manifest",
        "Lists the YAML files that make up this AUTOSAR project.",
        body=f"""autosar:
  version: "4.2"
  rootPackage: "{system_name.upper()}"

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
""",
    )


def readme_md(system_name: str, *, no_example: bool = False) -> str:
    example_note = (
        "This scaffold includes a small runnable sender-receiver example:\n\n"
        "- `types/` defines reusable data types.\n"
        "- `modes/power_state.yaml` defines a simple mode declaration group.\n"
        "- `interfaces/If_VehicleSpeed.yaml` and `interfaces/If_PowerState.yaml` define the example interfaces used by ports.\n"
        "- `swcs/SpeedSensor.yaml` and `swcs/SpeedDisplay.yaml` define SWC types with both data and mode ports.\n"
        "- `system.yaml` instantiates those SWC types as component prototypes and connects both flows.\n"
    )
    if no_example:
        example_note = (
            "This scaffold creates the project structure without example interfaces or SWCs.\n\n"
            "- Add reusable data types under `types/`.\n"
            "- Update the mode declaration groups under `modes/`.\n"
            "- Add interface definitions under `interfaces/`.\n"
            "- Add SWC type definitions under `swcs/`.\n"
            "- Define component instances and connectors in `system.yaml`.\n"
        )
    return f"""# {system_name}

ARForge project scaffold for AUTOSAR Classic modeling.

{example_note}
Validate the project:

```bash
python -m arforge.cli validate autosar.project.yaml
```

Export ARXML:

```bash
python -m arforge.cli export autosar.project.yaml --out build/out --split-by-swc
```
"""


def base_types_yaml() -> str:
    return _with_header(
        "ARForge: Base type definitions",
        "Defines low-level platform types used by implementation data types.",
body="""baseTypes:
  - name: "uint8"
    description: "Unsigned 8-bit platform integer."
    bitLength: 8
    signedness: "unsigned"
    nativeDeclaration: "uint8"
  - name: "uint16"
    description: "Unsigned 16-bit platform integer."
    bitLength: 16
    signedness: "unsigned"
    nativeDeclaration: "uint16"
""",
    )


def implementation_types_yaml() -> str:
    return _with_header(
        "ARForge: Implementation data types",
        "Defines type-level implementation data types backed by platform base types.",
body="""implementationDataTypes:
  - name: "Impl_VehicleSpeed_U16"
    description: "Raw implementation type for a vehicle speed sample."
    baseTypeRef: "uint16"
""",
    )


def application_types_yaml() -> str:
    return _with_header(
        "ARForge: Application data types",
        "Defines project-level application types used by interfaces.",
body="""applicationDataTypes:
  - name: "App_VehicleSpeed"
    description: "Vehicle speed value shared between the demo SWC types."
    implementationTypeRef: "Impl_VehicleSpeed_U16"
    constraint:
      min: 0
      max: 250
    unitRef: "km_per_h"
    compuMethodRef: "CM_VehicleSpeed_Kph"
""",
    )


def units_yaml() -> str:
    return _with_header(
        "ARForge: Units",
        "Physical units referenced by application data types and compu methods.",
body="""units:
  - name: "km_per_h"
    description: "Vehicle speed unit used by the scaffolded example."
    displayName: "km/h"
""",
    )


def compu_methods_yaml() -> str:
    return _with_header(
        "ARForge: Compu methods",
        "Simple physical scaling definitions for application data types.",
body="""compuMethods:
  - name: "CM_VehicleSpeed_Kph"
    description: "Identity scaling for the demo vehicle speed value."
    category: "linear"
    unitRef: "km_per_h"
    factor: 1.0
    offset: 0.0
    physMin: 0
    physMax: 250
""",
    )


def mode_declaration_groups_yaml() -> str:
    return _with_header(
        "ARForge: Mode declaration groups",
        "Defines AUTOSAR mode declaration groups used by mode-switch interfaces.",
body="""modeDeclarationGroups:
  - name: "Mdg_PowerState"
    description: "Power state modes used by the scaffolded mode-switch interface."
    initialMode: "OFF"
    modes:
      - "OFF"
      - "ON"
      - "SLEEP"
""",
    )


def interface_vehicle_speed_yaml() -> str:
    return _with_header(
        "ARForge: Interface definition",
        "Defines a Sender-Receiver, Client-Server, or Mode-Switch interface used by SWC ports.",
body="""interface:
  name: "If_VehicleSpeed"
  description: "Sender-receiver interface for the current vehicle speed."
  type: "senderReceiver"
  dataElements:
    - name: "VehicleSpeed"
      description: "Latest measured vehicle speed sample."
      typeRef: "App_VehicleSpeed"
""",
    )


def interface_power_state_yaml() -> str:
    return _with_header(
        "ARForge: Interface definition",
        "Defines a Sender-Receiver, Client-Server, or Mode-Switch interface used by SWC ports.",
body="""interface:
  name: "If_PowerState"
  description: "Mode switch interface for ECU power state."
  type: "modeSwitch"
  modeGroupRef: "Mdg_PowerState"
""",
    )


def swc_speed_sensor_yaml() -> str:
    return _with_header(
        "ARForge: Software Component Type",
        "Defines ports, runnables, and internal behavior for one AUTOSAR SWC type.",
body="""swc:
  name: "SpeedSensor"
  description: "SWC type that publishes the current vehicle speed."
  runnables:
    - name: "Runnable_PublishVehicleSpeed"
      description: "Writes the latest vehicle speed sample to the provided port."
      timingEventMs: 10
      writes:
        - port: "Pp_VehicleSpeed"
          dataElement: "VehicleSpeed"
  ports:
    - name: "Pp_VehicleSpeed"
      description: "Provided sender-receiver port for publishing speed."
      direction: "provides"
      interfaceRef: "If_VehicleSpeed"
    - name: "Pp_PowerState"
      description: "Provided mode switch port for ECU power state."
      direction: "provides"
      interfaceRef: "If_PowerState"
""",
    )


def swc_speed_display_yaml() -> str:
    return _with_header(
        "ARForge: Software Component Type",
        "Defines ports, runnables, and internal behavior for one AUTOSAR SWC type.",
body="""swc:
  name: "SpeedDisplay"
  description: "SWC type that reads vehicle speed and could display it to a user."
  runnables:
    - name: "Runnable_ReadVehicleSpeed"
      description: "Reads the latest vehicle speed sample from the required port."
      timingEventMs: 10
      reads:
        - port: "Rp_VehicleSpeed"
          dataElement: "VehicleSpeed"
  ports:
    - name: "Rp_VehicleSpeed"
      description: "Required sender-receiver port for receiving speed."
      direction: "requires"
      interfaceRef: "If_VehicleSpeed"
    - name: "Rp_PowerState"
      description: "Required mode switch port for ECU power state."
      direction: "requires"
      interfaceRef: "If_PowerState"
""",
    )


def system_yaml(system_name: str) -> str:
    return _with_header(
        "ARForge: System composition",
        "Defines component prototypes (instances) and connectors between their ports.",
body=f"""system:
  name: "{system_name}"
  description: "Demo AUTOSAR system wiring one speed flow and one mode-switch flow."
  composition:
    name: "Composition_{system_name}"
    description: "Top-level composition for the scaffolded sender-receiver and mode-switch example."
    # These are component prototypes (instances in the system).
    # typeRef points to the SWC type defined in swcs/*.yaml.
    components:
      - name: "SpeedSensor_1"
        description: "Instance of the SpeedSensor SWC type."
        typeRef: "SpeedSensor"
      - name: "SpeedDisplay_1"
        description: "Instance of the SpeedDisplay SWC type."
        typeRef: "SpeedDisplay"
    # Connect the provider ports on the producer instance to the receiver ports on the consumer instance.
    connectors:
      - from: "SpeedSensor_1.Pp_VehicleSpeed"
        description: "Connects the published speed sample to the display instance."
        to: "SpeedDisplay_1.Rp_VehicleSpeed"
      - from: "SpeedSensor_1.Pp_PowerState"
        description: "Connects the ECU power-state mode to the display instance."
        to: "SpeedDisplay_1.Rp_PowerState"
""",
    )


def structure_only_system_yaml(system_name: str) -> str:
    return _with_header(
        "ARForge: System composition",
        "Add components and connectors here when you are ready to model the system.",
        body=f"""# Example shape:
# system:
#   name: "{system_name}"
#   composition:
#     name: "Composition_{system_name}"
#     components:
#       - name: "MyComponent_1"
#         typeRef: "MyComponent"
#     connectors:
#       - from: "MyProvider_1.Pp_Port"
#         to: "MyConsumer_1.Rp_Port"
""",
    )


def scaffold_files(system_name: str, *, no_example: bool = False) -> Dict[Path, str]:
    files: Dict[Path, str] = {
        Path("README.md"): readme_md(system_name, no_example=no_example),
        Path("autosar.project.yaml"): project_yaml(system_name),
        Path("types/base_types.yaml"): base_types_yaml(),
        Path("types/implementation_types.yaml"): implementation_types_yaml(),
        Path("types/application_types.yaml"): application_types_yaml(),
        Path("units/units.yaml"): units_yaml(),
        Path("compu_methods/compu_methods.yaml"): compu_methods_yaml(),
        Path("modes/power_state.yaml"): mode_declaration_groups_yaml(),
    }

    if no_example:
        files[Path("system.yaml")] = structure_only_system_yaml(system_name)
        return files

    files[Path("interfaces/If_VehicleSpeed.yaml")] = interface_vehicle_speed_yaml()
    files[Path("interfaces/If_PowerState.yaml")] = interface_power_state_yaml()
    files[Path("swcs/SpeedSensor.yaml")] = swc_speed_sensor_yaml()
    files[Path("swcs/SpeedDisplay.yaml")] = swc_speed_display_yaml()
    files[Path("system.yaml")] = system_yaml(system_name)
    return files


def scaffold_project(path: Path, *, name: str = "DemoSystem", force: bool = False, no_example: bool = False) -> list[Path]:
    target = path.resolve()
    if target.exists() and any(target.iterdir()) and not force:
        raise FileExistsError(f"Target path exists and is not empty: {target}")

    target.mkdir(parents=True, exist_ok=True)
    files = scaffold_files(name, no_example=no_example)
    for rel_dir in [
        Path("interfaces"),
        Path("swcs"),
        Path("types"),
        Path("units"),
        Path("compu_methods"),
        Path("modes"),
    ]:
        (target / rel_dir).mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for rel_path in sorted(files.keys(), key=lambda p: p.as_posix()):
        out_path = target / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(files[rel_path], encoding="utf-8")
        written.append(out_path)
    return written
