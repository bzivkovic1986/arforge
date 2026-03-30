from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest
import yaml

from arforge.exporter import write_outputs, write_outputs_with_report
from arforge.diagrams import build_diagram_views, write_diagram_outputs
from arforge.model import (
    ComponentPrototype,
    Composition,
    Interface,
    OperationInvokedEvent,
    Port,
    Project,
    Runnable,
    Swc,
    System,
)
from arforge.semantic_validation import Finding, FindingSeverity
from arforge.validate import ValidationError, build_semantic_report, load_aggregator, load_and_validate_aggregator


REPO_ROOT = Path(__file__).resolve().parent.parent
VALID_PROJECT = REPO_ROOT / "examples" / "autosar.project.yaml"
INVALID_DIR = REPO_ROOT / "examples" / "invalid"
SHARED_EXAMPLE_OUTPUT = "DEMO_SharedTypes.arxml"
SYSTEM_EXAMPLE_OUTPUT = "DemoSystem.arxml"
PLANTUML_DIAGRAM_OUTPUTS = [
    "composition_DemoSystem.puml",
    "interfaces_wiring.puml",
    "interfaces_contracts.puml",
    "behavior_SpeedDisplay.puml",
    "behavior_SpeedSensor.puml",
]
WARNING_ONLY_PROJECT = INVALID_DIR / "project_connected_sr_port_unused.yaml"
ERROR_PROJECT = INVALID_DIR / "project_bad_runnable_access.yaml"
MIXED_PROJECT = INVALID_DIR / "project_sr_read_unconnected.yaml"
CS_SERVER_WARNING_PROJECT = INVALID_DIR / "project_cs_server_oie_unconnected.yaml"
UNUSED_MODE_GROUP_PROJECT = INVALID_DIR / "project_unused_mode_group.yaml"
CONNECTED_UNUSED_MODE_SWITCH_PROJECT = INVALID_DIR / "project_connected_mode_switch_port_unused.yaml"


def _is_project_fixture(path: Path) -> bool:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return isinstance(data, dict) and "autosar" in data and "inputs" in data


def _invalid_project_fixtures() -> list[Path]:
    warning_only = {
        "project_connected_sr_port_unused.yaml",
        "project_cs_server_oie_unconnected.yaml",
        "project_declared_unused_cs_provides.yaml",
        "project_declared_unused_cs_requires.yaml",
        "project_declared_unused_mode_requires.yaml",
        "project_declared_unused_sr_provides.yaml",
        "project_connected_mode_switch_port_unused.yaml",
        "project_mode_switch_unconnected.yaml",
        "project_unused_mode_group.yaml",
        "project_sr_consumer_faster.yaml",
        "project_sr_producer_faster.yaml",
        "project_sr_timing_equal.yaml",
    }
    fixtures = [
        p
        for p in sorted(INVALID_DIR.glob("*.yaml"))
        if _is_project_fixture(p) and p.name not in warning_only
    ]
    return fixtures


def test_validate_main_example_passes() -> None:
    load_and_validate_aggregator(VALID_PROJECT)


def test_finding_defaults_to_error_severity() -> None:
    finding = Finding(code="CORE-999", message="Compatibility default.")

    assert finding.severity == FindingSeverity.ERROR


def test_main_example_descriptions_are_loaded_into_model_ir() -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)

    assert next(interface for interface in project.interfaces if interface.name == "If_VehicleSpeed").description == (
        "Sender-receiver interface for the current vehicle speed."
    )
    power_state_interface = next(interface for interface in project.interfaces if interface.name == "If_PowerState")
    assert power_state_interface.description == "Mode switch interface for ECU power state."
    assert power_state_interface.modeGroupRef == "Mdg_PowerState"
    assert next(swc for swc in project.swcs if swc.name == "SpeedSensor").description == (
        "SWC type that publishes the current vehicle speed."
    )
    assert next(swc for swc in project.swcs if swc.name == "SpeedDisplay").description == (
        "SWC type that reads vehicle speed through explicit, implicit, and queued receiver semantics."
    )
    provided_mode_port = next(
        port
        for swc in project.swcs
        if swc.name == "SpeedSensor"
        for port in swc.ports
        if port.name == "Pp_PowerState"
    )
    assert provided_mode_port.description == "Provided mode switch port for ECU power state."
    assert provided_mode_port.interfaceType == "modeSwitch"
    speed_port = next(
        port
        for swc in project.swcs
        if swc.name == "SpeedDisplay"
        for port in swc.ports
        if port.name == "Rp_VehicleSpeed"
    )
    assert speed_port.description == "Required sender-receiver port for receiving speed."
    power_state_port = next(
        port
        for swc in project.swcs
        if swc.name == "SpeedDisplay"
        for port in swc.ports
        if port.name == "Rp_PowerState"
    )
    assert power_state_port.description == "Required mode switch port for ECU power state."
    assert power_state_port.interfaceType == "modeSwitch"
    assert power_state_port.modeGroupRef == "Mdg_PowerState"
    on_power_on = next(
        runnable
        for swc in project.swcs
        if swc.name == "SpeedDisplay"
        for runnable in swc.runnables
        if runnable.name == "Runnable_OnPowerOn"
    )
    assert [(event.port, event.mode) for event in on_power_on.modeSwitchEvents] == [("Rp_PowerState", "ON")]
    assert next(data_type for data_type in project.applicationDataTypes if data_type.name == "App_VehicleSpeed").description == (
        "Vehicle speed value shared between the demo SWC types."
    )
    assert next(data_type for data_type in project.implementationDataTypes if data_type.name == "Impl_VehicleSpeed_U16").description == (
        "Raw implementation type for a vehicle speed sample."
    )
    assert next(compu for compu in project.compuMethods if compu.name == "CM_VehicleSpeed_Kph").description == (
        "Identity scaling for the demo vehicle speed value."
    )
    assert project.system.description == (
        "Demo AUTOSAR system wiring explicit, implicit, and queued speed flows plus one mode-switch flow."
    )


