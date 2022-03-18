# aws-ssh-tunnel
`aws-ssh-tunnel` is a CLI tool used to set up port forwarding sessions with public and private AWS instances that support SSH, such as EC2 and RDS.
This is done by piping `stdin` and `stdout` through a secured AWS SSM Session Manager session, removing the need to publicly expose bastion servers.

Supports SSH tunnels with instances in both public and private subnets, including instances that can only be accessed from within a designated VPC or security group.

## How it works
```
                    +-------------------------+                                                                                                                                   
                    |AWS VPC                  |                                                                                                                                   
                    |+-----------------------+|                                                                                                                                   
     6. establish   ||private subnet         || 5. SSH request verified by                                                                                                        
        tunnel with || +-----+      +-----+  ||    jump server using public key                                                                                                   
        remote RDS  || | RDS +------| EC2 |------------------------------------+                                                                                                  
        instance    || |     |      |     |------------------------+           |                                                                                                  
                    || +-----+      +-----+  || 3. Session Manager |           |                                                                                                  
                    |+-----------------|-----+|    connects to EC2 |           |                                                                                                  
                    +------------------|------+                    |           |                                                                                                  
                       +--------------------+                +-----------------------+                                                                                            
                       |EC2 Instance Connect|                |AWS SSM Session Manager|                                                                                            
                       +----------|---------+                +-----------------------+                                                                                            
                                  |                                |           |                                                                                                  
                                  |     2. establish session       |           |                                                                                                  
 1. generate  public/private  +------+  with SSM Session Manager   |           |                                                                                                  
    keypair  and send public  | USER |-----------------------------+           |                                                                                                  
    key to jump server using  |      |-----------------------------------------+                                                                                                  
    EC2 Instance Connect API  +------+  4. proxy SSH tunnel to AWS SSM session manager
```

## Installation
Directly install with `pipx` or clone locally.

*pipx*
```
pipx install aws-ssh-tunnel
```
*git clone*
```
git clone https://github.com/binxio/aws-ssh-tunnel.git
python3 -m pip install .
```

## Usage

*config*

Set up your local config with `aws-ssh-tunnel config`.
You are prompted to fill in the following details:
```
aws_region: the aws region in which your instances are located.

aws_profile: the aws profile to use. Should have the necessary IAM permissions to perform ec2-instance-connect:SendSSHPublicKey and ssm:StartSession.


ssh_instance_user: user on the (jump) instance that will be used to set up the SSH session. For AWS AMIs, the default user is `ec2-user`.

ssh_instance_tag: tag used to identify the (jump) instance that will be used to set up the SSH session. If multiple instances are identified, a random one will be chosen.
```
*run*
```
Usage: aws-ssh-tunnel run [OPTIONS]

  Start the CLI.

  Example: aws-ssh-tunnel run --remote_host mydb.123456789012.eu-west-1.rds.amazonaws.com --port 5432 --tag application=jump_server

Options:
  -r, --remote_host TEXT       Remote host endpoint to to jump to. Omit or set
                               to 'localhost' to set up a direct tunnel with
                               the instance defined in '--tag'  [default:
                               localhost]
  -p, --port INTEGER           Listening port on the remote host. The same
                               port will be opened on the local machine.
                               [default: 80]
  -t, --ssh_instance_tag TEXT  tag (format: KEY=VALUE) of the (jump) instance
                               that will be used to set up the SSH session. If
                               tunneling to RDS or other services which only
                               allow internal vpc traffic, pass the tag of a
                               dedicated jump instance. Omit to use the
                               ssh_instance_tag environment variable in the
                               local configuration file.  [default:
                               (ssh_instance_tag environment variable in aws-
                               ssh-tunnel.cfg)]
  --help                       Show this message and exit.
```
## TODO

- Add support for tunnels to Fargate containers by integrating AWS ECS Exec sessions into the CLI. 

