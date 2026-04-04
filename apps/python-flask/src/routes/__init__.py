"""Blueprint registration for API routes."""

from importlib import import_module

from .demo import register_demo_blueprints
from .health import health_bp
from .info import info_bp


flask = import_module("flask")
Flask = flask.Flask


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(info_bp)
    register_demo_blueprints(app)
