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


def test_init_default_creates_valid_project(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    result = _run_init(project_dir, "--name", "DemoSystem")
    assert result.returncode == 0, result.stdout + result.stderr

    expected_files = [
        "autosar.project.yaml",
        "platform/base_types.yaml",
        "types/implementation_types.yaml",
        "types/application_types.yaml",
        "units/units.yaml",
        "compu_methods/compu_methods.yaml",
        "interfaces/If_VehicleSpeed.yaml",
        "interfaces/If_Diagnostics.yaml",
        "swcs/SpeedSensor.yaml",
        "swcs/SpeedConsumer.yaml",
        "system.yaml",
    ]
    for rel in expected_files:
        assert (project_dir / rel).is_file(), f"Missing scaffold file: {rel}"

    project = load_and_validate_aggregator(project_dir / "autosar.project.yaml")
    system_yaml = (project_dir / "system.yaml").read_text(encoding="utf-8")
    speed_consumer_yaml = (project_dir / "swcs" / "SpeedConsumer.yaml").read_text(encoding="utf-8")
    assert 'dataElement: "VehicleSpeed"' not in system_yaml
    assert 'dataReceiveEvents:' in speed_consumer_yaml

    out_file = tmp_path / "all.arxml"
    written = write_outputs(project, template_dir=TEMPLATE_DIR, out=out_file, split_by_swc=False)
    assert written == [out_file]
    assert out_file.is_file()


def test_init_no_example_creates_placeholder_model(tmp_path: Path) -> None:
    project_dir = tmp_path / "empty"
    result = _run_init(project_dir, "--no-example")
    assert result.returncode == 0, result.stdout + result.stderr

    expected_files = [
        "autosar.project.yaml",
        "platform/base_types.yaml",
        "types/implementation_types.yaml",
        "types/application_types.yaml",
        "units/units.yaml",
        "compu_methods/compu_methods.yaml",
        "interfaces/placeholder_interface.yaml",
        "swcs/producer.yaml",
        "swcs/consumer.yaml",
        "system.yaml",
    ]
    for rel in expected_files:
        assert (project_dir / rel).is_file(), f"Missing scaffold file: {rel}"

    project = load_and_validate_aggregator(project_dir / "autosar.project.yaml")
    system_yaml = (project_dir / "system.yaml").read_text(encoding="utf-8")
    consumer_yaml = (project_dir / "swcs" / "consumer.yaml").read_text(encoding="utf-8")
    assert 'dataElement: "Value"' not in system_yaml
    assert 'dataReceiveEvents:' in consumer_yaml

    out_dir = tmp_path / "out"
    written = write_outputs(project, template_dir=TEMPLATE_DIR, out=out_dir, split_by_swc=True)
    assert len(written) == 4
    assert (out_dir / "shared.arxml").is_file()
    assert (out_dir / "Producer.arxml").is_file()
    assert (out_dir / "Consumer.arxml").is_file()
    assert (out_dir / "system.arxml").is_file()


def test_init_fails_for_non_empty_dir_without_force(tmp_path: Path) -> None:
    project_dir = tmp_path / "existing"
    project_dir.mkdir()
    (project_dir / "keep.txt").write_text("keep", encoding="utf-8")

    result = _run_init(project_dir)
    assert result.returncode != 0
    assert "not empty" in (result.stdout + result.stderr)