def test_main_example_mode_declaration_group_is_loaded_into_model_ir() -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)

    assert [group.name for group in project.modeDeclarationGroups] == ["Mdg_PowerState"]
    assert project.modeDeclarationGroups[0].description == "Power state modes for the ECU."
    assert project.modeDeclarationGroups[0].initialMode == "OFF"
    assert [mode.name for mode in project.modeDeclarationGroups[0].modes] == ["OFF", "ON", "SLEEP"]


def _extract_r_port_fragment(xml: str, port_name: str) -> str:
    match = re.search(
        rf"<R-PORT-PROTOTYPE>\s*<SHORT-NAME>{re.escape(port_name)}</SHORT-NAME>(.*?)</R-PORT-PROTOTYPE>",
        xml,
        flags=re.DOTALL,
    )
    assert match is not None, f"Missing R-PORT-PROTOTYPE for {port_name}"
    return match.group(1)


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


def test_cli_export_smoke() -> None:
    out_dir = REPO_ROOT / "build" / "test_cli_export_examples"
    if out_dir.exists():
        shutil.rmtree(out_dir)

    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "export", str(VALID_PROJECT), "--out", str(out_dir), "--split-by-swc"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("diagram_format", "expected_names"),
    [
        ("plantuml", PLANTUML_DIAGRAM_OUTPUTS),
    ],
)
def test_generate_diagrams_writes_expected_files(tmp_path: Path, diagram_format: str, expected_names: list[str]) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / diagram_format

    written = write_diagram_outputs(project, template_dir=template_dir, out=out_dir, fmt=diagram_format)

    assert [artifact.path.name for artifact in written] == expected_names


@pytest.mark.parametrize(
    ("diagram_format", "composition_name", "interface_name", "behavior_name"),
    [
        ("plantuml", "SpeedSensor_1", "If_VehicleSpeed", "Runnable_PublishVehicleSpeed"),
    ],
)
def test_generate_diagrams_contain_expected_smoke_fragments(
    tmp_path: Path,
    diagram_format: str,
    composition_name: str,
    interface_name: str,
    behavior_name: str,
) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / diagram_format

    _ = write_diagram_outputs(project, template_dir=template_dir, out=out_dir, fmt=diagram_format)
    extension = ".puml"

    composition_text = (out_dir / f"composition_DemoSystem{extension}").read_text(encoding="utf-8")
    interfaces_wiring_text = (out_dir / f"interfaces_wiring{extension}").read_text(encoding="utf-8")
    interfaces_contracts_text = (out_dir / f"interfaces_contracts{extension}").read_text(encoding="utf-8")
    behavior_text = (out_dir / f"behavior_SpeedSensor{extension}").read_text(encoding="utf-8")

    assert composition_name in composition_text
    assert "Rp_PowerState" in composition_text
    assert 'component "SpeedSensor_1"' in composition_text
    assert 'portout "Pp_VehicleSpeed"' in composition_text
    assert 'portin "Rp_PowerState"' in composition_text
    assert "Provided S/R" in composition_text
    assert "Required ModeSwitch" in composition_text
    assert "[#2e8b57]" in composition_text
    assert "[#8e44ad,dashed]" in composition_text
    assert ": C/S" not in composition_text
    assert "Application SWC" in composition_text
    assert "Client/Server connector" in composition_text
    assert interface_name in interfaces_wiring_text
    assert "SpeedDisplay_1" in interfaces_wiring_text
    assert "Rp_VehicleSpeed" in interfaces_wiring_text
    assert interface_name in interfaces_contracts_text
    assert "Mdg_PowerState" in interfaces_contracts_text
    assert "type__App_VehicleSpeed --> type__Impl_VehicleSpeed_U16 : impl" in interfaces_contracts_text
    assert behavior_name in behavior_text
    assert "Pp_VehicleSpeed" in behavior_text


