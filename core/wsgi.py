"""
WSGI compatibility entrypoint for legacy deployment commands.
Delegates directly to config.wsgi.application.
"""
from config.wsgi import application

__all__ = ['application']
