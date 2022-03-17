from setuptools import setup

setup(
    name="aws-ssh-tunnel",
    version="0.1.0",
    py_modules=["aws_ssh_tunnel"],
    install_requires=[
        "boto3",
        "paramiko",
        "sshtunnel",
        "click",
    ],
    entry_points={
        "console_scripts": [
            "aws-ssh-tunnel=aws_ssh_tunnel:main",
        ],
    },
)
