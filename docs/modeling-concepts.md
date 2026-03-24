# Modeling Concepts

This page explains the ARForge YAML modeling language. It covers every supported construct with examples drawn from real project files.

---

## Data types

ARForge models the AUTOSAR type system in three layers, matching the AUTOSAR metamodel.

### Base types

Base types define the raw platform integers. They are the foundation everything else builds on.

```yaml
baseTypes:
  - name: "uint8"
    bitLength: 8
    signedness: "unsigned"
    nativeDeclaration: "uint8"
  - name: "uint16"
    bitLength: 16
    signedness: "unsigned"
    nativeDeclaration: "uint16"
```

### Implementation data types

Implementation data types are backed by a base type. ARForge supports scalar, array, and struct kinds.

```yaml
implementationDataTypes:
  # scalar
  - name: "Impl_VehicleSpeed_U16"
    baseTypeRef: "uint16"

  # array
  - name: "Impl_SpeedBuffer"
    array:
      elementTypeRef: "Impl_VehicleSpeed_U16"
      length: 8

  # struct
  - name: "Impl_SpeedPacket"
    struct:
      fields:
        - name: "Speed"
          typeRef: "Impl_VehicleSpeed_U16"
        - name: "Timestamp"
          typeRef: "Impl_Timestamp_U32"
```

Struct field references must resolve to other implementation types. Circular struct references are caught by `CORE-010-STRUCT-CYCLE`.

### Application data types

Application types add physical meaning to implementation types — units, constraints, and scaling via compu methods.

```yaml
applicationDataTypes:
  - name: "App_VehicleSpeed"
    implementationTypeRef: "Impl_VehicleSpeed_U16"
    constraint:
      min: 0
      max: 250
    unitRef: "km_per_h"
    compuMethodRef: "CM_VehicleSpeed_Kph"
```

All references are validated. Constraints are checked against the base type range.

### Units and compu methods

```yaml
# units/units.yaml
units:
  - name: "km_per_h"
    displayName: "km/h"

# compu_methods/compu_methods.yaml
compuMethods:
  - name: "CM_VehicleSpeed_Kph"
    category: "linear"
    unitRef: "km_per_h"
    factor: 1.0
    offset: 0.0
    physMin: 0
    physMax: 250
```

Supported compu method categories are `linear` and `textTable`. A `textTable` compu method defines an enumeration:

```yaml
compuMethods:
  - name: "CM_PowerState"
    category: "textTable"
    unitRef: "NoUnit"
    entries:
      - value: 0
        label: "OFF"
      - value: 1
        label: "ON"
      - value: 2
        label: "SLEEP"
```

---

## Mode declaration groups

Mode declaration groups define the named mode sets used by mode-switch interfaces and ports. They are first-class model artifacts, defined separately from interfaces so they can be shared across multiple interfaces.

```yaml
# modes/power_state.yaml
modeDeclarationGroups:
  - name: "Mdg_PowerState"
    description: "Power state modes for the ECU."
    initialMode: "OFF"
    modes:
      - "OFF"
      - "ON"
      - "SLEEP"
```

`initialMode` must be one of the declared modes (`CORE-013`). Duplicate mode names are caught by `CORE-012`. Mode declaration groups that are never referenced by any mode-switch interface produce a `CORE-014` warning.

---

## Interfaces

ARForge supports three interface kinds: `senderReceiver`, `clientServer`, and `modeSwitch`.

### Sender-receiver interfaces

```yaml
interface:
  name: "If_VehicleSpeed"
  type: "senderReceiver"
  dataElements:
    - name: "VehicleSpeed"
      typeRef: "App_VehicleSpeed"
```

Each data element references an application data type. Multiple data elements per interface are supported.

### Client-server interfaces

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
        - name: "DtcState"
          direction: "out"
          typeRef: "UInt8"
        - name: "OccurrenceCounter"
          direction: "inout"
          typeRef: "UInt16"
      returnType: "UInt8"
      possibleErrors:
        - name: "DTC_NOT_FOUND"
          code: 1
        - name: "MEMORY_ERROR"
          code: 2
    - name: "ClearDTC"
      returnType: "void"
```

Argument directions are `in`, `out`, and `inout`. `returnType` is required; use `"void"` for operations with no return value. `possibleErrors` are optional and define the server-side errors a runnable can raise.

### Mode-switch interfaces

```yaml
interface:
  name: "If_PowerState"
  type: "modeSwitch"
  modeGroupRef: "Mdg_PowerState"
