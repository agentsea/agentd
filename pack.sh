#!/bin/bash

# Fetch the current GCP project ID
export GCP_PROJECT_ID=$(gcloud config get-value project)

# Fetch the current AWS region
export AWS_REGION=$(aws configure get region)

# Check if GCP_PROJECT_ID is not empty
if [ -z "$GCP_PROJECT_ID" ]; then
  echo "GCP Project ID could not be found. Ensure you're logged in to gcloud and have a project set."
  exit 1
fi

# Check if AWS_REGION is not empty
if [ -z "$AWS_REGION" ]; then
  echo "AWS Region could not be found. Ensure you're logged in to aws cli and have a default region set."
  exit 1
fi

rm -rf ~/.cache/packer

# Initialize Packer configuration
packer init base.pkr.hcl

# Generate a timestamp
TIMESTAMP=$(date +%Y%m%d%H%M%S)

# Define the base directory for VM outputs
BASE_DIR=".vms/jammy"

# Create a unique output directory with the timestamp
OUTPUT_DIRECTORY="${BASE_DIR}/${TIMESTAMP}"

# Ensure the directory exists
mkdir -p "${BASE_DIRECTORY}"

# Run Packer with the current GCP project ID, AWS region, and the generated timestamp for version
PACKER_LOG=1 packer build \
  -var 'gcp_project_id='"$GCP_PROJECT_ID" \
  -var 'aws_region='"$AWS_REGION" \
  -var 'version='"$TIMESTAMP" \
  -var "output_directory=${OUTPUT_DIRECTORY}" \
  base.pkr.hcl

cp "${OUTPUT_DIRECTORY}/packer-jammy" "${BASE_DIR}/latest/jammy.qcow2"

echo "copying artifacts to GCS..."
gsutil cp "${BASE_DIR}/latest/jammy.qcow2" "gs://agentsea-vms/jammy/latest/agentd-jammy.qcow2"
gsutil acl ch -u AllUsers:R "gs://agentsea-vms/jammy/latest/agentd-jammy.qcow2"
gsutil cp "gs://agentsea-vms/jammy/latest/agentd-jammy.qcow2" "gs://agentsea-vms/jammy/${TIMESTAMP}/agentd-jammy.qcow2"
gsutil acl ch -u AllUsers:R "gs://agentsea-vms/jammy/${TIMESTAMP}/agentd-jammy.qcow2"
