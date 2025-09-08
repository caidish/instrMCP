from setuptools import setup, find_packages
from pathlib import Path

HERE = Path(__file__).parent.resolve()

# Get version from package.json
import json
with open(HERE / "package.json", "r") as f:
    package_json = json.load(f)
    version = package_json["version"]
    description = package_json["description"]

# Read long description from README
long_description = (HERE / "README.md").read_text(encoding="utf-8")

setup(
    name="mcp_active_cell_bridge",
    version=version,
    description=description,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="InstrMCP Contributors",
    url="https://github.com/caijiaqi/instrMCP",
    license="MIT",
    platforms=["Linux", "Mac OS X", "Windows"],
    keywords=["Jupyter", "JupyterLab", "MCP"],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: Jupyter",
        "Framework :: Jupyter :: JupyterLab",
        "Framework :: Jupyter :: JupyterLab :: 4",
        "Framework :: Jupyter :: JupyterLab :: Extensions",
        "Framework :: Jupyter :: JupyterLab :: Extensions :: Prebuilt",
    ],
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "mcp_active_cell_bridge": ["labextension/**"],
    },
    data_files=[
        ("share/jupyter/labextensions/mcp-active-cell-bridge", ["install.json"]),
    ],
    python_requires=">=3.8",
    install_requires=[
        "jupyterlab>=4.0.0,<5",
    ],
    zip_safe=False,
)