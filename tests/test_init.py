from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from arforge.exporter import write_outputs
from arforge.validate import load_and_validate_aggregator


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates"


def _run_init(project_dir: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "arforge.cli", "init", str(project_dir), *extra_args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "arforge.cli", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_init_default_creates_valid_project(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    result = _run_init(project_dir, "--name", "DemoSystem")
    assert result.returncode == 0, result.stdout + result.stderr

    expected_files = [
        "README.md",
        "autosar.project.yaml",
        "types/base_types.yaml",
        "types/implementation_types.yaml",
        "types/application_types.yaml",
        "units/units.yaml",
        "compu_methods/compu_methods.yaml",
        "modes/power_state.yaml",
        "interfaces/If_VehicleSpeed.yaml",
        "interfaces/If_PowerState.yaml",
        "swcs/SpeedSensor.yaml",
        "swcs/SpeedDisplay.yaml",
        "system.yaml",
    ]
    for rel in expected_files:
        assert (project_dir / rel).is_file(), f"Missing scaffold file: {rel}"

    project = load_and_validate_aggregator(project_dir / "autosar.project.yaml")
    readme = (project_dir / "README.md").read_text(encoding="utf-8")
    project_yaml = (project_dir / "autosar.project.yaml").read_text(encoding="utf-8")
    system_yaml = (project_dir / "system.yaml").read_text(encoding="utf-8")
    modes_yaml = (project_dir / "modes" / "power_state.yaml").read_text(encoding="utf-8")
    interface_yaml = (project_dir / "interfaces" / "If_VehicleSpeed.yaml").read_text(encoding="utf-8")
    mode_interface_yaml = (project_dir / "interfaces" / "If_PowerState.yaml").read_text(encoding="utf-8")
    producer_yaml = (project_dir / "swcs" / "SpeedSensor.yaml").read_text(encoding="utf-8")
    consumer_yaml = (project_dir / "swcs" / "SpeedDisplay.yaml").read_text(encoding="utf-8")
    application_types_yaml = (project_dir / "types" / "application_types.yaml").read_text(encoding="utf-8")
    implementation_types_yaml = (project_dir / "types" / "implementation_types.yaml").read_text(encoding="utf-8")
    assert project_yaml.startswith("# ARForge: Project input manifest")
    assert system_yaml.startswith("# ARForge: System composition")
    assert interface_yaml.startswith("# ARForge: Interface definition")
    assert producer_yaml.startswith("# ARForge: Software Component Type")
    assert consumer_yaml.startswith("# ARForge: Software Component Type")
    assert modes_yaml.startswith("# ARForge: Mode declaration groups")
    assert "instantiates those SWC types as component prototypes" in readme
    assert "modes/power_state.yaml" in readme
    assert "interfaces/If_PowerState.yaml" in readme
    assert "python -m arforge.cli validate autosar.project.yaml" in readme
    assert "python -m arforge.cli export autosar.project.yaml --out build/out --split-by-swc" in readme
    assert 'modeDeclarationGroups:' in project_yaml
    assert '- "modes/*.yaml"' in project_yaml
    assert 'description: "Power state modes used by the scaffolded mode-switch interface."' in modes_yaml
    assert 'typeRef points to the SWC type defined in swcs/*.yaml.' in system_yaml
    assert 'name: "SpeedSensor_1"' in system_yaml
    assert 'typeRef: "SpeedSensor"' in system_yaml
    assert 'name: "SpeedDisplay_1"' in system_yaml
    assert 'description: "Connects the ECU power-state mode to the display instance."' in system_yaml
    assert 'description: "Sender-receiver interface for the current vehicle speed."' in interface_yaml
    assert 'description: "Mode switch interface for ECU power state."' in mode_interface_yaml
    assert 'modeGroupRef: "Mdg_PowerState"' in mode_interface_yaml
    assert 'description: "SWC type that publishes the current vehicle speed."' in producer_yaml
    assert 'description: "Provided mode switch port for ECU power state."' in producer_yaml
    assert 'description: "SWC type that reads vehicle speed and could display it to a user."' in consumer_yaml
    assert 'description: "Required mode switch port for ECU power state."' in consumer_yaml
    assert 'description: "Vehicle speed value shared between the demo SWC types."' in application_types_yaml
    assert 'description: "Raw implementation type for a vehicle speed sample."' in implementation_types_yaml

    validate_result = _run_cli("validate", str(project_dir / "autosar.project.yaml"))
    assert validate_result.returncode == 0, validate_result.stdout + validate_result.stderr

    export_result = _run_cli(
        "export",
        str(project_dir / "autosar.project.yaml"),
        "--out",
        str(tmp_path / "out_cli"),
        "--split-by-swc",
    )
    assert export_result.returncode == 0, export_result.stdout + export_result.stderr

    out_dir = tmp_path / "out"
    written = write_outputs(project, template_dir=TEMPLATE_DIR, out=out_dir, split_by_swc=True)
    assert [path.name for path in written] == [
        "DEMOSYSTEM_SharedTypes.arxml",
        "SpeedDisplay.arxml",
        "SpeedSensor.arxml",
        "DemoSystem.arxml",
    ]


def test_init_no_example_creates_structure_only_project(tmp_path: Path) -> None:
    project_dir = tmp_path / "empty"
    result = _run_init(project_dir, "--no-example")
    assert result.returncode == 0, result.stdout + result.stderr

    expected_files = [
        "README.md",
        "autosar.project.yaml",
        "types/base_types.yaml",
        "types/implementation_types.yaml",
        "types/application_types.yaml",
        "units/units.yaml",
        "compu_methods/compu_methods.yaml",
        "modes/power_state.yaml",
        "system.yaml",
    ]
    for rel in expected_files:
        assert (project_dir / rel).is_file(), f"Missing scaffold file: {rel}"

    assert (project_dir / "interfaces").is_dir()
    assert (project_dir / "swcs").is_dir()
    assert list((project_dir / "interfaces").glob("*.yaml")) == []
    assert list((project_dir / "swcs").glob("*.yaml")) == []
    readme = (project_dir / "README.md").read_text(encoding="utf-8")
    system_yaml = (project_dir / "system.yaml").read_text(encoding="utf-8")
    project_yaml = (project_dir / "autosar.project.yaml").read_text(encoding="utf-8")
    modes_yaml = (project_dir / "modes" / "power_state.yaml").read_text(encoding="utf-8")
    assert "without example interfaces or SWCs" in readme
    assert "mode declaration groups under `modes/`" in readme
    assert system_yaml.startswith("# ARForge: System composition")
    assert "Example shape:" in system_yaml
    assert 'modeDeclarationGroups:' in project_yaml
    assert modes_yaml.startswith("# ARForge: Mode declaration groups")


def test_init_fails_for_non_empty_dir_without_force(tmp_path: Path) -> None:
    project_dir = tmp_path / "existing"
    project_dir.mkdir()
    (project_dir / "keep.txt").write_text("keep", encoding="utf-8")

    result = _run_init(project_dir)
    assert result.returncode != 0
    assert "not empty" in (result.stdout + result.stderr)
