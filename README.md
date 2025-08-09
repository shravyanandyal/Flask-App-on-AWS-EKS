# Flask-App-on-AWS-EKS
# Scalable Microservice Deployment on AWS EKS

This repository contains the code and documentation for deploying a production-ready, scalable, and stateful Flask microservice on Amazon's Elastic Kubernetes Service (EKS). The project fulfills the requirements of a practical DevOps challenge, covering Infrastructure as Code, containerization, Kubernetes orchestration, and autoscaling.

## Architecture Overview

The architecture consists of a Python Flask application that serves three API endpoints. It uses an  Amazon S3 bucket  for persistent file storage and a  PostgreSQL  database for recording metadata. The entire stack is orchestrated by  Kubernetes  on an  Amazon EKS  cluster. An  Application Load Balancer (ALB)  exposes the application to the internet, and a  Horizontal Pod Autoscaler (HPA)  manages scaling based on load.

## Prerequisites

Before you begin, ensure you have the following tools installed and configured on your local machine:

*  AWS CLI:  [Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)  
*  kubectl:  [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)  
*  eksctl:  [Installation Guide](https://www.google.com/search?q=https://eksctl.io/introduction/%23installation)  
*  Docker:  [Installation Guide](https://docs.docker.com/get-docker/)  
*  Helm:  [Installation Guide](https://helm.sh/docs/intro/install/) (Required for the AWS Load Balancer Controller)

## Phase 1: Application Development & Containerization

This phase involves creating the Flask application and packaging it into a portable Docker container image.

###  1.1 Application Code 

The application is structured in an app/ directory.

####  app/main.py 

####  app/requirements.txt 

####  app/Dockerfile 




###  1.2 Build and Push Image to Amazon ECR 

Execute these commands to build the Docker image and push it to a private Amazon ECR repository.

\# Set environment variables  
export AWS\_REGION=ap-south-1  
export AWS\_ACCOUNT\_ID=$(aws sts get-caller-identity \--query Account \--output text)  
export IMAGE\_URI="${AWS\_ACCOUNT\_ID}.dkr.ecr.${AWS\_REGION}.amazonaws.com/flask-app:latest"

\# Create the ECR repository  
aws ecr create-repository \--repository-name flask-app \--region $AWS\_REGION

\# Log in to ECR  
aws ecr get-login-password \--region $AWS\_REGION | docker login \--username AWS \--password-stdin ${AWS\_ACCOUNT\_ID}.dkr.ecr.${AWS\_REGION}.amazonaws.com

\# Build the image  
docker build \-t $IMAGE\_URI ./app

\# Push the image  
docker push $IMAGE\_URI

##  Phase 2: Infrastructure Provisioning on AWS 

This phase uses Infrastructure as Code (IaC) principles to create the necessary AWS resources.

###  2.1 Configure AWS CLI 

First, configure the AWS CLI with an IAM user that has AdministratorAccess.  Do not use the root user. 

aws configure  
\# AWS Access Key ID \[None\]: YOUR\_IAM\_USER\_ACCESS\_KEY  
\# AWS Secret Access Key \[None\]: YOUR\_IAM\_USER\_SECRET\_KEY  
\# Default region name \[None\]: ap-south-1  
\# Default output format \[None\]: json

###  2.2 Create S3 Bucket 

export BUCKET\_NAME="eks-challenge-uploads-${AWS\_ACCOUNT\_ID}"  
aws s3api create-bucket \--bucket $BUCKET\_NAME \--region $AWS\_REGION \--create-bucket-configuration LocationConstraint=$AWS\_REGION

###  2.3 Create EKS Cluster 

This command creates a managed EKS cluster with one t3.medium node to start.

eksctl create cluster \\  
  \--name challenge-cluster \\  
  \--region $AWS\_REGION \\  
  \--version 1.28 \\  
  \--nodegroup-name standard-workers \\  
  \--node-type t3.medium \\  
  \--nodes 1 \\  
  \--nodes-min 1 \\  
  \--nodes-max 2 \\  
  \--managed

###  2.4 Install EKS Add-ons 

Install the necessary add-ons for storage and ingress.

####  EBS CSI Driver 

eksctl create addon \--name aws-ebs-csi-driver \--cluster challenge-cluster \--region $AWS\_REGION \--force

####  AWS Load Balancer Controller 

\# Create IAM OIDC Provider  
eksctl utils associate-iam-oidc-provider \--region=$AWS\_REGION \--cluster=challenge-cluster \--approve

\# Create IAM Policy  
curl \-O https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.5.4/docs/install/iam\_policy.json  
aws iam create-policy \--policy-name AWSLoadBalancerControllerIAMPolicy \--policy-document file://iam\_policy.json

\# Create IAM Service Account for the Controller  
eksctl create iamserviceaccount \\  
  \--cluster=challenge-cluster \\  
  \--namespace=kube-system \\  
  \--name=aws-load-balancer-controller \\  
  \--attach-policy-arn=arn:aws:iam::${AWS\_ACCOUNT\_ID}:policy/AWSLoadBalancerControllerIAMPolicy \\  
  \--region=$AWS\_REGION \\  
  \--override-existing-serviceaccounts \\  
  \--approve

\# Install the controller using Helm  
helm repo add eks https://aws.github.io/eks-charts  
helm repo update eks  
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \\  
  \-n kube-system \\  
  \--set clusterName=challenge-cluster \\  
  \--set serviceAccount.create=false \\  
  \--set serviceAccount.name=aws-load-balancer-controller

###  2.5 Create IAM Role for the Flask App (IRSA) 

This securely grants the Flask application pods permission to access S3.

eksctl create iamserviceaccount \\  
  \--name flask-app-s3-access \\  
  \--namespace default \\  
  \--cluster challenge-cluster \\  
  \--region $AWS\_REGION \\  
  \--attach-policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess \\  
  \--approve

##  Phase 3: Kubernetes Manifests 

These .yaml files define the desired state of the application within the Kubernetes cluster. They should be placed in a k8s/ directory.

####  k8s/postgres-secret.yaml 

####  k8s/postgres-statefulset.yaml 

####  k8s/flask-app.yaml 

####  k8s/hpa.yaml 

##  Phase 4: Scaling the Node Group 

The initial node group used t3.medium instances. To meet the requirement of 4 vCPU / 16 GiB nodes, we scale the node group and upgrade its instance type.

\# First, add a new, more powerful node group  
eksctl create nodegroup \\  
  \--cluster=challenge-cluster \\  
  \--name=large-workers \\  
  \--node-type=t3.xlarge \\  
  \--nodes=1 \\  
  \--nodes-min=1 \\  
  \--nodes-max=4 \\  
  \--region=ap-south-1

\# Then, scale it to the desired number of nodes  
eksctl scale nodegroup \\  
  \--cluster=challenge-cluster \\  
  \--name=large-workers \\  
  \--nodes=3 \\  
  \--region=ap-south-1

\# export OLD\_NODE\_NAME=$(kubectl get nodes \-l eks.amazonaws.com/nodegroup=standard-workers \-o jsonpath='{.items\[0\].metadata.name}')  
\# kubectl drain $OLD\_NODE\_NAME \--ignore-daemonsets \--delete-emptydir-data  
\# eksctl delete nodegroup \--cluster=challenge-cluster \--name=standard-workers \--region=ap-south-1

##  Phase 5: Deployment and Verification 

###  5.1 Apply Manifests 

Deploy the entire application stack with a single command.

kubectl apply \-f k8s/

###  5.2 Verify Deployment 

Check the status of your pods and wait for the Ingress to get a public URL.

\# Watch pods until they are all 'Running'  
kubectl get pods \-w

\# Get the public URL of the Application Load Balancer (may take a few minutes)  
kubectl get ingress

###  5.3 Test Endpoints 

Use the public URL from the Ingress to test the application.

\# Set your URL  
export INGRESS\_URL="\<your-alb-dns-name\>"

\# 1\. Test health probe  
curl http://${INGRESS\_URL}/up

\# 2\. Test file upload  
echo "Hello from EKS\!" \> testfile.txt  
curl \-X POST \-F "file=@testfile.txt" http://${INGRESS\_URL}/upload

\# 3\. Test file download  
curl http://${INGRESS\_URL}/file/testfile.txt

##  Phase 6: Demonstrating Autoscaling 

###  6.1 Load Test Script 

Create a script load\_test.sh to generate traffic.

\#\!/bin/bash  
if \[ \-z "$1" \]; then  
  echo "Usage: $0 \<INGRESS\_URL\>"  
  exit 1  
fi

INGRESS\_URL=$1  
echo "Starting load test on http://${INGRESS\_URL}/up..."

while true; do  
  \# Spawn 10 parallel curl processes  
  for i in {1..10}; do  
    curl \-s \-o /dev/null http://${INGRESS\_URL}/up &  
  done  
  wait  
done

###  6.2 Run the Test 

\# Make the script executable  
chmod \+x load\_test.sh

\# Start the load test  
./load\_test.sh $INGRESS\_URL

###  6.3 Monitor HPA 

In a separate terminal, watch the Horizontal Pod Autoscaler in action.

kubectl get hpa \-w

You will see the REPLICAS count increase from 2 towards 10 as CPU load increases. 
