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
git clone placeholder
```
Install dependencies:
```
pip install .
```
That's it!

## Usage
*Configuration*

Set up your local config with `aws-ssh-tunnel config`.
Fill in the prompted aws region, aws profile, target instance tag, and instance user that is used to establish an ssh tunnel on the target instance or jump server.

*CLI*
Run the CLI with `aws-ssh-tunnel run --port <port to forward> (default: 80)  [--remote_host <remote host to establish tunnel to> (default: localhost)`. 
The CLI will automatically detect the jump server using the tag that is provided in the configuration.






