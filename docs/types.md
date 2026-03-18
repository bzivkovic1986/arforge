# Types

ARForge currently models 5 type groups:

1. `baseTypes`
2. `implementationDataTypes`
3. `applicationDataTypes`
4. `units` (optional)
5. `compuMethods` (optional: `linear` and `textTable`)

## Base types

```yaml
baseTypes:
  - name: "uint16"
  - name: "uint8"
    bitLength: 8
    signedness: "unsigned"
    nativeDeclaration: "uint8"
```

Base type entry formats:

- raw type metadata: `{ name, bitLength, signedness, nativeDeclaration? }`

Metadata rules:

- `bitLength` must be an integer `>= 1`
- `signedness` must be `unsigned` or `signed`
- use metadata to define representable ranges for constrained integer application types

## Implementation data types

Scalar:

```yaml
implementationDataTypes:
  - name: "Impl_VehicleSpeed_U16"
    baseTypeRef: "uint16"
```

Struct (v0):

```yaml
implementationDataTypes:
  - name: "SpeedPair_T"
    kind: "struct"
    fields:
      - name: "vehicle"
        typeRef: "UInt16"
      - name: "wheel"
        typeRef: "UInt16"
```

Struct field policy:

- field `typeRef` may target base or implementation types
- field `typeRef` must not target application types
- field names must be unique within the struct
- recursive struct cycles are rejected, including nested references through array element types

Array (v0):

```yaml
implementationDataTypes:
  - name: "Impl_WheelSpeeds"
    kind: "array"
    elementTypeRef: "UInt16"
    length: 4
```

Array policy:

- `kind` must be `array`
- `elementTypeRef` may target base or implementation types
- `elementTypeRef` must not target application types
- `length` must be an integer `>= 1`
- trivial direct self-reference is rejected

## Application data types

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

Constraint policy (v0):

- `constraint` is optional and requires both `min` and `max`
- `min` must be less than or equal to `max`
- scalar integer implementation types require integer `min`/`max`
- integer constraints must fit the base type representable range derived from metadata:
  - unsigned: `0 .. (2^bitLength - 1)`
  - signed: `-(2^(bitLength-1)) .. (2^(bitLength-1) - 1)`
- scalar float implementation types (`float32`, `float64`) accept integer or float bounds
- non-scalar implementation types (for example `struct`) do not support constraints in v0

Compu method linkage policy:

- if `compuMethodRef` points to a `linear` compu method:
  - `unitRef` is required
  - `applicationDataTypes[*].unitRef` must match `compuMethods[*].unitRef`
- if `compuMethodRef` points to a `textTable` compu method:
  - `unitRef` is optional
  - no unit match check is applied

## Units and compu methods

```yaml
units:
  - name: "km_per_h"
    displayName: "km/h"
```

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

Enumeration-style `textTable`:

```yaml
compuMethods:
  - name: "CM_DtcStatus"
    category: "textTable"
    entries:
      - value: 0
        label: "OK"
      - value: 1
        label: "Failed"
      - value: 2
        label: "Pending"
```
