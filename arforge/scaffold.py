from __future__ import annotations

from pathlib import Path
from typing import Dict


def project_yaml(system_name: str) -> str:
    return f"""autosar:
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
"""


def base_types_yaml() -> str:
    return """baseTypes:
  - name: "uint8"
    bitLength: 8
    signedness: "unsigned"
    nativeDeclaration: "uint8"
  - name: "uint16"
    bitLength: 16
    signedness: "unsigned"
    nativeDeclaration: "uint16"
"""


def implementation_types_yaml() -> str:
    return """implementationDataTypes:
  - name: "UInt8"
    baseTypeRef: "uint8"
  - name: "UInt16"
    baseTypeRef: "uint16"
"""


def application_types_yaml() -> str:
    return """applicationDataTypes:
  - name: "App_VehicleSpeed"
    implementationTypeRef: "UInt16"
    constraint:
      min: 0
      max: 300
    unitRef: "km_h"
    compuMethodRef: "CM_Speed_Kmh_Linear"
"""


def units_yaml() -> str:
    return """units:
  - name: "km_h"
    displayName: "km/h"
"""


def compu_methods_yaml() -> str:
    return """compuMethods:
  - name: "CM_Speed_Kmh_Linear"
    category: "linear"
    unitRef: "km_h"
    factor: 0.1
    offset: 0.0
    physMin: 0
    physMax: 300
"""


def interface_vehicle_speed_yaml() -> str:
    return """interface:
  name: "If_VehicleSpeed"
  type: "senderReceiver"
  dataElements:
    - name: "VehicleSpeed"
      typeRef: "App_VehicleSpeed"
"""


def interface_diagnostics_yaml() -> str:
    return """interface:
  name: "If_Diagnostics"
  type: "clientServer"
  operations:
    - name: "ReadDTC"
      arguments:
        - name: "DtcId"
          direction: "in"
          typeRef: "UInt16"
      returnType: "UInt8"
"""


def swc_speed_sensor_yaml() -> str:
    return """swc:
  name: "SpeedSensor"
  runnables:
    - name: "Runnable_ReadSpeed"
      timingEventMs: 10
      writes:
        - port: "Pp_VehicleSpeed"
          dataElement: "VehicleSpeed"
    - name: "Runnable_DiagServer"
      operationInvokedEvents:
        - port: "Pp_Diag"
          operation: "ReadDTC"
  ports:
    - name: "Pp_VehicleSpeed"
      direction: "provides"
      interfaceRef: "If_VehicleSpeed"
    - name: "Pp_Diag"
      direction: "provides"
      interfaceRef: "If_Diagnostics"
"""


def swc_speed_consumer_yaml() -> str:
    return """swc:
  name: "SpeedConsumer"
  runnables:
    - name: "Runnable_UseSpeed"
      timingEventMs: 10
      reads:
        - port: "Rp_VehicleSpeed"
          dataElement: "VehicleSpeed"
      calls:
        - port: "Rp_Diag"
          operation: "ReadDTC"
    - name: "Runnable_OnVehicleSpeed"
      dataReceiveEvents:
        - port: "Rp_VehicleSpeed"
          dataElement: "VehicleSpeed"
  ports:
    - name: "Rp_VehicleSpeed"
      direction: "requires"
      interfaceRef: "If_VehicleSpeed"
      comSpec:
        mode: "queued"
        queueLength: 8
    - name: "Rp_Diag"
      direction: "requires"
      interfaceRef: "If_Diagnostics"
"""


def system_yaml(system_name: str) -> str:
    return f"""system:
  name: "{system_name}"
  composition:
    name: "Composition_{system_name}"
    components:
      - name: "SpeedSensor_1"
        typeRef: "SpeedSensor"
      - name: "SpeedConsumer_1"
        typeRef: "SpeedConsumer"
    connectors:
      - from: "SpeedSensor_1.Pp_VehicleSpeed"
        to: "SpeedConsumer_1.Rp_VehicleSpeed"
      - from: "SpeedSensor_1.Pp_Diag"
        to: "SpeedConsumer_1.Rp_Diag"
        operation: "ReadDTC"
"""


def placeholder_interface_yaml() -> str:
    return """interface:
  name: "If_Data"
  type: "senderReceiver"
  dataElements:
    - name: "Value"
      typeRef: "App_VehicleSpeed"
"""


def placeholder_producer_yaml() -> str:
    return """swc:
  name: "Producer"
  runnables:
    - name: "Runnable_Produce"
      timingEventMs: 10
      writes:
        - port: "Pp_Data"
          dataElement: "Value"
  ports:
    - name: "Pp_Data"
      direction: "provides"
      interfaceRef: "If_Data"
"""


def placeholder_consumer_yaml() -> str:
    return """swc:
  name: "Consumer"
  runnables:
    - name: "Runnable_Consume"
      timingEventMs: 10
      reads:
        - port: "Rp_Data"
          dataElement: "Value"
    - name: "Runnable_OnData"
      dataReceiveEvents:
        - port: "Rp_Data"
          dataElement: "Value"
  ports:
    - name: "Rp_Data"
      direction: "requires"
      interfaceRef: "If_Data"
      comSpec:
        mode: "queued"
        queueLength: 1
"""


def placeholder_system_yaml(system_name: str) -> str:
    return f"""system:
  name: "{system_name}"
  composition:
    name: "Composition_{system_name}"
    components:
      - name: "Producer_1"
        typeRef: "Producer"
      - name: "Consumer_1"
        typeRef: "Consumer"
    connectors:
      - from: "Producer_1.Pp_Data"
        to: "Consumer_1.Rp_Data"
"""


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
        files[Path("interfaces/placeholder_interface.yaml")] = placeholder_interface_yaml()
        files[Path("swcs/producer.yaml")] = placeholder_producer_yaml()
        files[Path("swcs/consumer.yaml")] = placeholder_consumer_yaml()
        files[Path("system.yaml")] = placeholder_system_yaml(system_name)
        return files

    files[Path("interfaces/If_VehicleSpeed.yaml")] = interface_vehicle_speed_yaml()
    files[Path("interfaces/If_Diagnostics.yaml")] = interface_diagnostics_yaml()
    files[Path("swcs/SpeedSensor.yaml")] = swc_speed_sensor_yaml()
    files[Path("swcs/SpeedConsumer.yaml")] = swc_speed_consumer_yaml()
    files[Path("system.yaml")] = system_yaml(system_name)
    return files


def scaffold_project(path: Path, *, name: str = "DemoSystem", force: bool = False, no_example: bool = False) -> list[Path]:
    target = path.resolve()
    if target.exists() and any(target.iterdir()) and not force:
        raise FileExistsError(f"Target path exists and is not empty: {target}")

    target.mkdir(parents=True, exist_ok=True)
    files = scaffold_files(name, no_example=no_example)
    written: list[Path] = []
    for rel_path in sorted(files.keys(), key=lambda p: p.as_posix()):
        out_path = target / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(files[rel_path], encoding="utf-8")
        written.append(out_path)
    return written
