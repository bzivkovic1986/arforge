from __future__ import annotations

from pathlib import Path
from time import perf_counter

import typer
from rich.console import Console
from rich.panel import Panel

from .exporter import ExportInputSummary, InputPatternExpansion, write_outputs, write_outputs_with_report
from .scaffold import scaffold_project
from .validate import (
    ValidationError,
    build_semantic_report,
    format_finding,
    load_aggregator,
    load_and_validate_aggregator,
    load_aggregator_with_report,
)

app = typer.Typer(
    add_completion=False,
    help=(
        "ARForge (AUTOSAR Classic YAML -> ARXML).\n"
    ),
)

console = Console()


def _default_template_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "templates"


def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    return f"{size_bytes / 1024.0:.1f} KB"


def _print_pattern_summary(label: str, patterns: list[InputPatternExpansion], preview_limit: int = 3) -> None:
    total = sum(len(p.matched_files) for p in patterns)
    console.print(f"{label}: patterns={len(patterns)} matched_files={total}")
    for p in patterns:
        console.print(f" - pattern '{p.pattern}' -> {len(p.matched_files)} files")
        for path in p.matched_files[:preview_limit]:
            console.print(f"   - {path}")
        if len(p.matched_files) > preview_limit:
            console.print(f"   - ... ({len(p.matched_files) - preview_limit} more)")


def _format_case_metrics(case) -> str:
    return f"(ms={case.duration_ms:.2f} findings={case.finding_count})"


def _format_cli_finding(finding) -> str:
    return f"{finding.code} {format_finding(finding)}"


def _severity_label(severity: str) -> str:
    return severity.upper()


def _severity_style(severity: str) -> str:
    if severity == "error":
        return "red"
    if severity == "warning":
        return "yellow"
    return "cyan"


def _print_colored_finding(prefix: str, finding) -> None:
    label = _severity_label(finding.severity)
    style = _severity_style(finding.severity)
    console.print(f"{prefix}[{style}]{label}[/{style}] {_format_cli_finding(finding)}")


def _print_validation_summary(report) -> None:
    counts = report.severity_counts()
    console.print("summary:")
    console.print(f" - errors: {counts['error']}")
    console.print(f" - warnings: {counts['warning']}")
    console.print(f" - infos: {counts['info']}")


@app.command()
def validate(
    project: Path,
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help=(
            "Validation verbosity:\n"
            "-v  show which validation cases ran (OK/SKIP/FAIL)\n"
            "-vv also show per-case timing and finding counts"
        ),
    ),
):
    """Validate project YAMLs (supports globs).
    Use -v/-vv for semantic validation execution details."""
    try:
        parsed = load_aggregator(project)
        report = build_semantic_report(parsed, ruleset="core")
        has_errors = bool(report.error_findings())

        if verbose > 0:
            console.print(f"ruleset={report.ruleset} cases={len(report.case_results)}")
            for case in report.case_results:
                if case.status == "skip":
                    if verbose >= 2:
                        console.print(f" - {case.case_id} {case.name}")
                        console.print(f"   {case.description}")
                        console.print(f"   SKIP ({case.reason}) {_format_case_metrics(case)}")
                    else:
                        console.print(f" - {case.case_id} {case.name} SKIP ({case.reason}) {_format_case_metrics(case)}")
                    continue

                if verbose >= 2:
                    console.print(f" - {case.case_id} {case.name}")
                    console.print(f"   {case.description}")
                    console.print(f"   RUN {case.outcome.upper()} {_format_case_metrics(case)}")
                    for finding in case.findings:
                        _print_colored_finding("   ", finding)
                else:
                    console.print(f" - {case.case_id} {case.name} RUN {case.outcome.upper()} {_format_case_metrics(case)}")
        elif report.findings:
            for finding in report.findings:
                _print_colored_finding("", finding)

        _print_validation_summary(report)

        if has_errors:
            console.print(Panel.fit(f"[red]FAILED[/red] {project}", title="validate"))
            raise typer.Exit(code=2)

        console.print(Panel.fit(f"[green]OK[/green] Valid: {project}", title="validate"))
    except ValidationError as e:
        console.print(Panel.fit(f"[red]FAILED[/red] {project}", title="validate"))
        for msg in e.errors:
            console.print(f" - {msg}")
        raise typer.Exit(code=2)


