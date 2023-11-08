#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
A CLI used to set up port forwarding sessions with public and private AWS instances that support SSH,
such as EC2 and RDS. This is done by piping stdin and stdout through a secured AWS SSM Session Manager session,
removing the need to publicly expose bastion servers.
Supports SSH tunnels with instances in both public and private subnets,
including instances that can only be accessed from within a designated VPC or security group.
"""

import os
import random
import socket
import subprocess
import sys
from configparser import ConfigParser
from typing import Any, Callable, Dict, Optional

import boto3
import click

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
DEFAULT_CFG_FILE = os.path.join(__location__, "aws_ssh_tunnel.cfg")
RUNNING_STATE_CODE = 16
cfg = ConfigParser()


def common_options(function: Callable) -> Callable:
    function = click.option(
        "--tag",
        "-t",
        type=str,
        help="tag (format: KEY=VALUE) of the (jump) instance that will be used to set up the SSH (tunneling) session."
        " If tunneling to RDS or other services which only allow internal vpc traffic,"
        " pass the tag of a dedicated jump instance. Omit to use the tag environment variable"
        " in the local configuration file.",
        show_default="ssh_instance_tag environment variable in aws-ssh-tunnel.cfg",
    )(function)

    function = click.option(
        "--profile",
        type=str,
        help="AWS profile to use when using aws-ssh-tunnel",
    )(function)

    function = click.option(
        "--region",
        type=str,
        help="AWS region to use when using aws-ssh-tunnel",
    )(function)

    return function


@click.group()
def main():
    """
    Simple CLI tool that utilizes AWS SSM Session Manager to set up SSH sessions with private AWS EC2 and RDS instances.
    """
    pass


@click.pass_context
def get_aws_session(ctx: click.Context) -> boto3.Session:
    """
    Retrieve an AWS session using the region and profile in the configuration file.
    """
    return boto3.Session(
        region_name=ctx.obj["aws_region"], profile_name=ctx.obj["aws_profile"]
    )


def load_config() -> Dict[str, Any]:
    """
    Load the AWS environment variables from the configuration file as well as any additional parameters.
    """
    aws_config = cfg.read(DEFAULT_CFG_FILE)
    if len(aws_config) > 0 and "aws_environment" in cfg:
        return dict(cfg["aws_environment"])
    else:
        click.echo(
            "Unable to retrieve AWS environment variables,"
            "have you set up the configuration file using 'aws-ssh-tunnel config'?"
        )
        sys.exit(1)


@click.pass_context
def set_target_instance_details(ctx: click.Context, session: boto3.Session):
    """
    Retrieve the id and availability zone of the target instance using the provided tag.
    """
    client = session.client("ec2")
    key, value = ctx.obj["ssh_instance_tag"].split("=")
    custom_filter = [{"Name": f"tag:{key}", "Values": [value]}]
    response = client.describe_instances(Filters=custom_filter)
    if len(response["Reservations"]) > 0:
        available_instances = [
            available_instance
            for reservation in response["Reservations"]
            for available_instance in reservation["Instances"]
            if available_instance["State"]["Code"] == RUNNING_STATE_CODE
        ]
        random_instance = random.choice(available_instances)
        ssh_instance_id = random_instance["InstanceId"]
        ssh_instance_az = random_instance["Placement"]["AvailabilityZone"]
        click.echo(
            f"Found instance with tag {ctx.obj['ssh_instance_tag']}"
            f" and id {ssh_instance_id} on availability zone {ssh_instance_az}..."
        )
        ctx.obj["ssh_instance_id"] = ssh_instance_id
        ctx.obj["ssh_instance_az"] = ssh_instance_az
    else:
        click.echo(
            f"No instances found with tag {ctx.obj['ssh_instance_tag']} and profile {ctx.obj['aws_profile']}"
            f" in region {ctx.obj['aws_region']}, exiting..."
        )
        sys.exit(1)


def get_port(requested_port: int) -> int:
    s = socket.socket()
    try:
        s.bind(("", int(requested_port)))
        port = s.getsockname()[1]

        return port

    except socket.error:
        click.echo(f"Unable to bind to local port '{requested_port}'. Is it in use?")
        exit(1)

    finally:
        s.close()


def execute_ssm_command(cmd: str):
    ssh_proc = subprocess.Popen(
        cmd,
        shell=True,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = ssh_proc.communicate()
        if stderr:
            print(str(stderr))
    except KeyboardInterrupt:
        ssh_proc.terminate()
        click.echo("\nClosing application...")
        sys.exit(0)


@click.pass_context
def start_tunnel(ctx: click.Context, local_port: int):
    """
    Start a tunneling session.
    Can be a direct tunnel to the target EC2 instance or a tunnel to a second instance using a jump server.
    """
    click.echo(
        f"Attempting to start tunnel on AWS SSM Session Manager to {ctx.obj['remote_host']}"
        f" using local port {local_port} and remote port {ctx.obj['port']}..."
    )
    params = f'host="{ctx.obj["remote_host"]}",portNumber="{ctx.obj["port"]}",localPortNumber="{local_port}"'
    cmd = f"aws ssm start-session \
         --target {ctx.obj['ssh_instance_id']} \
         --document-name AWS-StartPortForwardingSessionToRemoteHost \
         --parameters {params} \
         --profile {ctx.obj['aws_profile']} \
         --region {ctx.obj['aws_region']}"
    execute_ssm_command(cmd)


@click.pass_context
def start_session(ctx: click.Context):
    """
    Start an ssh session.
    """
    click.echo(
        f"Attempting to start session on AWS SSM Session Manager to {ctx.obj['ssh_instance_id']}..."
    )

    profile_option = (
        "--profile " + ctx.obj["aws_profile"]
        if ctx.obj["aws_profile"] is not None
        else ""
    )
    region_option = (
        "--region " + ctx.obj["aws_region"] if ctx.obj["aws_region"] is not None else ""
    )

    cmd = f"aws ssm start-session \
         --target {ctx.obj['ssh_instance_id']} \
            {profile_option} \
            {region_option}"
    execute_ssm_command(cmd)


@click.pass_context
def initialize_environment(
    ctx: click.Context,
    tag: Optional[str] = None,
    profile: Optional[str] = None,
    remote_host: Optional[str] = None,
    port: Optional[int] = None,
    region: Optional[str] = None,
):
    """Initializes the ctx object for the CLI. Config variables are overwritten if args are provided.
    aws_profile and aws_region can also stay None if AWS environment variables are set
    """
    ctx.obj = {
        "aws_profile": profile,
        "aws_region": region,
        "ssh_instance_tag": tag,
        "remote_host": remote_host,
        "port": port,
    }

    config_dict = load_config()
    for key, value in config_dict.items():
        if ctx.obj.get(key) is None:
            ctx.obj.update({key: value})

    session = get_aws_session()
    set_target_instance_details(session)


@main.command()
@common_options
@click.option(
    "--region",
    type=str,
    help="AWS region to use for tunneling session."
)
@click.option(
    "--profile",
    type=str,
    help="AWS profile to assume for tunneling session."
)
def config(region, profile, tag):
    """
    Set AWS configuration.
    """
    cfg.read(DEFAULT_CFG_FILE)
    aws_config = {}

    if len(cfg) > 0 and "aws_environment" in cfg:
        aws_config = dict(cfg["aws_environment"])

    if not region:
        aws_region = click.prompt(
            "AWS region to use for tunneling session",
            default=aws_config.get("aws_region"),
        )
    else:
        aws_region = region

    if not profile:
        aws_profile = click.prompt(
            "AWS profile to assume for tunneling session",
            default=aws_config.get("aws_profile"),
        )
    else:
        aws_profile = profile

    if not tag:
        tag = click.prompt(
            "Tag used to identify the (jump) instance that will be used to set up the SSH session",
            default=aws_config.get("ssh_instance_tag"),
        )

    aws_config = {
        **aws_config,
        **{
            "aws_region": aws_region.lower(),
            "aws_profile": aws_profile.lower(),
            "ssh_instance_tag": tag.lower(),
        },
    }

    cfg["aws_environment"] = aws_config

    with open(DEFAULT_CFG_FILE, "w", encoding="utf-8") as config_file:
        cfg.write(config_file)


@main.command()
@common_options
@click.option(
    "-r",
    "--remote-host",
    type=str,
    help="Remote host endpoint to tunnel to.",
    default="localhost",
    show_default=True,
)
@click.option(
    "--port",
    "-p",
    type=str,
    help="The port on the remote host to forward traffic to.",
    default=22,
    show_default=True,
)
@click.option(
    "--local-port",
    "-l",
    type=str,
    help="The port on the local host to route traffic to. If not provided it takes the value of the remote port. "
    "Provide 0 to choose a random port.",
)
def start_forwarding_session(
    remote_host: str,
    port: int,
    tag: Optional[str] = None,
    local_port: Optional[int] = None,
    profile: Optional[str] = None,
    region: Optional[str] = None,
):
    """
    Start a port forwarding session.

    Example:

    aws-ssh-tunnel start-forwarding-session \n
        --remote-host mydb.123456789012.eu-west-1.rds.amazonaws.com \n
        --port 5432 \n
        --local-port 5432 \n
        --tag application=jump_server \n
    """
    try:
        initialize_environment(
            tag=tag, profile=profile, remote_host=remote_host, port=port, region=region
        )
        if not local_port:
            local_port = port

        _local_port = get_port(local_port)
        start_tunnel(_local_port)
    except Exception as error:
        click.echo(
            f"Something went wrong when starting the port forwarding session: {error}"
        )


@main.command()
@common_options
def start_ssh_session(
    tag: Optional[str] = None,
    profile: Optional[str] = None,
    region: Optional[str] = None,
):
    """
    Start an SSH session.

    Example:

    aws-ssh-tunnel start-ssh-session \n
        -t application=jump_server \n
    """
    try:
        initialize_environment(tag=tag, profile=profile, region=region)
        start_session()

    except Exception as error:
        click.echo(f"Something went wrong when starting the SSH session: {error}")


if __name__ == "__main__":
    main()
