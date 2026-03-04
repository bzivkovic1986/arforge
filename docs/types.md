# Types

ARForge currently models 5 type groups:

1. `baseTypes`
2. `implementationDataTypes`
3. `applicationDataTypes`
4. `units` (optional)
5. `compuMethods` (optional, linear only in v0)

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
```

## Units and linear compu methods

```yaml
units:
  - name: "km_h"
    displayName: "km/h"
```

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
