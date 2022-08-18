from setuptools import setup
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="aws-ssh-tunnel",
    version="2.0.1",
    author="Daniel Molenaars",
    author_email="danielmolenaars@binx.io",
    description="CLI for port forwarding sessions with private AWS RDS and EC2 instances.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    py_modules=["aws_ssh_tunnel"],
    install_requires=[
        "boto3",
        "click",
    ],
    entry_points={
        "console_scripts": [
            "aws-ssh-tunnel=aws_ssh_tunnel:main",
        ],
    },
)
