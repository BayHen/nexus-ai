"""ASGI entrypoint for NEXUS AI."""

from nexus.bootstrap.application import create_app

app = create_app()
