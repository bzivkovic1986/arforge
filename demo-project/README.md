# DemoSystem

ARForge project scaffold for AUTOSAR Classic modeling.

This scaffold includes a small runnable sender-receiver example:

- `types/` defines reusable data types.
- `modes/power_state.yaml` defines a simple mode declaration group.
- `interfaces/If_VehicleSpeed.yaml` and `interfaces/If_PowerState.yaml` define the example interfaces used by ports.
- `swcs/SpeedSensor.yaml` and `swcs/SpeedDisplay.yaml` define SWC types with both data and mode ports, including a runnable mode-switch trigger.
- `system.yaml` instantiates those SWC types as component prototypes and connects both flows.

Validate the project:

```bash
python -m arforge.cli validate autosar.project.yaml
```

Export ARXML:

```bash
python -m arforge.cli export autosar.project.yaml --out build/out --split-by-swc
```
