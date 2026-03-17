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
  baseTypes: "platform/base_types.yaml"
  implementationDataTypes: "types/implementation_types.yaml"
  applicationDataTypes: "types/application_types.yaml"
  units:
    - "units/units.yaml"
  compuMethods:
    - "compu_methods/compu_methods.yaml"
  interfaces:
    - "interfaces/*.yaml"
  swcs:
    - "swcs/*.yaml"
  system: "system.yaml"
""",
    )


def base_types_yaml() -> str:
    return _with_header(
        "ARForge: Base type definitions",
        "Platform-specific primitive and raw types.",
        body="""baseTypes:
  - name: "uint8"
    bitLength: 8
    signedness: "unsigned"
    nativeDeclaration: "uint8"
  - name: "uint16"
    bitLength: 16
    signedness: "unsigned"
    nativeDeclaration: "uint16"
""",
    )


def implementation_types_yaml() -> str:
    return _with_header(
        "ARForge: Implementation data types",
        "Maps AUTOSAR implementation types onto platform base types.",
        body="""implementationDataTypes:
  - name: "UInt8"
    baseTypeRef: "uint8"
  - name: "UInt16"
    baseTypeRef: "uint16"
""",
    )


def application_types_yaml() -> str:
    return _with_header(
        "ARForge: Application data types",
        "Project-facing types with optional units and compu methods.",
        body="""applicationDataTypes:
  - name: "App_SystemValue"
    implementationTypeRef: "UInt16"
    constraint:
      min: 0
      max: 1000
    unitRef: "raw_count"
    compuMethodRef: "CM_SystemValue_Identity"
""",
    )


def units_yaml() -> str:
    return _with_header(
        "ARForge: Units",
        "Physical units referenced by application data types and compu methods.",
        body="""units:
  - name: "raw_count"
    displayName: "count"
""",
    )


def compu_methods_yaml() -> str:
    return _with_header(
        "ARForge: Compu methods",
        "Simple physical scaling definitions for application data types.",
        body="""compuMethods:
  - name: "CM_SystemValue_Identity"
    category: "linear"
    unitRef: "raw_count"
    factor: 1.0
    offset: 0.0
    physMin: 0
    physMax: 1000
""",
    )


def interface_system_value_yaml() -> str:
    return _with_header(
        "ARForge: Interface definition",
        "Defines a Sender-Receiver or Client-Server AUTOSAR interface.",
        body="""interface:
  name: "If_SystemValue"
  type: "senderReceiver"
  dataElements:
    - name: "SystemValue"
      typeRef: "App_SystemValue"
""",
    )


def swc_provider_yaml() -> str:
    return _with_header(
        "ARForge: Software Component Type",
        "Defines ports, runnables, and internal behavior.",
        body="""swc:
  name: "SystemValueProvider"
  runnables:
    - name: "Runnable_WriteSystemValue"
      timingEventMs: 10
      writes:
        - port: "Pp_SystemValue"
          dataElement: "SystemValue"
  ports:
    - name: "Pp_SystemValue"
      direction: "provides"
      interfaceRef: "If_SystemValue"
""",
    )


def swc_consumer_yaml() -> str:
    return _with_header(
        "ARForge: Software Component Type",
        "Defines ports, runnables, and internal behavior.",
        body="""swc:
  name: "SystemValueConsumer"
  runnables:
    - name: "Runnable_ReadSystemValue"
      timingEventMs: 10
      reads:
        - port: "Rp_SystemValue"
          dataElement: "SystemValue"
    - name: "Runnable_OnSystemValue"
      dataReceiveEvents:
        - port: "Rp_SystemValue"
          dataElement: "SystemValue"
  ports:
    - name: "Rp_SystemValue"
      direction: "requires"
      interfaceRef: "If_SystemValue"
      comSpec:
        mode: "queued"
        queueLength: 1
""",
    )


def system_yaml(system_name: str) -> str:
    return _with_header(
        "ARForge: System composition",
        "Defines component prototypes and connectors between ports.",
        body=f"""system:
  name: "{system_name}"
  composition:
    name: "Composition_{system_name}"
    components:
      - name: "SystemValueProvider_1"
        typeRef: "SystemValueProvider"
      - name: "SystemValueConsumer_1"
        typeRef: "SystemValueConsumer"
    connectors:
      - from: "SystemValueProvider_1.Pp_SystemValue"
        to: "SystemValueConsumer_1.Rp_SystemValue"
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
        Path("autosar.project.yaml"): project_yaml(system_name),
        Path("platform/base_types.yaml"): base_types_yaml(),
        Path("types/implementation_types.yaml"): implementation_types_yaml(),
        Path("types/application_types.yaml"): application_types_yaml(),
        Path("units/units.yaml"): units_yaml(),
        Path("compu_methods/compu_methods.yaml"): compu_methods_yaml(),
    }

    if no_example:
        files[Path("system.yaml")] = structure_only_system_yaml(system_name)
        return files

    files[Path("interfaces/If_SystemValue.yaml")] = interface_system_value_yaml()
    files[Path("swcs/SystemValueProvider.yaml")] = swc_provider_yaml()
    files[Path("swcs/SystemValueConsumer.yaml")] = swc_consumer_yaml()
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
        Path("platform"),
        Path("types"),
        Path("units"),
        Path("compu_methods"),
    ]:
        (target / rel_dir).mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for rel_path in sorted(files.keys(), key=lambda p: p.as_posix()):
        out_path = target / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(files[rel_path], encoding="utf-8")
        written.append(out_path)
    return written
