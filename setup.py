"""
QA Bob-iverse Setup
"""

from setuptools import setup, find_packages

setup(
    name="qa-lab",
    version="4.0.0",
    description="QA Bob-iverse Autonomic Research Lab",
    packages=find_packages(),
    install_requires=[
        "pyzmq",
        "numpy",
        "matplotlib",
        "torch",
        "torchvision",
        "tqdm",
        "pytest",
        "mkdocs",
        "mkdocs-material",
        "networkx",
        "scipy",
        "scikit-learn",
    ],
    entry_points={
        "console_scripts": [
            "qa=qa_agents.cli.qa_cli:main",
        ],
    },
    python_requires=">=3.8",
)
