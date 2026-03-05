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

## Compu methods

Linear:

```yaml
compuMethods:
  - name: "CM_Speed_Kmh_Linear"
    category: "linear"
    unitRef: "km_h"
    factor: 0.1
    offset: 0.0
    physMin: 0
    physMax: 300
```

Text table:

```yaml
compuMethods:
  - name: "CM_DtcStatus"
    category: "textTable"
    entries:
      - value: 0
        label: "OK"
      - value: 1
        label: "Failed"
```

## Application data type constraints

`applicationDataTypes[*]` may define an optional numeric range:

```yaml
applicationDataTypes:
  - name: "App_VehicleSpeed"
    implementationTypeRef: "UInt16"
    constraint:
      min: 0
      max: 300
```

Constraint range validation for integer base types uses base type metadata:

- unsigned: `0 .. (2^bitLength - 1)`
- signed: `-(2^(bitLength-1)) .. (2^(bitLength-1) - 1)`

Legacy base type definitions (`{ name }`) remain valid. For constraint range checks, ARForge currently applies fallback metadata only for `uint8` and `uint16`.

## Base type files

`baseTypes` supports two entry shapes:

- legacy:

```yaml
baseTypes:
  - name: "uint16"
```

- raw metadata:

```yaml
baseTypes:
  - name: "uint16"
    bitLength: 16
    signedness: "unsigned"
    nativeDeclaration: "uint16"
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
      returnType: "App_DtcStatus"
```

## SWC files

Runnables can be cyclic (`timingEventMs`) or operation-triggered (`operationInvokedEvents`) but not both.
Runnables can also declare optional access definitions:

- `reads`: list of `{ port, dataElement }` for sender-receiver requires ports
- `writes`: list of `{ port, dataElement }` for sender-receiver provides ports
- `calls`: list of `{ port, operation }` for client-server requires ports

```yaml
swc:
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
  ports:
    - name: "Rp_VehicleSpeed"
      direction: "requires"
      interfaceRef: "If_VehicleSpeed"
      comSpec:
        mode: "queued"      # implicit | explicit | queued
        queueLength: 8      # required only for queued
    - name: "Rp_Diag"
      direction: "requires"
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
