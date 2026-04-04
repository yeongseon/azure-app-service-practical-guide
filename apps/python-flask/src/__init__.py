"""Flask application package for Azure App Service reference app."""

from .app import app, create_app

__all__ = ["app", "create_app"]
