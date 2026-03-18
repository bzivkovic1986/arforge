# YAML Model

## Aggregator project file

Example:

```yaml
autosar:
  version: "4.2"
  rootPackage: "DEMO"

inputs:
  baseTypes: "types/base_types.yaml"
  implementationDataTypes: "types/implementation_types.yaml"
  applicationDataTypes: "types/application_types.yaml"
  units:
    - "units/units.yaml"
  compuMethods:
    - "compu_methods/compu_methods.yaml"
  interfaces:
    - "interfaces/If_VehicleSpeed.yaml"
  swcs:
    - "swcs/SpeedSensor.yaml"
    - "swcs/SpeedDisplay.yaml"
  system: "system.yaml"
```

## Compu methods

Linear:

```yaml
compuMethods:
  - name: "CM_VehicleSpeed_Kph"
    category: "linear"
    unitRef: "km_per_h"
    factor: 1.0
    offset: 0.0
    physMin: 0
    physMax: 250
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
    implementationTypeRef: "Impl_VehicleSpeed_U16"
    constraint:
      min: 0
      max: 250
```

Constraint range validation for integer base types uses base type metadata:

- unsigned: `0 .. (2^bitLength - 1)`
- signed: `-(2^(bitLength-1)) .. (2^(bitLength-1) - 1)`

## Base type files

`baseTypes` entries use explicit metadata:

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
- `calls`: list of `{ port, operation, timeoutMs? }` for client-server requires ports
- `ports[*].comSpec`: optional communication specification (sender-receiver or client-server)

Supported SWC categories:

- `application` -> exported as `APPLICATION-SW-COMPONENT-TYPE`
- `service` -> exported as `SERVICE-SW-COMPONENT-TYPE`
- `complexDeviceDriver` -> exported as `COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE`

If `category` is omitted, ARForge defaults to `application`.

```yaml
swc:
  name: "SpeedDisplay"
  category: "application"
  runnables:
    - name: "Runnable_ReadVehicleSpeed"
      timingEventMs: 10
      reads:
        - port: "Rp_VehicleSpeed"
          dataElement: "VehicleSpeed"
  ports:
    - name: "Rp_VehicleSpeed"
      direction: "requires"
      interfaceRef: "If_VehicleSpeed"
```

ComSpec rules:

- SenderReceiver:
  - `mode` is required (`implicit | explicit | queued`)
  - `mode: queued` requires `queueLength` with integer value `>= 1`
  - `mode: implicit` and `mode: explicit` must not define `queueLength`
  - `callMode` and `timeoutMs` are not allowed
- ClientServer:
  - `callMode` is required (`synchronous | asynchronous`)
  - `timeoutMs` must be integer `>= 0` when present
  - `timeoutMs` is allowed only when `callMode: synchronous`
  - `mode` and `queueLength` are not allowed
- Runnable calls:
  - `timeoutMs` is optional integer `>= 0`
  - `timeoutMs` is valid only when the referenced client port call mode is synchronous
  - when client-server `comSpec.callMode` is absent, ARForge uses existing default synchronous behavior

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
      - name: "SpeedDisplay_1"
        typeRef: "SpeedDisplay"
    connectors:
      - from: "SpeedSensor_1.Pp_VehicleSpeed"
        to: "SpeedDisplay_1.Rp_VehicleSpeed"
```

System connectors are port-level only. SenderReceiver data-element usage belongs in runnable `reads`, `writes`, and `dataReceiveEvents`. ClientServer operation usage belongs in runnable `calls`, `operationInvokedEvents`, and `raisesErrors`; connector-level `operation` is not supported.
