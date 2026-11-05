"""WSGI entry point for hosting (PythonAnywhere, gunicorn, ...):  from wsgi import application"""
from app import app as application  # noqa: F401
