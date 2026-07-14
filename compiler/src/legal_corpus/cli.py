from pathlib import Path

import typer

from legal_corpus.config import load_local_env
from legal_corpus.compiler import CompileError, compile_sources
from legal_corpus.extractors.local_pdf import LocalPdfExtractor
from legal_corpus.export_records import ExportRecordError
from legal_corpus.reports import build_corpus_report, render_corpus_report
from legal_corpus.scaffold import ScaffoldError, create_scaffold
from legal_corpus.source_records import SourceRecordError
from legal_corpus.structure_records import StructureRecordError
from legal_corpus.validators.gbrain import validate_gbrain_corpus


app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Legal Corpus Compiler command line interface."""
    load_local_env(Path.cwd())


@app.command("init")
def init(target: Path) -> None:
    """Create a new legal corpus scaffold."""
    try:
        create_scaffold(target)
    except ScaffoldError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Legal corpus scaffold created: {target}")


@app.command("compile")
def compile_command(
    source: Path,
    output: Path,
    pdf_provider: str = typer.Option(
        "reducto",
        "--pdf-provider",
        help="PDF extraction provider: reducto or local.",
    ),
) -> None:
    """Extract source documents into raw sidecars."""
    if pdf_provider not in {"reducto", "local"}:
        typer.echo("Error: --pdf-provider must be reducto or local", err=True)
        raise typer.Exit(code=1)
    extractor = LocalPdfExtractor() if pdf_provider == "local" else None
    try:
        result = compile_sources(source, output, pdf_extractor=extractor)
    except (
        CompileError,
        ExportRecordError,
        ScaffoldError,
        SourceRecordError,
        StructureRecordError,
    ) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(
        f"Compiled {result.documents_compiled} source document(s) into {output} "
        f"with {result.generated_file_count} generated corpus file(s)"
    )


@app.command("config-check")
def config_check() -> None:
    """Report non-secret extraction provider configuration status."""
    import importlib.util
    import os

    env_path = load_local_env(Path.cwd())
    reducto_key = os.environ.get("REDUCTO_API_KEY")
    reducto_package = importlib.util.find_spec("reducto") is not None
    local_pdf = importlib.util.find_spec("fitz") is not None or importlib.util.find_spec("PyPDF2") is not None
    typer.echo("Legal Corpus Compiler config")
    typer.echo(f"Local .env: {'present' if env_path else 'not found'}")
    typer.echo(f"REDUCTO_API_KEY: {'configured' if reducto_key else 'missing'}")
    typer.echo(f"Reducto package: {'available' if reducto_package else 'missing'}")
    typer.echo(f"Local PDF extractor: {'available' if local_pdf else 'missing'}")


@app.command("validate")
def validate_command(output: Path) -> None:
    """Validate a compiled GBrain corpus folder."""
    result = validate_gbrain_corpus(output, update_manifest=True)
    if result.passed:
        typer.echo(
            f"Validation passed for {output} "
            f"with {result.warning_count} warning(s)"
        )
        return

    typer.echo(
        f"Validation failed for {output}: "
        f"{result.blocking_error_count} error(s), {result.warning_count} warning(s)",
        err=True,
    )
    for issue in result.issues[:25]:
        location = f" [{issue.path}]" if issue.path else ""
        typer.echo(
            f"- {issue.severity}: {issue.category}{location} {issue.message}",
            err=True,
        )
    raise typer.Exit(code=1)


@app.command("report")
def report_command(output: Path) -> None:
    """Print a summary report for a compiled GBrain corpus folder."""
    typer.echo(render_corpus_report(build_corpus_report(output)))


if __name__ == "__main__":
    app()
