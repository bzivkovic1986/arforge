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
```

## Implementation data types

Scalar:

```yaml
implementationDataTypes:
  - name: "UInt16"
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

## Application data types

```yaml
applicationDataTypes:
  - name: "App_VehicleSpeed"
    implementationTypeRef: "UInt16"
    unitRef: "km_h"
    compuMethodRef: "CM_Speed_Kmh_Linear"
  - name: "App_DtcStatus"
    implementationTypeRef: "UInt8"
    compuMethodRef: "CM_DtcStatus"
```

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
  - name: "km_h"
    displayName: "km/h"
```

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
