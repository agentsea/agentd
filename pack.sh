#!/bin/bash

# Default builder flags
BUILD_QEMU=${BUILD_QEMU:-true}
BUILD_EC2=${BUILD_EC2:-true}
BUILD_GCE=${BUILD_GCE:-true}

# Parse command-line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --no-qemu) BUILD_QEMU=false ;;
        --no-ec2) BUILD_EC2=false ;;
        --no-gce) BUILD_GCE=false ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

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
mkdir -p "${BASE_DIR}"

# Run Packer with the current GCP project ID, AWS region, generated timestamp for version, and builder flags
PACKER_LOG=1 packer build \
  -var 'gcp_project_id='"$GCP_PROJECT_ID" \
  -var 'aws_region='"$AWS_REGION" \
  -var 'version='"$TIMESTAMP" \
  -var "output_directory=${OUTPUT_DIRECTORY}" \
  -var 'build_qemu='"$BUILD_QEMU" \
  -var 'build_ec2='"$BUILD_EC2" \
  -var 'build_gce='"$BUILD_GCE" \
  base.pkr.hcl
