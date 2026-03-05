# Export

Export is implemented by `arforge/exporter.py` and Jinja2 templates in `templates/`.

## Modes

Split mode (`--split-by-swc`):

- `shared.arxml`
- `<SWC>.arxml` per SWC
- `system.arxml`

Monolithic mode:

- single output file from `all_42.arxml.j2`

## Shared ARXML content

`shared.arxml` currently contains:

- `BaseTypes` package
- `ImplementationDataTypes` package (including struct members)
- `ApplicationDataTypes` package
- `Units` package
- `CompuMethods` package (`linear` and `textTable`)
- Interfaces package (SR + CS)

Application data type links are emitted when present:

- `UNIT-REF`
- `COMPU-METHOD-REF`

Compu method rendering:

- `linear` emits `UNIT-REF`, `FACTOR`, `OFFSET`, optional `PHYS-MIN`/`PHYS-MAX`
- `textTable` emits internal-to-physical scales with per-entry:
  - numeric value (lower/upper limit)
  - label (`VT`)

## SWC ARXML content

Each SWC file includes:

- provides/requires ports
- runnables
- timing events (when `timingEventMs` is set)
- operation-invoked events (for `operationInvokedEvents`)

## System ARXML content

Includes:

- composition prototypes
- assembly connectors between `Instance.Port` endpoints