@pytest.mark.parametrize(
    ("diagram_format", "expected_names"),
    [
        ("plantuml", PLANTUML_DIAGRAM_OUTPUTS),
    ],
)
def test_generate_diagrams_is_deterministic(tmp_path: Path, diagram_format: str, expected_names: list[str]) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out1 = tmp_path / f"{diagram_format}_1"
    out2 = tmp_path / f"{diagram_format}_2"

    _ = write_diagram_outputs(project, template_dir=template_dir, out=out1, fmt=diagram_format)
    _ = write_diagram_outputs(project, template_dir=template_dir, out=out2, fmt=diagram_format)

    assert sorted(path.name for path in out1.iterdir()) == sorted(expected_names)
    assert sorted(path.name for path in out2.iterdir()) == sorted(expected_names)

    for name in expected_names:
        data1 = (out1 / name).read_bytes()
        data2 = (out2 / name).read_bytes()
        assert data1 == data2
        assert hashlib.sha256(data1).hexdigest() == hashlib.sha256(data2).hexdigest()


def test_composition_diagram_uses_multi_column_layout_for_larger_systems() -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    expanded_project = replace(
        project,
        system=replace(
            project.system,
            composition=replace(
                project.system.composition,
                components=sorted(
                    [
                        *project.system.composition.components,
                        replace(project.system.composition.components[0], name="SpeedDisplay_2", typeRef="SpeedDisplay"),
                        replace(project.system.composition.components[1], name="SpeedSensor_2", typeRef="SpeedSensor"),
                        replace(project.system.composition.components[0], name="SpeedDisplay_3", typeRef="SpeedDisplay"),
                    ],
                    key=lambda component: component.name,
                ),
            ),
        ),
    )

    view = build_diagram_views(expanded_project).composition

    assert view.grid_columns == 2
    assert [len(row.instances) for row in view.rows] == [2, 2, 1]


def test_behavior_diagram_places_server_trigger_ports_in_incoming_lane() -> None:
    project = Project(
        autosar_version="4.2",
        rootPackage="DEMO",
        baseTypes=[],
        implementationDataTypes=[],
        applicationDataTypes=[],
        units=[],
        compuMethods=[],
        modeDeclarationGroups=[],
        interfaces=[
            Interface(
                name="If_Diagnostics",
                type="clientServer",
                operations=[],
            )
        ],
        swcs=[
            Swc(
                name="DiagServer",
                ports=[
                    Port(
                        name="Pp_Diagnostics",
                        direction="provides",
                        interfaceRef="If_Diagnostics",
                        interfaceType="clientServer",
                    ),
                    Port(
                        name="Rp_DiagnosticsClient",
                        direction="requires",
                        interfaceRef="If_Diagnostics",
                        interfaceType="clientServer",
                    ),
                ],
                runnables=[
                    Runnable(
                        name="Runnable_HandleRequest",
                        operationInvokedEvents=[
                            OperationInvokedEvent(
                                port="Pp_Diagnostics",
                                operation="ReadDtc",
                            )
                        ],
                    )
                ],
            )
        ],
        system=System(
            name="DemoSystem",
            composition=Composition(
                name="Composition_DemoSystem",
                components=[ComponentPrototype(name="DiagServer_1", typeRef="DiagServer")],
                connectors=[],
            ),
        ),
    )

    view = build_diagram_views(project).behaviors[0]

    assert [port.name for port in view.incoming_ports] == ["Pp_Diagnostics", "Rp_DiagnosticsClient"]
    assert [port.name for port in view.outgoing_ports] == []


def test_behavior_diagram_uses_runnable_grid_for_larger_behaviors() -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    speed_display = next(swc for swc in project.swcs if swc.name == "SpeedDisplay")
    expanded_runnables = sorted(
        [
            *speed_display.runnables,
            Runnable(name="Runnable_Extra1"),
            Runnable(name="Runnable_Extra2"),
            Runnable(name="Runnable_Extra3"),
        ],
        key=lambda runnable: runnable.name,
    )
    expanded_project = replace(
        project,
        swcs=[
            replace(swc, runnables=expanded_runnables) if swc.name == "SpeedDisplay" else swc
            for swc in project.swcs
        ],
    )

    view = next(behavior for behavior in build_diagram_views(expanded_project).behaviors if behavior.swc_name == "SpeedDisplay")

    assert view.runnable_columns == 2
    assert [len(row.runnables) for row in view.runnable_rows] == [2, 2, 2, 1]


