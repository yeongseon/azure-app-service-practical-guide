"""Demo endpoint blueprints."""

from importlib import import_module

from .dependencies import dependencies_bp
from .exceptions import exceptions_bp
from .requests import requests_bp


flask = import_module("flask")
Flask = flask.Flask


def register_demo_blueprints(app: Flask) -> None:
    app.register_blueprint(requests_bp)
    app.register_blueprint(dependencies_bp)
    app.register_blueprint(exceptions_bp)
