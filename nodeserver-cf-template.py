"""Generating CloudFormation template."""
from ipaddress import ip_network

from ipify import get_ip

from troposphere import (
    Base64,
    ec2,
    GetAtt,
    Join,
    Output,
    Parameter,
    Ref,
    Template,
)

from troposphere.iam import ( 
    InstanceProfile, 
    PolicyType as IAMPolicy, 
    Role,  
) 
 
from awacs.aws import ( 
    Action, 
    Allow, 
    Policy, 
    Principal, 
    Statement, 
) 
 
from awacs.sts import AssumeRole 

ApplicationName = "nodeserver"
ApplicationPort = "3000"

GithubAccount = "EffectiveDevOpsWithAWS"
GithubAnsibleURL = "https://github.com/{}/Ansible".format("simonliu9")

AnsiblePullCmd = \
    "/usr/local/bin/ansible-pull -U {} {}.yml -i localhost".format( 
        GithubAnsibleURL, 
        ApplicationName 
    ) 


PublicCidrIp = str(ip_network(get_ip()))

t = Template()

t.add_description("Effective DevOps in AWS: HelloWorld web application")

t.add_parameter(Parameter(
    "KeyPair",
    Description="Name of an existing EC2 KeyPair to SSH",
    Type="AWS::EC2::KeyPair::KeyName",
    ConstraintDescription="must be the name of an existing EC2 KeyPair.",
))

t.add_resource(ec2.SecurityGroup(
    "SecurityGroup",
    VpcId="vpc-d9a7fda0",
    GroupDescription="Allow SSH and TCP/{} access".format(ApplicationPort),
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="22",
            ToPort="22",
            CidrIp=PublicCidrIp,
        ),
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort=ApplicationPort,
            ToPort=ApplicationPort,
            CidrIp=PublicCidrIp,
        ),
    ],
))

ud = Base64(Join('\n', [
    "#!/bin/bash",
    "yum install --enablerepo=epel -y git",
    "yum install java-1.8.0-openjdk -y",
    "echo 2 |/usr/sbin/alternatives --config java",
    "pip install ansible",
    AnsiblePullCmd,
  
    "echo '*/10 * * * * {}' > /etc/cron.d/ansible-pull".format(AnsiblePullCmd)
]))

t.add_resource(Role(
    "Role",
    AssumeRolePolicyDocument=Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Action=[AssumeRole],
                Principal=Principal("Service", ["ec2.amazonaws.com"])
            )
        ]
    )
))

t.add_resource(InstanceProfile( 
    "InstanceProfile", 
    Path="/", 
    Roles=[Ref("Role")] 
)) 

t.add_resource(IAMPolicy( 
    "Policy", 
    PolicyName="AllowS3", 
    PolicyDocument=Policy( 
        Statement=[ 
            Statement( 
                Effect=Allow, 
                Action=[Action("s3", "*")], 
                Resource=["*"]) 
        ] 
    ), 
    Roles=[Ref("Role")] 
)) 

t.add_resource(ec2.Instance(
    "instance",
    ImageId="ami-e251209a",
    InstanceType="t2.micro",
    NetworkInterfaces=[
        ec2.NetworkInterfaceProperty(
	    AssociatePublicIpAddress="true",
	    GroupSet=[Ref("SecurityGroup")],
	    SubnetId="subnet-72379639",
            DeviceIndex="0"
        ),
    ],
    KeyName=Ref("KeyPair"),
    IamInstanceProfile=Ref("InstanceProfile"),
    UserData=ud,
))

t.add_output(Output(
    "InstancePublicIp",
    Description="Public IP of our instance.",
    Value=GetAtt("instance", "PublicIp"),
))

t.add_output(Output(
    "WebUrl",
    Description="Application endpoint",
    Value=Join("", [
        "http://", GetAtt("instance", "PublicDnsName"),
        ":", ApplicationPort
    ]),
))

print t.to_json()
