"""Production WSGI entry point. ProxyFix is configured by the app factory."""
from petcare import create_app


app = create_app()
