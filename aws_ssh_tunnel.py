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
import subprocess
import sys
import boto3
import click
from configparser import ConfigParser

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
DEFAULT_CFG_FILE = os.path.join(__location__, "aws_ssh_tunnel.cfg")
RUNNING_STATE_CODE = 16
cfg = ConfigParser()


@click.group()
def main():
    """
    Simple CLI tool that utilizes AWS SSM Session Manager to start an ssh tunnel to private AWS EC2 or RDS instances.
    """
    pass


@click.pass_context
def get_aws_session(ctx):
    """
    Retrieve an AWS session using the region and profile in the configuration file.
    """
    return boto3.Session(
        region_name=ctx.obj["aws_region"], profile_name=ctx.obj["aws_profile"]
    )


@click.pass_context
def load_config(ctx, remote_host, port, ssh_instance_tag):
    """
    Load the AWS environment variables from the configuration file as well as any additional parameters.
    """
    aws_config = cfg.read(DEFAULT_CFG_FILE)
    if len(aws_config) > 0 and "aws_environment" in cfg:
        ctx.obj = dict(cfg["aws_environment"])
        ctx.obj["port"] = port
        ctx.obj["remote_host"] = remote_host
        if ssh_instance_tag is not None:
            ctx.obj["ssh_instance_tag"] = ssh_instance_tag
    else:
        click.echo(
            "Unable to retrieve AWS environment variables,"
            "have you set up the configuration file using 'aws-ssh-tunnel config'?"
        )
        sys.exit(1)


@click.pass_context
def set_target_instance_details(ctx, session):
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


@click.pass_context
def start_tunnel(ctx):
    """
    Start a tunneling session.
    Can be a direct tunnel to the target EC2 instance or a tunnel to a second instance using a jump server.
    """
    click.echo(
        f"Attempting to start tunnel on AWS SSM Session Manager to {ctx.obj['remote_host']}"
        f" on port {ctx.obj['port']}..."
    )
    params = f'host="{ctx.obj["remote_host"]}",portNumber="{ctx.obj["port"]}",localPortNumber="{ctx.obj["port"]}"'
    cmd = f"aws ssm start-session \
         --target {ctx.obj['ssh_instance_id']} \
         --document-name AWS-StartPortForwardingSessionToRemoteHost \
         --parameters {params} \
         --profile {ctx.obj['aws_profile']} \
         --region {ctx.obj['aws_region']}"
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


@main.command()
def config():
    """
    Load AWS environment variables into the CLI configuration.
    """
    cfg.read(DEFAULT_CFG_FILE)
    aws_config = {}

    if len(cfg) > 0 and "aws_environment" in cfg:
        aws_config = dict(cfg["aws_environment"])

    aws_region = click.prompt(
        "AWS region to use for tunneling session",
        default=aws_config.get("aws_region"),
    )
    aws_profile = click.prompt(
        "AWS profile to assume for tunneling session",
        default=aws_config.get("aws_profile"),
    )
    ssh_instance_tag = click.prompt(
        "Tag used to identify the (jump) instance that will be used to set up the SSH session",
        default=aws_config.get("ssh_instance_tag"),
    )
    aws_config = {
        **aws_config,
        **{
            "aws_region": aws_region,
            "aws_profile": aws_profile,
            "ssh_instance_tag": ssh_instance_tag,
        },
    }

    cfg["aws_environment"] = aws_config

    with open(DEFAULT_CFG_FILE, "w", encoding="utf-8") as config_file:
        cfg.write(config_file)


@main.command()
@click.option(
    "-r",
    "--remote_host",
    type=str,
    help="Remote host endpoint to to jump to."
    " Omit or set to 'localhost' to set up a direct tunnel with the instance defined in '--tag'",
    default="localhost",
    show_default=True,
)
@click.option(
    "--port",
    "-p",
    type=str,
    help="Listening port on the remote host. The same port will be opened on the local machine.",
    default=33333,
    show_default=True,
)
@click.option(
    "--ssh_instance_tag",
    "-t",
    type=str,
    help="tag (format: KEY=VALUE) of the (jump) instance that will be used to set up the SSH session."
    " If tunneling to RDS or other services which only allow internal vpc traffic,"
    " pass the tag of a dedicated jump instance. Omit to use the ssh_instance_tag environment variable"
    " in the local configuration file.",
    show_default="ssh_instance_tag environment variable in aws-ssh-tunnel.cfg",
)
def run(remote_host, port, ssh_instance_tag):
    """
    Start the CLI.

    Example:

    aws-ssh-tunnel run \n
        --remote_host mydb.123456789012.eu-west-1.rds.amazonaws.com \n
        --port 5432 \n
        --ssh_instance_tag application=jump_server \n
    """
    try:
        load_config(remote_host, port, ssh_instance_tag)
        session = get_aws_session()
        set_target_instance_details(session)
        start_tunnel()
    except Exception as error:
        click.echo(f"Something went wrong while executing the CLI: {error}")


if __name__ == "__main__":
    main()
