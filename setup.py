"""
Setup script for Agentic OS.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="agentic-os",
    version="0.1.0",
    description="Agentic OS - Userspace Sandwich Layer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Agentic OS Team",
    python_requires=">=3.11",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "agentic-os=core.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX :: Linux",
    ],
)
