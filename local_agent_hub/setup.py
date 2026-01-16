"""
Setup script for local_agent_hub
"""
from setuptools import setup, find_packages

setup(
    name="local_agent_hub",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.27.0",
        "cryptography>=42.0.0",
        "pydantic>=2.5.3",
        "pydantic-settings>=2.1.0",
        "pyyaml>=6.0.1",
        "python-dotenv>=1.0.0",
        "structlog>=24.1.0",
    ],
)
