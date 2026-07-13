from typing import Annotated

import typer

from autoharness import __version__

app = typer.Typer(
    name="harness",
    help="Audit AI agent repositories and generate reviewable reliability controls.",
    no_args_is_help=False,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """AutoHarness CLI bootstrap; product commands arrive through the build phases."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