```

A mode-switch interface holds a single reference to a `ModeDeclarationGroup`. The group must be defined in a `modes/*.yaml` file loaded by the project manifest.

---

## SWC types

An SWC type defines the reusable blueprint — ports, runnables, behavior. Instances of the type appear in the system composition.

```yaml
swc:
  name: "SpeedSensor"
  description: "Publishes vehicle speed."
  category: "application"         # application | service | complexDeviceDriver
  ports:
    - ...
  runnables:
    - ...
```

### Ports

Every port references an interface by name and declares its direction.

```yaml
ports:
  # sender-receiver provide port
  - name: "Pp_VehicleSpeed"
    direction: "provides"
    interfaceRef: "If_VehicleSpeed"

  # sender-receiver require port with ComSpec
  - name: "Rp_VehicleSpeed"
    direction: "requires"
    interfaceRef: "If_VehicleSpeed"
    comSpec:
      mode: "queued"
      queueLength: 8

  # client-server require port
  - name: "Rp_Diag"
    direction: "requires"
    interfaceRef: "If_Diagnostics"
    comSpec:
      callMode: "synchronous"
      timeoutMs: 50

  # client-server require port, asynchronous
  - name: "Rp_DiagAsync"
    direction: "requires"
    interfaceRef: "If_Diagnostics"
    comSpec:
      callMode: "asynchronous"

  # mode-switch provide port (mode manager side)
  - name: "Pp_PowerState"
    direction: "provides"
    interfaceRef: "If_PowerState"

  # mode-switch require port (mode user side)
  - name: "Rp_PowerState"
    direction: "requires"
    interfaceRef: "If_PowerState"
```

**SR ComSpec modes:** `implicit`, `explicit`, `queued`. Queued ports require `queueLength >= 1`.

**CS ComSpec call modes:** `synchronous`, `asynchronous`. Synchronous ports may specify `timeoutMs`. Asynchronous ports must not carry `timeoutMs` or `queueLength`.

**Mode-switch ports** do not support ComSpec.

Ports that are declared but never used by any runnable produce `CORE-046` warnings. This applies to all interface kinds and both port directions.

### Runnables and events

Each runnable uses exactly one trigger. Mixing trigger styles is caught by `CORE-024`.

**Timing event** — cyclic execution:

```yaml
runnables:
  - name: "Runnable_PublishSpeed"
    timingEventMs: 10
    writes:
      - port: "Pp_VehicleSpeed"
        dataElement: "VehicleSpeed"
```

**Init event** — executed once at startup:

```yaml
runnables:
  - name: "Runnable_Init"
    initEvent: true
```

**Data receive event** — triggered when data arrives on a required SR port:

```yaml
runnables:
  - name: "Runnable_OnVehicleSpeed"
    dataReceiveEvents:
      - port: "Rp_VehicleSpeed"
        dataElement: "VehicleSpeed"
```

**Operation invoked event** — triggered when a client calls an operation on a provided CS port:

```yaml
runnables:
  - name: "Runnable_OnReadDTC"
    operationInvokedEvents:
      - port: "Pp_Diag"
        operation: "ReadDTC"
```

**Mode switch event** — triggered when the system enters a specific mode:

```yaml
runnables:
  - name: "Runnable_OnPowerOn"
    modeSwitchEvents:
      - port: "Rp_PowerState"
        mode: "ON"
```

The `port` must be a required mode-switch port. The `mode` must be declared in the referenced `ModeDeclarationGroup`.

### Runnable access definitions

Runnable access definitions describe what a runnable reads, writes, calls, or raises. These are validated against the port direction and interface kind.

```yaml
runnables:
  - name: "Runnable_UseSpeed"
    timingEventMs: 5
    reads:
      - port: "Rp_VehicleSpeed"
        dataElement: "VehicleSpeed"
    calls:
      - port: "Rp_Diag"
        operation: "ReadDTC"
        timeoutMs: 100
      - port: "Rp_DiagAsync"
        operation: "ClearDTC"
```

**`reads`** — SR data element read from a required port. Port must be SR, direction must be `requires`.

**`writes`** — SR data element write to a provided port. Port must be SR, direction must be `provides`.

**`calls`** — CS operation call on a required port. Port must be CS, direction must be `requires`.

**`raisesErrors`** — CS error raised on a provided port. Port must be CS, direction must be `provides`. The error name must appear in `possibleErrors` of the referenced operation.

```yaml
runnables:
  - name: "Runnable_OnReadDTC"
    operationInvokedEvents:
      - port: "Pp_Diag"
        operation: "ReadDTC"
    raisesErrors:
      - port: "Pp_Diag"
        operation: "ReadDTC"
        error: "DTC_NOT_FOUND"
```

---

## System composition

The system file defines the composition — which SWC types are instantiated and how their ports are connected.

### The type vs. instance distinction

This distinction is fundamental in AUTOSAR and ARForge models it correctly:

- An SWC type is defined in `swcs/SpeedSensor.yaml`. It is the reusable blueprint.
- A component prototype is an instance of that type inside the composition.

Connectors are wired between instantiated ports, not between SWC type definitions. The same SWC type can be instantiated multiple times.

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
      - from: "SpeedSensor_1.Pp_PowerState"
        to: "SpeedDisplay_1.Rp_PowerState"
```

Connector endpoints use `InstanceName.PortName` syntax. Both the instance and the port must exist. Interface compatibility between connected ports is validated by `CORE-040`.

### What connectors do not carry

Connectors are port-level only. They do not carry data element selection or operation selection. Those belong in runnable access definitions on the SWC type. This separation keeps wiring clean and keeps behavioral intent on the SWC where it belongs.
