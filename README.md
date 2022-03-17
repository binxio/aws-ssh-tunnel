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
Clone the project:

```
git clone https://github.com/binxio/aws-ssh-tunnel.git
```
Install dependencies and set PATH variables:
```
python3 -m pip install .
```
That's it!

## Usage

*Configuration*

Set up your local config with `aws-ssh-tunnel config`.
You are prompted to fill in the following details:

`aws_region`: the aws region in which your instances are located.

`aws_profile`: the aws profile to use.

`instance_user`: the user on the AWS target instance or jump server to authenticate the ssh session. For AWS AMIs, the default user is `ec2-user`. 

`instance_tag`: the identifying tag of the target instance or jump server. If multiple instances are identified, a random one will be chosen.

*CLI*

Run the CLI with `aws-ssh-tunnel run --port <port to forward> (default: 80)  --remote_host <remote host to establish tunnel to> (default: localhost)`. 
The CLI will automatically detect the jump server using the tag that is provided in the configuration.






