import typer

from vnalpha.cli_app import ask, cmd, data, eval, init, log, score, tui, watchlist
from vnalpha.cli_app.build import app as build_app
from vnalpha.cli_app.common import configure_app
from vnalpha.cli_app.outcome import app as outcome_app
from vnalpha.cli_app.sync import app as sync_app
from vnalpha.closed_loop.cli import repair_app, validate_app
from vnalpha.observability.cli_deploy import deploy_app
from vnalpha.observability.cli_logs import logs_app

app = typer.Typer(name="vnalpha", help="Alpha discovery research CLI.")
configure_app(app)
app.add_typer(sync_app, name="sync")
app.add_typer(build_app, name="build")
app.add_typer(data.app, name="data")
init.register(app)
score.register(app)
watchlist.register(app)
tui.register(app)
app.add_typer(outcome_app, name="outcome")
app.add_typer(eval.app, name="eval")
cmd.register(app)
ask.register(app)
log.register(app)
app.add_typer(logs_app, name="logs")
app.add_typer(repair_app, name="repair")
app.add_typer(deploy_app, name="deploy")
app.add_typer(validate_app, name="validate")
