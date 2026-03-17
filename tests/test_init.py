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
        "interfaces/If_SystemValue.yaml",
        "swcs/SystemValueProvider.yaml",
        "swcs/SystemValueConsumer.yaml",
        "system.yaml",
    ]
    for rel in expected_files:
        assert (project_dir / rel).is_file(), f"Missing scaffold file: {rel}"

    project = load_and_validate_aggregator(project_dir / "autosar.project.yaml")
    project_yaml = (project_dir / "autosar.project.yaml").read_text(encoding="utf-8")
    system_yaml = (project_dir / "system.yaml").read_text(encoding="utf-8")
    interface_yaml = (project_dir / "interfaces" / "If_SystemValue.yaml").read_text(encoding="utf-8")
    consumer_yaml = (project_dir / "swcs" / "SystemValueConsumer.yaml").read_text(encoding="utf-8")
    assert project_yaml.startswith("# ARForge: Project input manifest")
    assert system_yaml.startswith("# ARForge: System composition")
    assert interface_yaml.startswith("# ARForge: Interface definition")
    assert 'dataElement: "SystemValue"' not in system_yaml
    assert 'dataReceiveEvents:' in consumer_yaml

    out_dir = tmp_path / "out"
    written = write_outputs(project, template_dir=TEMPLATE_DIR, out=out_dir, split_by_swc=True)
    assert [path.name for path in written] == [
        "DEMOSYSTEM_SharedTypes.arxml",
        "SystemValueConsumer.arxml",
        "SystemValueProvider.arxml",
        "DemoSystem.arxml",
    ]


def test_init_no_example_creates_structure_only_project(tmp_path: Path) -> None:
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
        "system.yaml",
    ]
    for rel in expected_files:
        assert (project_dir / rel).is_file(), f"Missing scaffold file: {rel}"

    assert (project_dir / "interfaces").is_dir()
    assert (project_dir / "swcs").is_dir()
    assert list((project_dir / "interfaces").glob("*.yaml")) == []
    assert list((project_dir / "swcs").glob("*.yaml")) == []
    system_yaml = (project_dir / "system.yaml").read_text(encoding="utf-8")
    assert system_yaml.startswith("# ARForge: System composition")
    assert "Example shape:" in system_yaml


def test_init_fails_for_non_empty_dir_without_force(tmp_path: Path) -> None:
    project_dir = tmp_path / "existing"
    project_dir.mkdir()
    (project_dir / "keep.txt").write_text("keep", encoding="utf-8")

    result = _run_init(project_dir)
    assert result.returncode != 0
    assert "not empty" in (result.stdout + result.stderr)
