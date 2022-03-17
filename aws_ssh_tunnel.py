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
import sys
from time import sleep

import boto3
import click
import paramiko
from configparser import ConfigParser
from sshtunnel import open_tunnel

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
DEFAULT_CFG_FILE = os.path.join(__location__, "aws_ssh_tunnel.cfg")

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
    click.echo(dict(ctx.obj))
    return boto3.Session(
        region_name=ctx.obj["aws_region"], profile_name=ctx.obj["aws_profile"]
    )


@click.pass_context
def load_config(ctx, remote_host, port):
    """
    Load the AWS environment variables from the configuration file as well as any additional parameters.
    """
    aws_config = cfg.read(DEFAULT_CFG_FILE)
    if len(aws_config) > 0 and "aws_environment" in cfg:
        ctx.obj = dict(cfg["aws_environment"])
        ctx.obj["port"] = port
        ctx.obj["remote_host"] = remote_host
    else:
        click.echo(
            'Unable to locate AWS environment variables, have you run "tunnel config"?'
        )
        sys.exit(1)


def generate_keyset():
    """
    Generates an ephemeral public-private key pair used to authenticate with the target instance.
    """
    print("generating key pair for authentication with target instance...")
    private_key = paramiko.RSAKey.generate(4096)
    public_key = f"{private_key.get_name()} {private_key.get_base64()}"
    return public_key, private_key


@click.pass_context
def prepare_instance_authentication(ctx, session, public_key):
    """
    Sends an ephemeral public key to the target instance used to authenticate the SSH session.
    """
    print("sending public key to target instance...")
    client = session.client("ec2-instance-connect")
    return client.send_ssh_public_key(
        InstanceId=ctx.obj["instance_id"],
        InstanceOSUser=ctx.obj["instance_user"],
        SSHPublicKey=public_key,
        AvailabilityZone=ctx.obj["instance_az"],
    )


@click.pass_context
def set_target_instance_details(ctx, session):
    """
    Retrieve the id and availability zone of the target instance using the provided tag.
    """
    client = session.client("ec2")
    key, value = ctx.obj["instance_tag"].split(":")
    custom_filter = [{"Name": f"tag:{key}", "Values": [value]}]
    response = client.describe_instances(Filters=custom_filter)
    if len(response["Reservations"]) > 0:
        available_instances = response["Reservations"][0]["Instances"]
        random_instance = random.choice(available_instances)
        instance_id = random_instance["InstanceId"]
        instance_az = random_instance["Placement"]["AvailabilityZone"]
        print(
            f"found jumpserver with id {instance_id} on availability zone {instance_az}..."
        )
        ctx.obj["instance_id"] = instance_id
        ctx.obj["instance_az"] = instance_az
    else:
        print(
            f"""
            No instances found with tag {ctx.obj["instance_tag"]}
            and profile {ctx.obj["aws_profile"]}
            in region {ctx.obj["aws_region"]}, exiting...
            """
        )
        sys.exit(1)


@click.pass_context
def start_tunnel(ctx, private_key):
    """
    Start a tunnel session.
    Can be a direct tunnel to the target EC2 instance or a tunnel to a second instance using a jump server.
    """
    print(
        f'starting tunnel on AWS SSM Session Manager to {ctx.obj["remote_host"]} on port {ctx.obj["port"]}...'
    )
    proxy_command = f"""
    aws ssm start-session
        --target {ctx.obj['instance_id']}
        --document-name AWS-StartSSHSession
        --parameters "portNumber=22"
        --region={ctx.obj['aws_region']}
        --profile {ctx.obj['aws_profile']}
    """
    ssh_proxy = paramiko.ProxyCommand(proxy_command)
    with open_tunnel(
        ssh_address_or_host=ctx.obj["instance_id"],
        ssh_proxy=ssh_proxy,
        ssh_username=ctx.obj["instance_user"],
        ssh_pkey=private_key,
        remote_bind_address=(ctx.obj["remote_host"], ctx.obj["port"]),
        local_bind_address=("0.0.0.0", ctx.obj["port"]),
        # NOTE: host_pkey_directories is left empty.
        # Needed in order to suppress a false positive error when ssh_pkey is loaded as a runtime variable.
        host_pkey_directories=[],
    ) as server:
        print(
            f"tunnel complete, listening on port {server.local_bind_port}"
            " (press ctrl+c to close the connection)..."
        )
        while True:
            try:
                sleep(1)
            except KeyboardInterrupt:
                print("\nclosing connection...")
                break


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
        show_default="default AWS region",
    )
    aws_profile = click.prompt(
        "AWS profile to assume for tunneling session",
        default=aws_config.get("aws_profile"),
    )
    jump_server_user = click.prompt(
        "User on target instance used to establish port forwarding session",
        default=aws_config.get("instance_user"),
    )
    jump_server_tag = click.prompt(
        "Tag used to identify the target instance in AWS",
        default=aws_config.get("instance_tag"),
    )
    aws_config = {
        **aws_config,
        **{
            "aws_region": aws_region,
            "aws_profile": aws_profile,
            "instance_user": jump_server_user,
            "instance_tag": jump_server_tag,
        },
    }

    cfg["aws_environment"] = aws_config

    with open(DEFAULT_CFG_FILE, "w", encoding="utf-8") as config_file:
        cfg.write(config_file)


@main.command()
@click.option(
    "--remote_host",
    "-e",
    type=str,
    help="Remote host to jump to from jump server."
    "Leave empty to directly tunnel to tagged instance",
    default="localhost",
)
@click.option(
    "--port",
    "-p",
    type=int,
    help="Port used to create tunnel. Identical for local and remote host.",
    default=80,
)
def run(remote_host, port):
    """
    Start the CLI.
    """
    try:
        load_config(remote_host, port)
        session = get_aws_session()
        set_target_instance_details(session)
        public_key, private_key = generate_keyset()
        prepare_instance_authentication(session, public_key)
        start_tunnel(private_key)
    except Exception as error:
        print(f"Something went wrong during tunnel initialization: {error}")


if __name__ == "__main__":
    main()