def test_behavior_diagram_keeps_small_runnable_sets_in_one_row() -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    view = next(
        behavior for behavior in build_diagram_views(project).behaviors if behavior.swc_name == "SpeedDisplay"
    )

    assert len(view.runnables) == 4
    assert view.runnable_columns == 4
    assert [len(row.runnables) for row in view.runnable_rows] == [4]


@pytest.mark.parametrize(
    ("diagram_format", "expected_names"),
    [
        ("plantuml", PLANTUML_DIAGRAM_OUTPUTS),
    ],
)
def test_cli_generate_diagram_smoke(diagram_format: str, expected_names: list[str]) -> None:
    out_dir = REPO_ROOT / "build" / f"test_diagrams_{diagram_format}"
    if out_dir.exists():
        shutil.rmtree(out_dir)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "arforge.cli",
            "generate",
            "diagram",
            str(VALID_PROJECT),
            "--format",
            diagram_format,
            "--out",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(path.name for path in out_dir.iterdir()) == sorted(expected_names)


def test_warning_only_project_passes_validation_and_preserves_warning_report() -> None:
    project = load_and_validate_aggregator(WARNING_ONLY_PROJECT)
    report = build_semantic_report(project, ruleset="core")

    assert report.error_findings() == []
    assert any(finding.severity == FindingSeverity.WARNING for finding in report.findings)


def test_error_project_fails_validation() -> None:
    with pytest.raises(ValidationError):
        load_and_validate_aggregator(ERROR_PROJECT)


def test_mixed_warning_and_error_project_fails_and_reports_both_severities() -> None:
    project = load_aggregator(MIXED_PROJECT)
    report = build_semantic_report(project, ruleset="core")

    assert report.error_findings()
    assert any(finding.severity == FindingSeverity.WARNING for finding in report.findings)

    with pytest.raises(ValidationError):
        load_and_validate_aggregator(MIXED_PROJECT)


def test_cli_validate_verbose_includes_case_name() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(VALID_PROJECT), "-v"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CORE-021 PortInterfaceReferences RUN OK" in result.stdout


def test_cli_validate_extra_verbose_includes_case_description() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(VALID_PROJECT), "-vv"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CORE-021 PortInterfaceReferences" in result.stdout
    assert "Checks that each SWC port references an existing interface and uses the" in result.stdout
    assert "expected kind." in result.stdout


