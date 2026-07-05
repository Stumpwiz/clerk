"""
setup.py - Installation configuration for community administration backend models

This allows the backend models to be installed as a package and shared
with other projects (e.g., scribe).
"""

from setuptools import setup, find_packages

setup(
    name="community-admin-backend",
    version="0.1.0",
    description="Community administration backend models and database utilities",
    author="George Wright",
    packages=find_packages(),
    install_requires=[
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.11",
        "pydantic>=2.0",
        "pydantic-settings>=2.0.0",
    ],
    python_requires=">=3.10",
)
