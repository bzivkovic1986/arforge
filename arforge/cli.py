from __future__ import annotations

from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel

from .validate import ValidationError, build_semantic_report, format_finding, load_aggregator, load_and_validate_aggregator
from .exporter import write_outputs

app = typer.Typer(add_completion=False, help="ARForge (AUTOSAR Classic 4.2 YAML → ARXML)")

console = Console()

def _default_template_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "templates"

@app.command()
def validate(
    project: Path,
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Show validation case execution details (-vv adds timing)."),
):
    """Validate the aggregator project and all referenced YAML files (supports globs)."""
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
    split_by_swc: bool = typer.Option(False, "--split-by-swc", help="Write shared.arxml + one <SWC>.arxml per component + system.arxml"),
    templates: Path = typer.Option(None, help="Template directory"),
):
    """Validate then export ARXML using Jinja2 templates."""
    template_dir = templates or _default_template_dir()

    try:
        p = load_and_validate_aggregator(project)
    except ValidationError as e:
        console.print(Panel.fit(f"[red]FAILED[/red] {project}", title="export"))
        for msg in e.errors:
            console.print(f" - {msg}")
        raise typer.Exit(code=2)

    if split_by_swc:
        if out.suffix.lower() in [".arxml", ".xml"]:
            console.print("[yellow]Note:[/yellow] --split-by-swc expects --out to be a directory; using its parent directory.")
            out = out.parent
    else:
        if out.is_dir() or out.suffix == "":
            console.print("[red]Error:[/red] monolithic export expects a file path like build/all.arxml")
            raise typer.Exit(code=2)

    written = write_outputs(p, template_dir=template_dir, out=out, split_by_swc=split_by_swc)
    console.print(Panel.fit("[green]Export complete[/green]", title="export"))
    for wp in written:
        console.print(f" - {wp}")

if __name__ == "__main__":
    app()
