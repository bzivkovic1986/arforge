from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from arforge.exporter import write_outputs, write_outputs_with_report
from arforge.validate import ValidationError, build_semantic_report, load_aggregator, load_and_validate_aggregator


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
    sync_segment = xml.split("<SHORT-NAME>Rp_Diag</SHORT-NAME>", 1)[1].split("</R-PORT-PROTOTYPE>", 1)[0]
    assert "<CLIENT-COM-SPEC>" in sync_segment
    assert "<CALL-MODE>synchronous</CALL-MODE>" in sync_segment
    assert "<TIMEOUT-MS>50</TIMEOUT-MS>" in sync_segment


def test_split_export_includes_async_cs_client_comspec(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_consumer = out_dir / "SpeedConsumer.arxml"
    xml = speed_consumer.read_text(encoding="utf-8")

    async_segment = xml.split("<SHORT-NAME>Rp_DiagAsync</SHORT-NAME>", 1)[1].split("</R-PORT-PROTOTYPE>", 1)[0]
    assert "<CLIENT-COM-SPEC>" in async_segment
    assert "<CALL-MODE>asynchronous</CALL-MODE>" in async_segment
    assert "<TIMEOUT-MS>" not in async_segment


def test_split_export_cs_call_points_follow_call_mode(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    xml = (out_dir / "SpeedConsumer.arxml").read_text(encoding="utf-8")

    assert "<SYNCHRONOUS-SERVER-CALL-POINT>" in xml
    assert "<ASYNCHRONOUS-SERVER-CALL-POINT>" in xml
    assert "<SHORT-NAME>SCP_Rp_Diag_ReadDTC</SHORT-NAME>" in xml
    assert "<SHORT-NAME>SCP_Rp_DiagAsync_ClearDTC</SHORT-NAME>" in xml
    assert "<SHORT-NAME>SCP_Rp_DiagAsync_LogEvent</SHORT-NAME>" in xml
    assert "<TARGET-REQUIRED-OPERATION-REF DEST=\"CLIENT-SERVER-OPERATION\">/DEMO/Interfaces/If_Diagnostics/ReadDTC</TARGET-REQUIRED-OPERATION-REF>" in xml
    assert "<TARGET-REQUIRED-OPERATION-REF DEST=\"CLIENT-SERVER-OPERATION\">/DEMO/Interfaces/If_Diagnostics/ClearDTC</TARGET-REQUIRED-OPERATION-REF>" in xml


def test_split_export_system_contains_multiple_component_prototypes(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    system_xml = (out_dir / "system.arxml").read_text(encoding="utf-8")

    assert "<SHORT-NAME>SpeedSensor_1</SHORT-NAME>" in system_xml
    assert "<SHORT-NAME>SpeedSensor_2</SHORT-NAME>" in system_xml
    assert "<SHORT-NAME>SpeedConsumer_1</SHORT-NAME>" in system_xml
    assert "<SHORT-NAME>SpeedConsumer_2</SHORT-NAME>" in system_xml
    assert system_xml.count("<SW-COMPONENT-PROTOTYPE>") == 4
    assert system_xml.count("<ASSEMBLY-SW-CONNECTOR>") == 6
    assert "<TYPE-TREF DEST=\"APPLICATION-SW-COMPONENT-TYPE\">/DEMO/Components/SpeedSensor</TYPE-TREF>" in system_xml
    assert "<CONTEXT-COMPONENT-REF DEST=\"SW-COMPONENT-PROTOTYPE\">/DEMO/System/Composition_DemoSystem/SpeedSensor_1</CONTEXT-COMPONENT-REF>" in system_xml


def test_split_export_orders_interfaces_and_connector_fragments_deterministically(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    shared_xml = (out_dir / "shared.arxml").read_text(encoding="utf-8")
    system_xml = (out_dir / "system.arxml").read_text(encoding="utf-8")

    vehicle_speed_segment = shared_xml.split("<SHORT-NAME>If_VehicleSpeed</SHORT-NAME>", 1)[1].split("</SENDER-RECEIVER-INTERFACE>", 1)[0]
    assert vehicle_speed_segment.index("<SHORT-NAME>VehicleSnapshot</SHORT-NAME>") < vehicle_speed_segment.index("<SHORT-NAME>VehicleSpeed</SHORT-NAME>")
    assert vehicle_speed_segment.index("<SHORT-NAME>VehicleSpeed</SHORT-NAME>") < vehicle_speed_segment.index("<SHORT-NAME>WheelSpeed</SHORT-NAME>")
    assert vehicle_speed_segment.index("<SHORT-NAME>WheelSpeed</SHORT-NAME>") < vehicle_speed_segment.index("<SHORT-NAME>WheelSpeeds</SHORT-NAME>")
    assert shared_xml.index("<SHORT-NAME>ClearDTC</SHORT-NAME>") < shared_xml.index("<SHORT-NAME>LogEvent</SHORT-NAME>")
    assert shared_xml.index("<SHORT-NAME>LogEvent</SHORT-NAME>") < shared_xml.index("<SHORT-NAME>ReadDTC</SHORT-NAME>")

    connector_names = [
        "Conn_1",
        "Conn_2",
        "Conn_3",
        "Conn_4",
        "Conn_5",
        "Conn_6",
    ]
    connector_segments = [
        system_xml.split(f"<SHORT-NAME>{connector_name}</SHORT-NAME>", 1)[1].split("</ASSEMBLY-SW-CONNECTOR>", 1)[0]
        for connector_name in connector_names
    ]
    expected_pairs = [
        ("SpeedSensor_1", "Pp_Diag", "SpeedConsumer_1", "Rp_Diag"),
        ("SpeedSensor_1", "Pp_Diag", "SpeedConsumer_1", "Rp_DiagAsync"),
        ("SpeedSensor_1", "Pp_VehicleSpeed", "SpeedConsumer_1", "Rp_VehicleSpeed"),
        ("SpeedSensor_2", "Pp_Diag", "SpeedConsumer_2", "Rp_Diag"),
        ("SpeedSensor_2", "Pp_Diag", "SpeedConsumer_2", "Rp_DiagAsync"),
        ("SpeedSensor_2", "Pp_VehicleSpeed", "SpeedConsumer_2", "Rp_VehicleSpeed"),
    ]

    for segment, (from_instance, from_port, to_instance, to_port) in zip(connector_segments, expected_pairs):
        assert f"/DEMO/System/Composition_DemoSystem/{from_instance}</CONTEXT-COMPONENT-REF>" in segment
        assert f"/DEMO/System/Composition_DemoSystem/{from_instance}/{from_port}</TARGET-P-PORT-REF>" in segment
        assert f"/DEMO/System/Composition_DemoSystem/{to_instance}</CONTEXT-COMPONENT-REF>" in segment
        assert f"/DEMO/System/Composition_DemoSystem/{to_instance}/{to_port}</TARGET-R-PORT-REF>" in segment


def test_split_export_reports_swc_outputs_in_name_order(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    report = write_outputs_with_report(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    swc_outputs = [artifact.path.name for artifact in report.outputs if artifact.path.name.endswith(".arxml") and artifact.path.name not in {"shared.arxml", "system.arxml"}]
    assert swc_outputs == ["SpeedConsumer.arxml", "SpeedSensor.arxml"]


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


def test_split_export_includes_cs_operation_arguments_return_and_errors(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    shared_xml = (out_dir / "shared.arxml").read_text(encoding="utf-8")

    read_dtc_segment = shared_xml.split("<SHORT-NAME>ReadDTC</SHORT-NAME>", 1)[1].split("</CLIENT-SERVER-OPERATION>", 1)[0]
    assert "<ARGUMENTS>" in read_dtc_segment
    assert "<SHORT-NAME>DtcId</SHORT-NAME>" in read_dtc_segment
    assert "<TYPE-TREF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/UInt16</TYPE-TREF>" in read_dtc_segment
    assert "<DIRECTION>IN</DIRECTION>" in read_dtc_segment
    assert "<SHORT-NAME>DtcState</SHORT-NAME>" in read_dtc_segment
    assert "<TYPE-TREF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/UInt8</TYPE-TREF>" in read_dtc_segment
    assert "<DIRECTION>OUT</DIRECTION>" in read_dtc_segment
    assert "<SHORT-NAME>OccurrenceCounter</SHORT-NAME>" in read_dtc_segment
    assert "<DIRECTION>INOUT</DIRECTION>" in read_dtc_segment
    assert "<SHORT-NAME>ReturnValue</SHORT-NAME>" in read_dtc_segment
    assert read_dtc_segment.count("<TYPE-TREF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/UInt8</TYPE-TREF>") == 2
    assert "<POSSIBLE-ERROR-REF DEST=\"APPLICATION-ERROR\">/DEMO/Interfaces/If_Diagnostics/DTC_NOT_FOUND</POSSIBLE-ERROR-REF>" in read_dtc_segment
    assert "<POSSIBLE-ERROR-REF DEST=\"APPLICATION-ERROR\">/DEMO/Interfaces/If_Diagnostics/MEMORY_ERROR</POSSIBLE-ERROR-REF>" in read_dtc_segment

    interface_segment = shared_xml.split("<SHORT-NAME>If_Diagnostics</SHORT-NAME>", 1)[1].split("</CLIENT-SERVER-INTERFACE>", 1)[0]
    assert "<APPLICATION-ERROR>" in interface_segment
    assert "<SHORT-NAME>DTC_NOT_FOUND</SHORT-NAME>" in interface_segment
    assert "<ERROR-CODE>1</ERROR-CODE>" in interface_segment
    assert "<SHORT-NAME>MEMORY_ERROR</SHORT-NAME>" in interface_segment
    assert "<ERROR-CODE>2</ERROR-CODE>" in interface_segment


def test_split_export_includes_init_event(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_sensor_xml = (out_dir / "SpeedSensor.arxml").read_text(encoding="utf-8")

    assert "<INIT-EVENT>" in speed_sensor_xml
    assert "<SHORT-NAME>IE_Runnable_Init</SHORT-NAME>" in speed_sensor_xml
    assert "<START-ON-EVENT-REF DEST=\"RUNNABLE-ENTITY\">/DEMO/Components/SpeedSensor/IB_SpeedSensor/Runnable_Init</START-ON-EVENT-REF>" in speed_sensor_xml


def test_split_export_includes_data_receive_event(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    xml = (out_dir / "SpeedConsumer.arxml").read_text(encoding="utf-8")

    assert "<DATA-RECEIVE-EVENT>" in xml
    assert "<SHORT-NAME>DRE_Runnable_OnVehicleSpeed_Rp_VehicleSpeed_VehicleSpeed</SHORT-NAME>" in xml
    assert "<CONTEXT-R-PORT-REF DEST=\"R-PORT-PROTOTYPE\">/DEMO/Components/SpeedConsumer/Rp_VehicleSpeed</CONTEXT-R-PORT-REF>" in xml
    assert "<TARGET-DATA-ELEMENT-REF DEST=\"VARIABLE-DATA-PROTOTYPE\">/DEMO/Interfaces/If_VehicleSpeed/VehicleSpeed</TARGET-DATA-ELEMENT-REF>" in xml


def test_split_export_includes_void_return_cs_operation_without_return_typeref(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    shared_xml = (out_dir / "shared.arxml").read_text(encoding="utf-8")

    assert "<SHORT-NAME>LogEvent</SHORT-NAME>" in shared_xml
    log_event_segment = shared_xml.split("<SHORT-NAME>LogEvent</SHORT-NAME>", 1)[1].split("</CLIENT-SERVER-OPERATION>", 1)[0]
    assert "<SHORT-NAME>EventId</SHORT-NAME>" in log_event_segment
    assert "<TYPE-TREF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/UInt16</TYPE-TREF>" in log_event_segment
    assert "<SHORT-NAME>ReturnValue</SHORT-NAME>" not in log_event_segment


def test_split_export_includes_array_implementation_datatype(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    shared_xml = (out_dir / "shared.arxml").read_text(encoding="utf-8")

    array_segment = shared_xml.split("<SHORT-NAME>Impl_WheelSpeeds</SHORT-NAME>", 1)[1].split("</IMPLEMENTATION-DATA-TYPE>", 1)[0]
    assert "<CATEGORY>ARRAY</CATEGORY>" in array_segment
    assert "<SHORT-NAME>Impl_WheelSpeeds_Element</SHORT-NAME>" in array_segment
    assert "<TYPE-TREF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/UInt16</TYPE-TREF>" in array_segment
    assert "<ARRAY-SIZE>4</ARRAY-SIZE>" in array_segment

    iface_segment = shared_xml.split("<SHORT-NAME>If_VehicleSpeed</SHORT-NAME>", 1)[1].split("</SENDER-RECEIVER-INTERFACE>", 1)[0]
    assert "<SHORT-NAME>WheelSpeeds</SHORT-NAME>" in iface_segment
    assert "<TYPE-TREF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/Impl_WheelSpeeds</TYPE-TREF>" in iface_segment


def test_split_export_includes_nested_struct_implementation_datatypes(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    shared_xml = (out_dir / "shared.arxml").read_text(encoding="utf-8")

    inner_segment = shared_xml.split("<SHORT-NAME>Impl_Inner</SHORT-NAME>", 1)[1].split("</IMPLEMENTATION-DATA-TYPE>", 1)[0]
    assert "<CATEGORY>STRUCTURE</CATEGORY>" in inner_segment
    assert "<SHORT-NAME>value</SHORT-NAME>" in inner_segment
    assert "<IMPLEMENTATION-DATA-TYPE-REF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/UInt16</IMPLEMENTATION-DATA-TYPE-REF>" in inner_segment

    outer_segment = shared_xml.split("<SHORT-NAME>Impl_Outer</SHORT-NAME>", 1)[1].split("</IMPLEMENTATION-DATA-TYPE>", 1)[0]
    assert "<SHORT-NAME>inner</SHORT-NAME>" in outer_segment
    assert "<IMPLEMENTATION-DATA-TYPE-REF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/Impl_Inner</IMPLEMENTATION-DATA-TYPE-REF>" in outer_segment
    assert "<SHORT-NAME>quality</SHORT-NAME>" in outer_segment
    assert "<IMPLEMENTATION-DATA-TYPE-REF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/UInt16</IMPLEMENTATION-DATA-TYPE-REF>" in outer_segment
    assert outer_segment.index("<SHORT-NAME>inner</SHORT-NAME>") < outer_segment.index("<SHORT-NAME>quality</SHORT-NAME>")

    iface_segment = shared_xml.split("<SHORT-NAME>If_VehicleSpeed</SHORT-NAME>", 1)[1].split("</SENDER-RECEIVER-INTERFACE>", 1)[0]
    assert "<SHORT-NAME>VehicleSnapshot</SHORT-NAME>" in iface_segment
    assert "<TYPE-TREF DEST=\"IMPLEMENTATION-DATA-TYPE\">/DEMO/ImplementationDataTypes/Impl_Outer</TYPE-TREF>" in iface_segment


def test_split_export_operation_invoked_events_reference_operations(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_sensor_xml = (out_dir / "SpeedSensor.arxml").read_text(encoding="utf-8")

    oie_segment = speed_sensor_xml.split("<SHORT-NAME>OIE_Runnable_DiagServer_Pp_Diag_ReadDTC</SHORT-NAME>", 1)[1].split("</OPERATION-INVOKED-EVENT>", 1)[0]
    assert "<CONTEXT-P-PORT-REF DEST=\"P-PORT-PROTOTYPE\">/DEMO/Components/SpeedSensor/Pp_Diag</CONTEXT-P-PORT-REF>" in oie_segment
    assert "<TARGET-PROVIDED-OPERATION-REF DEST=\"CLIENT-SERVER-OPERATION\">/DEMO/Interfaces/If_Diagnostics/ReadDTC</TARGET-PROVIDED-OPERATION-REF>" in oie_segment


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    [
        ("project_data_receive_event_unknown_port.yaml", "CORE-027-DRE-UNKNOWN-PORT"),
        ("project_data_receive_event_unknown_dataelement.yaml", "CORE-027-DRE-UNKNOWN-DATAELEMENT"),
        ("project_data_receive_event_on_provides_port.yaml", "CORE-027-DRE-DIRECTION"),
        ("project_data_receive_event_on_client_server_port.yaml", "CORE-027-DRE-INTERFACE-TYPE"),
        ("project_cs_duplicate_port_pair.yaml", "CORE-040-CS-DUPLICATE-PORT-PAIR"),
        ("project_cs_interface_mismatch.yaml", "CORE-040-INTERFACE-MISMATCH"),
        ("project_cs_wrong_directions.yaml", "CORE-040-FROM-DIRECTION"),
        ("project_impl_array_application_ref.yaml", "CORE-010-ARRAY-APPLICATION-TYPE"),
        ("project_impl_array_unknown_element_type.yaml", "CORE-010-ARRAY-UNKNOWN-ELEMENT-TYPE"),
        ("project_impl_array_zero_length.yaml", "CORE-010-ARRAY-LENGTH"),
        ("project_struct_cycle.yaml", "CORE-010-STRUCT-CYCLE"),
        ("project_struct_duplicate_field_names.yaml", "CORE-010-STRUCT-DUPLICATE-FIELD"),
        ("project_struct_unknown_nested_type.yaml", "CORE-010-STRUCT-UNKNOWN-TYPE"),
        ("project_sr_duplicate_port_pair.yaml", "CORE-040-SR-DUPLICATE-PORT-PAIR"),
        ("project_sr_read_unconnected.yaml", "CORE-041-SR-READ-UNCONNECTED"),
        ("project_sr_write_unconnected.yaml", "CORE-041-SR-WRITE-UNCONNECTED"),
    ],
)
def test_data_receive_event_invalid_fixtures_emit_expected_codes(fixture_name: str, expected_code: str) -> None:
    project = load_aggregator(INVALID_DIR / fixture_name)
    report = build_semantic_report(project, ruleset="core")
    error_codes = {finding.code for finding in report.error_findings()}
    assert expected_code in error_codes


def test_split_export_is_deterministic(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    _ = write_outputs(project, template_dir=template_dir, out=out1, split_by_swc=True)
    _ = write_outputs(project, template_dir=template_dir, out=out2, split_by_swc=True)

    files1 = sorted(p.relative_to(out1) for p in out1.rglob("*.arxml"))
    files2 = sorted(p.relative_to(out2) for p in out2.rglob("*.arxml"))
    assert files1 == files2

    for rel in files1:
        data1 = (out1 / rel).read_bytes()
        data2 = (out2 / rel).read_bytes()
        assert data1 == data2
        assert hashlib.sha256(data1).hexdigest() == hashlib.sha256(data2).hexdigest()
