from __future__ import annotations

from pathlib import Path
from time import perf_counter

import typer
from rich.console import Console
from rich.panel import Panel

from .exporter import ExportInputSummary, InputPatternExpansion, write_outputs, write_outputs_with_report
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
    help="ARForge (AUTOSAR Classic 4.2 YAML -> ARXML). validate supports -v/-vv verbosity.",
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


@app.command()
def validate(
    project: Path,
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Validation verbosity: -v shows case execution, -vv adds timing and finding counts.",
    ),
):
    """Validate project YAMLs (supports globs, -v/-vv for semantic execution details)."""
    try:
        if verbose <= 0:
            _ = load_and_validate_aggregator(project)
            console.print(Panel.fit(f"[green]OK[/green] Valid: {project}", title="validate"))
            return

        parsed = load_aggregator(project)
        report = build_semantic_report(parsed, ruleset="core")
        error_messages = [format_finding(f) for f in report.error_findings()]

        console.print(f"ruleset={report.ruleset} cases={len(report.case_results)}")
        for case in report.case_results:
            if case.status == "skip":
                if verbose >= 2:
                    console.print(f" - {case.case_id} SKIP ({case.reason}) (ms=0.00 findings=0)")
                else:
                    console.print(f" - {case.case_id} SKIP ({case.reason})")
                continue

            line = f" - {case.case_id} RUN {case.outcome.upper()}"
            if verbose >= 2:
                line += f" (ms={case.duration_ms:.2f} findings={case.finding_count})"
            console.print(line)

        if error_messages:
            console.print(Panel.fit(f"[red]FAILED[/red] {project}", title="validate"))
            for msg in error_messages:
                console.print(f" - {msg}")
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
        help="Write shared.arxml + one <SWC>.arxml per component + system.arxml",
    ),
    templates: Path = typer.Option(None, help="Template directory"),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Export verbosity: -v shows input/layout/template details, -vv adds model/timing/size details.",
    ),
):
    """Validate then export ARXML using Jinja2 templates."""
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
            datatypes_file=load_report.datatypes_file,
            interface_patterns=[
                InputPatternExpansion(pattern=p.pattern, matched_files=p.matched_files)
                for p in load_report.interface_patterns
            ],
            swc_patterns=[
                InputPatternExpansion(pattern=p.pattern, matched_files=p.matched_files)
                for p in load_report.swc_patterns
            ],
            system_file=load_report.system_file,
            connections_file=load_report.connections_file,
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
            console.print(f"datatypes: {export_report.input_summary.datatypes_file}")
            _print_pattern_summary("interfaces", export_report.input_summary.interface_patterns)
            _print_pattern_summary("swcs", export_report.input_summary.swc_patterns)
            if export_report.input_summary.system_file:
                console.print(f"system: {export_report.input_summary.system_file}")
            if export_report.input_summary.connections_file:
                console.print(f"connections: {export_report.input_summary.connections_file}")

        if export_report.layout == "split-by-swc":
            console.print("layout=split-by-swc (shared + per-SWC + system)")
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


if __name__ == "__main__":
    app()
