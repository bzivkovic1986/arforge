# YAML Model

## Aggregator project file

Example:

```yaml
autosar:
  version: "4.2"
  rootPackage: "DEMO"

inputs:
  baseTypes: "platform/base_types.yaml"
  implementationDataTypes: "types/implementation_types.yaml"
  applicationDataTypes: "types/application_types.yaml"
  units:
    - "units/*.yaml"
  compuMethods:
    - "compu_methods/*.yaml"
  interfaces:
    - "interfaces/*.yaml"
  swcs:
    - "swcs/*.yaml"
  system: "system.yaml"
```

## Interface files

Sender-receiver:

```yaml
interface:
  name: "If_VehicleSpeed"
  type: "senderReceiver"
  dataElements:
    - name: "VehicleSpeed"
      typeRef: "App_VehicleSpeed"
```

Client-server:

```yaml
interface:
  name: "If_Diagnostics"
  type: "clientServer"
  operations:
    - name: "ReadDTC"
      arguments:
        - name: "DtcId"
          direction: "in"
          typeRef: "UInt16"
      returnType: "UInt16"
```

## SWC files

Runnables can be cyclic (`timingEventMs`) or operation-triggered (`operationInvokedEvents`) but not both.

```yaml
swc:
  name: "SpeedSensor"
  runnables:
    - name: "Runnable_ReadSpeed"
      timingEventMs: 10
    - name: "Runnable_DiagServer"
      operationInvokedEvents:
        - port: "Pp_Diag"
          operation: "ReadDTC"
  ports:
    - name: "Pp_Diag"
      direction: "provides"
      interfaceRef: "If_Diagnostics"
```

## System files

Endpoints are `Instance.Port`:

```yaml
system:
  name: "DemoSystem"
  composition:
    name: "Composition_DemoSystem"
    components:
      - name: "SpeedSensor_1"
        typeRef: "SpeedSensor"
    connectors:
      - from: "SpeedSensor_1.Pp_VehicleSpeed"
        to: "SpeedConsumer_1.Rp_VehicleSpeed"
        dataElement: "VehicleSpeed"
```
