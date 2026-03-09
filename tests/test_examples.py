from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from arforge.exporter import write_outputs
from arforge.validate import ValidationError, load_aggregator, load_and_validate_aggregator


REPO_ROOT = Path(__file__).resolve().parent.parent
VALID_PROJECT = REPO_ROOT / "examples" / "autosar.project.yaml"
INVALID_DIR = REPO_ROOT / "examples" / "invalid"


def _is_project_fixture(path: Path) -> bool:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return isinstance(data, dict) and "autosar" in data and "inputs" in data


def _invalid_project_fixtures() -> list[Path]:
    fixtures = [p for p in sorted(INVALID_DIR.glob("*.yaml")) if _is_project_fixture(p)]
    return fixtures


def test_validate_main_example_passes() -> None:
    load_and_validate_aggregator(VALID_PROJECT)


@pytest.mark.parametrize(
    "fixture_path",
    _invalid_project_fixtures(),
    ids=lambda p: p.name,
)
def test_invalid_project_fixtures_fail_validation(fixture_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_and_validate_aggregator(fixture_path)


def test_cli_validate_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(VALID_PROJECT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_split_export_includes_sr_comspec_blocks(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_consumer = out_dir / "SpeedConsumer.arxml"
    xml = speed_consumer.read_text(encoding="utf-8")

    assert "<REQUIRED-COM-SPECS>" in xml
    assert "<QUEUED-RECEIVER-COM-SPEC>" in xml
    assert "<QUEUE-LENGTH>8</QUEUE-LENGTH>" in xml
    assert "<CLIENT-COM-SPEC>" in xml
    assert "<CALL-MODE>synchronous</CALL-MODE>" in xml
    assert "<TIMEOUT-MS>50</TIMEOUT-MS>" in xml


def test_split_export_includes_async_cs_client_comspec(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_consumer = out_dir / "SpeedConsumer.arxml"
    xml = speed_consumer.read_text(encoding="utf-8")

    assert "<CLIENT-COM-SPEC>" in xml
    assert "<CALL-MODE>asynchronous</CALL-MODE>" in xml
    assert xml.count("<TIMEOUT-MS>") == 1


def test_split_export_system_contains_multiple_component_prototypes(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    system_xml = (out_dir / "system.arxml").read_text(encoding="utf-8")

    assert "<SHORT-NAME>SpeedSensor_1</SHORT-NAME>" in system_xml
    assert "<SHORT-NAME>SpeedSensor_2</SHORT-NAME>" in system_xml
    assert "<SHORT-NAME>SpeedConsumer_1</SHORT-NAME>" in system_xml
    assert system_xml.count("<SW-COMPONENT-PROTOTYPE>") == 3
    assert system_xml.count("<ASSEMBLY-SW-CONNECTOR>") == 4


def test_split_export_includes_server_raised_error_refs(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_sensor_xml = (out_dir / "SpeedSensor.arxml").read_text(encoding="utf-8")
    shared_xml = (out_dir / "shared.arxml").read_text(encoding="utf-8")

    assert "<RAISED-APPLICATION-ERROR-REFS>" in speed_sensor_xml
    assert "<TARGET-PROVIDED-OPERATION-REF DEST=\"CLIENT-SERVER-OPERATION\">/DEMO/Interfaces/If_Diagnostics/ReadDTC</TARGET-PROVIDED-OPERATION-REF>" in speed_sensor_xml
    assert "<TARGET-APPLICATION-ERROR-REF DEST=\"APPLICATION-ERROR\">/DEMO/Interfaces/If_Diagnostics/DTC_NOT_FOUND</TARGET-APPLICATION-ERROR-REF>" in speed_sensor_xml
    assert "<APPLICATION-ERROR>" in shared_xml
    assert "<SHORT-NAME>DTC_NOT_FOUND</SHORT-NAME>" in shared_xml
    assert "<ERROR-CODE>1</ERROR-CODE>" in shared_xml


def test_split_export_includes_void_return_cs_operation_without_return_typeref(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    shared_xml = (out_dir / "shared.arxml").read_text(encoding="utf-8")

    assert "<SHORT-NAME>LogEvent</SHORT-NAME>" in shared_xml
    log_event_segment = shared_xml.split("<SHORT-NAME>LogEvent</SHORT-NAME>", 1)[1].split("</CLIENT-SERVER-OPERATION>", 1)[0]
    assert "<TYPE-TREF" not in log_event_segment


def test_legacy_datatypes_input_emits_deprecation_warning() -> None:
    legacy_project = INVALID_DIR / "project_bad_operation.yaml"
    with pytest.warns(DeprecationWarning, match="Legacy 'inputs.datatypes' format is deprecated"):
        _ = load_aggregator(legacy_project)