@app.command()
def export(
    project: Path,
    out: Path = typer.Option(..., help="Output ARXML path (file) or directory when --split-by-swc"),
    split_by_swc: bool = typer.Option(
        False,
        "--split-by-swc",
        help="Write <Project>_SharedTypes.arxml + one <SWC>.arxml per component + <System>.arxml",
    ),
    templates: Path = typer.Option(None, help="Template directory"),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help=(
            "Export verbosity:\n"
            "-v  show resolved inputs (glob expansion), layout, and templates used\n"
            "-vv also show model counts, stage timings, and output file sizes"
        ),
    ),
):
    """Validate then export ARXML using Jinja2 templates.
    Use -v/-vv for detailed export diagnostics."""
    template_dir = templates or _default_template_dir()

    if split_by_swc:
        if out.suffix.lower() in [".arxml", ".xml"]:
            console.print("[yellow]Note:[/yellow] --split-by-swc expects --out to be a directory; using its parent directory.")
            out = out.parent
    else:
        if out.is_dir() or out.suffix == "":
            console.print("[red]Error:[/red] monolithic export expects a file path like build/all.arxml")
            raise typer.Exit(code=2)

    try:
        if verbose <= 0:
            p = load_and_validate_aggregator(project)
            written = write_outputs(p, template_dir=template_dir, out=out, split_by_swc=split_by_swc)
            console.print(Panel.fit("[green]Export complete[/green]", title="export"))
            for wp in written:
                console.print(f" - {wp}")
            return

        parsed, load_report = load_aggregator_with_report(project)
        sem_started = perf_counter()
        sem_report = build_semantic_report(parsed, ruleset="core")
        semantic_ms = (perf_counter() - sem_started) * 1000.0
        sem_errors = [format_finding(f) for f in sem_report.error_findings()]
        if sem_errors:
            console.print(Panel.fit(f"[red]FAILED[/red] {project}", title="export"))
            for msg in sem_errors:
                console.print(f" - {msg}")
            raise typer.Exit(code=2)

        input_summary = ExportInputSummary(
            base_types_file=load_report.base_types_file,
            implementation_types_file=load_report.implementation_types_file,
            application_types_file=load_report.application_types_file,
            unit_patterns=[
                InputPatternExpansion(pattern=p.pattern, matched_files=p.matched_files)
                for p in load_report.unit_patterns
            ],
            compu_method_patterns=[
                InputPatternExpansion(pattern=p.pattern, matched_files=p.matched_files)
                for p in load_report.compu_method_patterns
            ],
            interface_patterns=[
                InputPatternExpansion(pattern=p.pattern, matched_files=p.matched_files)
                for p in load_report.interface_patterns
            ],
            swc_patterns=[
                InputPatternExpansion(pattern=p.pattern, matched_files=p.matched_files)
                for p in load_report.swc_patterns
            ],
            system_file=load_report.system_file,
        )
        export_report = write_outputs_with_report(
            parsed,
            template_dir=template_dir,
            out=out,
            split_by_swc=split_by_swc,
            project_path=project,
            autosar_version=parsed.autosar_version,
            input_summary=input_summary,
            stage_timings_ms={
                "load+schema validation": load_report.load_schema_ms,
                "model build": load_report.model_build_ms,
                "semantic validation": semantic_ms,
            },
        )

        console.print(f"project={project} autosar={export_report.autosar_version}")
        if export_report.input_summary:
            if export_report.input_summary.base_types_file:
                console.print(f"baseTypes: {export_report.input_summary.base_types_file}")
            if export_report.input_summary.implementation_types_file:
                console.print(f"implementationDataTypes: {export_report.input_summary.implementation_types_file}")
            if export_report.input_summary.application_types_file:
                console.print(f"applicationDataTypes: {export_report.input_summary.application_types_file}")
            if export_report.input_summary.unit_patterns:
                _print_pattern_summary("units", export_report.input_summary.unit_patterns)
            if export_report.input_summary.compu_method_patterns:
                _print_pattern_summary("compuMethods", export_report.input_summary.compu_method_patterns)
            _print_pattern_summary("interfaces", export_report.input_summary.interface_patterns)
            _print_pattern_summary("swcs", export_report.input_summary.swc_patterns)
            if export_report.input_summary.system_file:
                console.print(f"system: {export_report.input_summary.system_file}")

        if export_report.layout == "split-by-swc":
            console.print("layout=split-by-swc (shared types + per-SWC + system)")
        else:
            console.print("layout=monolithic")

        console.print(f"templates dir: {export_report.template_dir}")
        if export_report.layout == "split-by-swc":
            console.print(
                "templates: "
                f"shared={export_report.templates['shared']} "
                f"swc={export_report.templates['swc']} "
                f"system={export_report.templates['system']}"
            )
        else:
            console.print(f"templates: monolithic={export_report.templates['monolithic']}")

        if verbose >= 2:
            ms = export_report.model_summary
            console.print(
                "model: "
                f"datatypes={ms.datatypes_count} "
                f"interfaces={ms.interfaces_count} (SR={ms.sr_interfaces_count}, CS={ms.cs_interfaces_count}) "
                f"swcs={ms.swcs_count} "
                f"instances={ms.instances_count} connectors={ms.connectors_count}"
            )
            console.print("timings (ms):")
            for key in ["load+schema validation", "model build", "semantic validation", "rendering", "writing"]:
                value = export_report.timings_ms.get(key, 0.0)
                console.print(f" - {key}: {value:.2f}")

    except ValidationError as e:
        console.print(Panel.fit(f"[red]FAILED[/red] {project}", title="export"))
        for msg in e.errors:
            console.print(f" - {msg}")
        raise typer.Exit(code=2)

    console.print(Panel.fit("[green]Export complete[/green]", title="export"))
    for artifact in export_report.outputs if verbose > 0 else []:
        if verbose >= 2:
            console.print(f" - {artifact.path} ({_fmt_size(artifact.size_bytes)})")
        else:
            console.print(f" - {artifact.path}")


@app.command()
def init(
    path: Path,
    name: str = typer.Option("DemoSystem", "--name", help="System name used in scaffold files."),
    force: bool = typer.Option(False, "--force", help="Allow scaffolding into an existing non-empty directory."),
    no_example: bool = typer.Option(
        False,
        "--no-example",
        help="Create the project structure without the runnable example.",
    ),
):
    """Scaffold a new ARForge project directory."""
    try:
        written = scaffold_project(path, name=name, force=force, no_example=no_example)
    except FileExistsError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=2)

    mode = "structure-only" if no_example else "example"
    console.print(Panel.fit(f"[green]Scaffold created[/green] ({mode})", title="init"))
    for p in written:
        console.print(f" - {p}")


if __name__ == "__main__":
    app()
