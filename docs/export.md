# Export

Export is implemented by `arforge/exporter.py` and Jinja2 templates in `templates/`.

## Modes

Split mode (`--split-by-swc`):

- `<RootPackage>_SharedTypes.arxml`
- `<SWC>.arxml` per SWC
- `<System>.arxml`

Monolithic mode:

- single output file from `all_42.arxml.j2`

## Shared ARXML content

The shared types artifact currently contains:

- `BaseTypes` package
- `ImplementationDataTypes` package (including struct members)
- array implementation data types with element type references and fixed `ARRAY-SIZE`
- `ApplicationDataTypes` package
- `Units` package
- `CompuMethods` package (`linear` and `textTable`)
- Interfaces package (SR + CS)

Base type rendering in `BaseTypes`:

- one `SW-BASE-TYPE` per base type (sorted by name for deterministic output)
- `SHORT-NAME` always
- `BASE-TYPE-SIZE` when `bitLength` is defined
- `BASE-TYPE-ENCODING`:
  - `NONE` for `signedness: unsigned`
  - `2C` for `signedness: signed`
- `NATIVE-DECLARATION` when `nativeDeclaration` is defined

Application data type links are emitted when present:

- `UNIT-REF`
- `COMPU-METHOD-REF`
- `DATA-CONSTR-REF` (when `applicationDataTypes[*].constraint` is defined)

Constraint rendering:

- `DataConstrs` package with one `DATA-CONSTR` per constrained application data type
- each constraint emits closed lower/upper limits from YAML `min`/`max`

Compu method rendering:

- `linear` emits `UNIT-REF`, `FACTOR`, `OFFSET`, optional `PHYS-MIN`/`PHYS-MAX`
- `textTable` emits internal-to-physical scales with per-entry:
  - numeric value (lower/upper limit)
  - label (`VT`)

## SWC ARXML content

Each SWC file includes:

- provides/requires ports
- optional sender-receiver/client-server ComSpec blocks inside port prototypes
- runnables
- runnable access points from `reads`/`writes`/`calls`
- timing events (when `timingEventMs` is set)
- operation-invoked events (for `operationInvokedEvents`)

When a port defines `comSpec`, export emits the block directly after the interface TREF:

- senderReceiver requires port (`R-PORT-PROTOTYPE`):
  - `REQUIRED-COM-SPECS`
  - queued mode: `QUEUED-RECEIVER-COM-SPEC` + `QUEUE-LENGTH`
  - nonqueued modes: `NONQUEUED-RECEIVER-COM-SPEC`
- senderReceiver provides port (`P-PORT-PROTOTYPE`):
  - `PROVIDED-COM-SPECS`
  - queued mode: `QUEUED-SENDER-COM-SPEC` + `QUEUE-LENGTH`
  - nonqueued modes: `NONQUEUED-SENDER-COM-SPEC`
- clientServer requires port:
  - `REQUIRED-COM-SPECS` + `CLIENT-COM-SPEC`
  - `CALL-MODE` (`synchronous` / `asynchronous`)
  - optional `TIMEOUT-MS` when synchronous
- clientServer provides port:
  - `PROVIDED-COM-SPECS` + `SERVER-COM-SPEC`
  - `CALL-MODE` and optional `TIMEOUT-MS` (same policy)

Notes:

- Current export keeps ComSpec minimal by design (no operation/data-element refs in ComSpec blocks).

## System ARXML content

Includes:

- composition prototypes
- assembly connectors between `Instance.Port` endpoints

For senderReceiver and clientServer interfaces, export emits one assembly connector per unique port pair. Data-element and operation usage remain in SWC runnable behavior rather than on system connectors.
