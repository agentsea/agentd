packer {
  required_plugins {
    googlecompute = {
      source  = "github.com/hashicorp/googlecompute"
      version = "~> 1"
    }
  }
}

variable "gcp_project_id" {
  type    = string
  default = "your-gcp-project-id"
}

variable "aws_region" {
  type    = string
  default = "your-aws-region"
}

source "qemu" "ubuntu" {
  accelerator     = "kvm"
  disk_image      = true
  format          = "qcow2"
  iso_url         = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  iso_checksum    = "auto"
  ssh_username    = "ubuntu"
  headless        = true
}

source "amazon-ebs" "ubuntu" {
  ami_name      = "ubuntu-22.04-${formatdate("YYYYMMDDHHmmss", timestamp())}"
  instance_type = "t2.micro"
  region        = var.aws_region
  source_ami_filter {
    filters = {
      name                = "ubuntu/images/*ubuntu-jammy-22.04-amd64-server-*"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    owners      = ["099720109477"] # Ubuntu's owner ID
    most_recent = true
  }
  ssh_username = "ubuntu"
}

source "googlecompute" "ubuntu" {
  project_id = var.gcp_project_id
  source_image_family = "ubuntu-2204-lts"
  zone        = "us-central1-a"
  ssh_username = "ubuntu"
  image_name  = "ubuntu-22-04-${formatdate("YYYYMMDDHHmmss", timestamp())}"
}

build {
  sources = [
    "source.qemu.ubuntu",
    "source.amazon-ebs.ubuntu",
    "source.googlecompute.ubuntu"
  ]

provisioner "shell" {
  inline = [
    # Create agentsea user
    "sudo adduser --disabled-password --gecos '' agentsea",
    "echo 'agentsea:sailor' | sudo chpasswd",
    "echo 'agentsea ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/agentsea",

    # Update and install software
    "sudo apt-get update",
    "curl -sSL https://raw.githubusercontent.com/agentsea/agentd/main/remote_install.sh | sudo bash",

    # Prepare cloud-init to run on next boot for the QEMU image
    "sudo cloud-init clean --logs",
    "sudo truncate -s 0 /etc/machine-id",
    "sudo rm /var/lib/dbus/machine-id",
    "sudo ln -s /etc/machine-id /var/lib/dbus/machine-id",

    # Disable SSH password authentication
    "sudo sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config",
    "sudo sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config",
    "sudo systemctl restart sshd",
  ]
  only = ["source.qemu.ubuntu"]
}
}