def test_cli_validate_main_example_has_clean_summary() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(VALID_PROJECT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "errors: 0" in result.stdout
    assert "warnings: 0" in result.stdout


def test_cli_validate_warning_only_project_shows_warning_and_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(WARNING_ONLY_PROJECT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARNING CORE-042-SR-CONNECTED-REQUIRES-UNUSED" in result.stdout
    assert "errors: 0" in result.stdout
    assert "warnings: 2" in result.stdout


def test_cs_server_unconnected_binding_passes_validation_and_reports_warning() -> None:
    project = load_and_validate_aggregator(CS_SERVER_WARNING_PROJECT)
    report = build_semantic_report(project, ruleset="core")

    assert report.error_findings() == []
    oie_findings = [finding for finding in report.findings if finding.code == "CORE-043-CS-OIE-UNCONNECTED"]
    assert oie_findings
    assert all(finding.severity == FindingSeverity.WARNING for finding in oie_findings)


def test_cli_validate_cs_server_unconnected_binding_warns_and_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(CS_SERVER_WARNING_PROJECT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARNING CORE-043-CS-OIE-UNCONNECTED" in result.stdout
    assert "errors: 0" in result.stdout


def test_cli_validate_error_project_shows_error_and_fails() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(ERROR_PROJECT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "ERROR" in result.stdout
    assert "errors: " in result.stdout


def test_cli_validate_mixed_project_shows_both_severities_and_fails() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(MIXED_PROJECT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "ERROR CORE-041-SR-READ-UNCONNECTED" in result.stdout
    assert "WARNING CORE-041-SR-REQUIRES-NO-INCOMING" in result.stdout


def test_validation_report_summary_counts_are_grouped_by_severity() -> None:
    project = load_aggregator(MIXED_PROJECT)
    report = build_semantic_report(project, ruleset="core")

    assert report.severity_counts() == {"error": 3, "warning": 2, "info": 0}


def test_main_example_has_no_declared_unused_port_findings() -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    report = build_semantic_report(project, ruleset="core")
    warning_codes = {finding.code for finding in report.findings if finding.severity == "warning"}

    assert "CORE-046-SR-PROVIDES-DECLARED-UNUSED" not in warning_codes
    assert "CORE-046-SR-REQUIRES-DECLARED-UNUSED" not in warning_codes
    assert "CORE-046-CS-PROVIDES-DECLARED-UNUSED" not in warning_codes
    assert "CORE-046-CS-REQUIRES-DECLARED-UNUSED" not in warning_codes
    assert "CORE-046-MS-REQUIRES-DECLARED-UNUSED" not in warning_codes


def test_main_example_has_no_connected_unused_mode_switch_requires_warning() -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    report = build_semantic_report(project, ruleset="core")
    warning_codes = {finding.code for finding in report.findings if finding.severity == "warning"}

    assert "CORE-047-MS-CONNECTED-REQUIRES-UNUSED" not in warning_codes


def test_main_example_has_no_unused_mode_declaration_group_warning() -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    report = build_semantic_report(project, ruleset="core")
    warning_codes = {finding.code for finding in report.findings if finding.severity == "warning"}

    assert "CORE-014-MDG-DECLARED-UNUSED" not in warning_codes


def test_unused_mode_group_project_passes_validation_and_reports_warning() -> None:
    project = load_and_validate_aggregator(UNUSED_MODE_GROUP_PROJECT)
    report = build_semantic_report(project, ruleset="core")

    assert report.error_findings() == []
    unused_group_findings = [finding for finding in report.findings if finding.code == "CORE-014-MDG-DECLARED-UNUSED"]
    assert len(unused_group_findings) == 1
    assert unused_group_findings[0].severity == FindingSeverity.WARNING
    assert unused_group_findings[0].message == (
        "ModeDeclarationGroup 'Mdg_UnusedPowerState' is declared but not referenced by any ModeSwitchInterface."
    )


def test_cli_validate_unused_mode_group_warns_and_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(UNUSED_MODE_GROUP_PROJECT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARNING CORE-014-MDG-DECLARED-UNUSED" in result.stdout
    assert "Mdg_UnusedPowerState" in result.stdout
    assert "errors: 0" in result.stdout
    assert "warnings: 1" in result.stdout


def test_connected_unused_mode_switch_project_passes_validation_and_reports_warning() -> None:
    project = load_and_validate_aggregator(CONNECTED_UNUSED_MODE_SWITCH_PROJECT)
    report = build_semantic_report(project, ruleset="core")

    assert report.error_findings() == []
    connected_findings = [
        finding for finding in report.findings if finding.code == "CORE-047-MS-CONNECTED-REQUIRES-UNUSED"
    ]
    assert len(connected_findings) == 1
    assert connected_findings[0].severity == FindingSeverity.WARNING
    assert connected_findings[0].message == (
        "Connected modeSwitch requires port 'SpeedDisplay_1.Rp_PowerState' is not used by any runnable modeSwitchEvents."
    )


def test_cli_validate_connected_unused_mode_switch_warns_and_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "arforge.cli", "validate", str(CONNECTED_UNUSED_MODE_SWITCH_PROJECT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARNING CORE-047-MS-CONNECTED-REQUIRES-UNUSED" in result.stdout
    assert "SpeedDisplay_1.Rp_PowerState" in result.stdout
    assert "errors: 0" in result.stdout


def test_split_export_reports_aligned_example_outputs(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    written = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    assert [path.name for path in written] == [
        SHARED_EXAMPLE_OUTPUT,
        "SpeedDisplay.arxml",
        "SpeedSensor.arxml",
        SYSTEM_EXAMPLE_OUTPUT,
    ]


def test_split_export_system_contains_one_clear_end_to_end_connection(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    system_xml = (out_dir / SYSTEM_EXAMPLE_OUTPUT).read_text(encoding="utf-8")

    assert "<SHORT-NAME>SpeedSensor_1</SHORT-NAME>" in system_xml
    assert "<SHORT-NAME>SpeedDisplay_1</SHORT-NAME>" in system_xml
    assert system_xml.count("<SW-COMPONENT-PROTOTYPE>") == 2
    assert system_xml.count("<ASSEMBLY-SW-CONNECTOR>") == 4
    assert "<TYPE-TREF DEST=\"APPLICATION-SW-COMPONENT-TYPE\">/DEMO/Components/SpeedSensor</TYPE-TREF>" in system_xml
    assert "<TYPE-TREF DEST=\"APPLICATION-SW-COMPONENT-TYPE\">/DEMO/Components/SpeedDisplay</TYPE-TREF>" in system_xml
    assert "/DEMO/System/Composition_DemoSystem/SpeedSensor_1/Pp_VehicleSpeed</TARGET-P-PORT-REF>" in system_xml
    assert "/DEMO/System/Composition_DemoSystem/SpeedDisplay_1/Rp_VehicleSpeed</TARGET-R-PORT-REF>" in system_xml
    assert "/DEMO/System/Composition_DemoSystem/SpeedDisplay_1/Rp_VehicleSpeedImplicit</TARGET-R-PORT-REF>" in system_xml
    assert "/DEMO/System/Composition_DemoSystem/SpeedDisplay_1/Rp_VehicleSpeedQueued</TARGET-R-PORT-REF>" in system_xml
    assert "/DEMO/System/Composition_DemoSystem/SpeedSensor_1/Pp_PowerState</TARGET-P-PORT-REF>" in system_xml
    assert "/DEMO/System/Composition_DemoSystem/SpeedDisplay_1/Rp_PowerState</TARGET-R-PORT-REF>" in system_xml


def test_split_export_shared_types_match_simple_example_model(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    shared_xml = (out_dir / SHARED_EXAMPLE_OUTPUT).read_text(encoding="utf-8")

    assert "<SHORT-NAME>If_VehicleSpeed</SHORT-NAME>" in shared_xml
    assert "<SHORT-NAME>If_PowerState</SHORT-NAME>" in shared_xml
    assert "<SHORT-NAME>VehicleSpeed</SHORT-NAME>" in shared_xml
    assert "<TYPE-TREF DEST=\"APPLICATION-PRIMITIVE-DATA-TYPE\">/DEMO/ApplicationDataTypes/App_VehicleSpeed</TYPE-TREF>" in shared_xml
    assert "<SHORT-NAME>App_VehicleSpeed</SHORT-NAME>" in shared_xml
    assert "<SHORT-NAME>Impl_VehicleSpeed_U16</SHORT-NAME>" in shared_xml
    assert "<SHORT-NAME>CM_VehicleSpeed_Kph</SHORT-NAME>" in shared_xml
    assert "<SHORT-NAME>km_per_h</SHORT-NAME>" in shared_xml
    assert "<SHORT-NAME>Mdg_PowerState</SHORT-NAME>" in shared_xml
    assert "<INITIAL-MODE-REF DEST=\"MODE-DECLARATION\">/DEMO/Modes/Mdg_PowerState/OFF</INITIAL-MODE-REF>" in shared_xml
    assert "<SHORT-NAME>SLEEP</SHORT-NAME>" in shared_xml
    assert "<MODE-SWITCH-INTERFACE>" in shared_xml
    assert "<TYPE-TREF DEST=\"MODE-DECLARATION-GROUP\">/DEMO/Modes/Mdg_PowerState</TYPE-TREF>" in shared_xml


def test_split_export_swc_files_contain_aligned_runnables_and_ports(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_sensor_xml = (out_dir / "SpeedSensor.arxml").read_text(encoding="utf-8")
    speed_display_xml = (out_dir / "SpeedDisplay.arxml").read_text(encoding="utf-8")

    assert "<SHORT-NAME>Runnable_PublishVehicleSpeed</SHORT-NAME>" in speed_sensor_xml
    assert "<SHORT-NAME>Pp_VehicleSpeed</SHORT-NAME>" in speed_sensor_xml
    assert "<SHORT-NAME>Pp_PowerState</SHORT-NAME>" in speed_sensor_xml
    assert "<PROVIDED-INTERFACE-TREF DEST=\"MODE-SWITCH-INTERFACE\">/DEMO/Interfaces/If_PowerState</PROVIDED-INTERFACE-TREF>" in speed_sensor_xml
    assert "<SHORT-NAME>Runnable_ReadVehicleSpeed</SHORT-NAME>" in speed_display_xml
    assert "<SHORT-NAME>Runnable_ReadVehicleSpeedImplicit</SHORT-NAME>" in speed_display_xml
    assert "<SHORT-NAME>Runnable_ReadVehicleSpeedQueued</SHORT-NAME>" in speed_display_xml
    assert "<SHORT-NAME>Runnable_OnPowerOn</SHORT-NAME>" in speed_display_xml
    assert "<SHORT-NAME>Rp_VehicleSpeed</SHORT-NAME>" in speed_display_xml
    assert "<SHORT-NAME>Rp_VehicleSpeedImplicit</SHORT-NAME>" in speed_display_xml
    assert "<SHORT-NAME>Rp_VehicleSpeedQueued</SHORT-NAME>" in speed_display_xml
    assert "<SHORT-NAME>Rp_PowerState</SHORT-NAME>" in speed_display_xml
    assert "<REQUIRED-INTERFACE-TREF DEST=\"MODE-SWITCH-INTERFACE\">/DEMO/Interfaces/If_PowerState</REQUIRED-INTERFACE-TREF>" in speed_display_xml
    assert "<MODE-SWITCH-EVENT>" in speed_display_xml
    assert "<SHORT-NAME>MSE_Runnable_OnPowerOn_Rp_PowerState_ON</SHORT-NAME>" in speed_display_xml
    assert "<TARGET-MODE-DECLARATION-REF DEST=\"MODE-DECLARATION\">/DEMO/Modes/Mdg_PowerState/ON</TARGET-MODE-DECLARATION-REF>" in speed_display_xml


def test_split_export_preserves_explicit_sr_receiver_semantics(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_display_xml = (out_dir / "SpeedDisplay.arxml").read_text(encoding="utf-8")
    explicit_fragment = _extract_r_port_fragment(speed_display_xml, "Rp_VehicleSpeed")

    assert "<NONQUEUED-RECEIVER-COM-SPEC>" in explicit_fragment
    assert "<ENABLE-UPDATE>true</ENABLE-UPDATE>" in explicit_fragment


def test_split_export_preserves_implicit_sr_receiver_semantics(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_display_xml = (out_dir / "SpeedDisplay.arxml").read_text(encoding="utf-8")
    implicit_fragment = _extract_r_port_fragment(speed_display_xml, "Rp_VehicleSpeedImplicit")

    assert "<NONQUEUED-RECEIVER-COM-SPEC>" in implicit_fragment
    assert "<ENABLE-UPDATE>false</ENABLE-UPDATE>" in implicit_fragment


def test_split_export_preserves_queued_sr_receiver_semantics(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_display_xml = (out_dir / "SpeedDisplay.arxml").read_text(encoding="utf-8")
    queued_fragment = _extract_r_port_fragment(speed_display_xml, "Rp_VehicleSpeedQueued")

    assert "<QUEUED-RECEIVER-COM-SPEC>" in queued_fragment
    assert "<QUEUE-LENGTH>4</QUEUE-LENGTH>" in queued_fragment


def test_split_export_explicit_and_implicit_receiver_fragments_differ(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    _ = write_outputs(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_display_xml = (out_dir / "SpeedDisplay.arxml").read_text(encoding="utf-8")
    explicit_fragment = _extract_r_port_fragment(speed_display_xml, "Rp_VehicleSpeed")
    implicit_fragment = _extract_r_port_fragment(speed_display_xml, "Rp_VehicleSpeedImplicit")

    assert explicit_fragment != implicit_fragment


def test_main_example_omitted_swc_category_defaults_to_application() -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)

    assert next(swc for swc in project.swcs if swc.name == "SpeedSensor").category == "application"
    assert next(swc for swc in project.swcs if swc.name == "SpeedDisplay").category == "application"


def test_split_export_uses_swc_category_for_component_types_and_prototype_dests(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    categorized_project = replace(
        project,
        swcs=[
            replace(swc, category="service") if swc.name == "SpeedSensor" else replace(swc, category="complexDeviceDriver")
            for swc in project.swcs
        ],
    )

    _ = write_outputs(categorized_project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    speed_sensor_xml = (out_dir / "SpeedSensor.arxml").read_text(encoding="utf-8")
    speed_display_xml = (out_dir / "SpeedDisplay.arxml").read_text(encoding="utf-8")
    system_xml = (out_dir / SYSTEM_EXAMPLE_OUTPUT).read_text(encoding="utf-8")

    assert "<SERVICE-SW-COMPONENT-TYPE>" in speed_sensor_xml
    assert "<APPLICATION-SW-COMPONENT-TYPE>" not in speed_sensor_xml
    assert "<COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE>" in speed_display_xml
    assert "<TYPE-TREF DEST=\"SERVICE-SW-COMPONENT-TYPE\">/DEMO/Components/SpeedSensor</TYPE-TREF>" in system_xml
    assert "<TYPE-TREF DEST=\"COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE\">/DEMO/Components/SpeedDisplay</TYPE-TREF>" in system_xml


def test_split_export_orders_outputs_deterministically(tmp_path: Path) -> None:
    project = load_and_validate_aggregator(VALID_PROJECT)
    template_dir = REPO_ROOT / "templates"
    out_dir = tmp_path / "out"
    report = write_outputs_with_report(project, template_dir=template_dir, out=out_dir, split_by_swc=True)

    swc_outputs = [
        artifact.path.name
        for artifact in report.outputs
        if artifact.path.name.endswith(".arxml") and artifact.path.name not in {SHARED_EXAMPLE_OUTPUT, SYSTEM_EXAMPLE_OUTPUT}
    ]
    assert swc_outputs == ["SpeedDisplay.arxml", "SpeedSensor.arxml"]


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    [
        ("project_data_receive_event_unknown_port.yaml", "CORE-027-DRE-UNKNOWN-PORT"),
        ("project_data_receive_event_unknown_dataelement.yaml", "CORE-027-DRE-UNKNOWN-DATAELEMENT"),
        ("project_data_receive_event_on_provides_port.yaml", "CORE-027-DRE-DIRECTION"),
        ("project_data_receive_event_on_client_server_port.yaml", "CORE-027-DRE-INTERFACE-TYPE"),
        ("project_cs_call_unconnected.yaml", "CORE-043-CS-CALL-UNCONNECTED"),
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
        ("project_mode_group_duplicate_modes.yaml", "CORE-012-MDG-DUPLICATE-MODE"),
        ("project_mode_group_bad_initial_mode.yaml", "CORE-013-MDG-INITIAL-MODE"),
        ("project_mode_switch_interface_unknown_mode_group.yaml", "CORE-010-MS-UNKNOWN-MODE-GROUP-REF"),
        ("project_mode_switch_event_unknown_port.yaml", "CORE-028-MSE-UNKNOWN-PORT"),
        ("project_mode_switch_event_on_provides_port.yaml", "CORE-028-MSE-DIRECTION"),
        ("project_mode_switch_event_on_non_mode_switch_port.yaml", "CORE-028-MSE-INTERFACE-TYPE"),
        ("project_mode_switch_event_unknown_mode.yaml", "CORE-028-MSE-UNKNOWN-MODE"),
    ],
)
def test_data_receive_event_invalid_fixtures_emit_expected_codes(fixture_name: str, expected_code: str) -> None:
    project = load_aggregator(INVALID_DIR / fixture_name)
    report = build_semantic_report(project, ruleset="core")
    error_codes = {finding.code for finding in report.error_findings()}
    assert expected_code in error_codes


@pytest.mark.parametrize(
    ("fixture_name", "expected_warning"),
    [
        ("project_declared_unused_sr_provides.yaml", "CORE-046-SR-PROVIDES-DECLARED-UNUSED"),
        ("project_connected_sr_port_unused.yaml", "CORE-046-SR-REQUIRES-DECLARED-UNUSED"),
        ("project_declared_unused_cs_requires.yaml", "CORE-046-CS-REQUIRES-DECLARED-UNUSED"),
        ("project_declared_unused_cs_provides.yaml", "CORE-046-CS-PROVIDES-DECLARED-UNUSED"),
        ("project_declared_unused_mode_requires.yaml", "CORE-046-MS-REQUIRES-DECLARED-UNUSED"),
        ("project_connected_mode_switch_port_unused.yaml", "CORE-047-MS-CONNECTED-REQUIRES-UNUSED"),
        ("project_unused_mode_group.yaml", "CORE-014-MDG-DECLARED-UNUSED"),
        ("project_sr_read_unconnected.yaml", "CORE-041-SR-REQUIRES-NO-INCOMING"),
        ("project_sr_write_unconnected.yaml", "CORE-041-SR-PROVIDES-NO-OUTGOING"),
        ("project_cs_call_unconnected.yaml", "CORE-044-CS-REQUIRES-NO-CONNECTOR"),
        ("project_connected_sr_port_unused.yaml", "CORE-042-SR-CONNECTED-REQUIRES-UNUSED"),
        ("project_cs_server_oie_unconnected.yaml", "CORE-043-CS-OIE-UNCONNECTED"),
    ],
)
def test_invalid_project_fixtures_emit_expected_warnings(fixture_name: str, expected_warning: str) -> None:
    project = load_aggregator(INVALID_DIR / fixture_name)
    report = build_semantic_report(project, ruleset="core")
    warning_codes = {finding.code for finding in report.findings if finding.severity == "warning"}
    assert expected_warning in warning_codes


def test_open_mode_switch_ports_emit_connectivity_warnings() -> None:
    project = load_aggregator(INVALID_DIR / "project_mode_switch_unconnected.yaml")
    report = build_semantic_report(project, ruleset="core")
    warning_codes = {finding.code for finding in report.findings if finding.severity == "warning"}

    assert "CORE-045-MS-PROVIDES-NO-OUTGOING" in warning_codes
    assert "CORE-045-MS-REQUIRES-NO-INCOMING" in warning_codes


def test_sr_timing_equal_fixture_has_no_timing_mismatch_findings() -> None:
    project = load_aggregator(INVALID_DIR / "project_sr_timing_equal.yaml")
    report = build_semantic_report(project, ruleset="core")
    warning_codes = {finding.code for finding in report.findings if finding.severity == "warning"}
    assert "CORE-050" not in warning_codes
    assert "CORE-051" not in warning_codes


@pytest.mark.parametrize(
    ("fixture_name", "expected_warning"),
    [
        ("project_sr_consumer_faster.yaml", "CORE-050"),
        ("project_sr_producer_faster.yaml", "CORE-051"),
    ],
)
def test_sr_timing_warning_fixtures_emit_expected_codes(fixture_name: str, expected_warning: str) -> None:
    project = load_aggregator(INVALID_DIR / fixture_name)
    report = build_semantic_report(project, ruleset="core")
    warning_codes = {finding.code for finding in report.findings if finding.severity == "warning"}
    assert expected_warning in warning_codes


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
