packer {
  required_plugins {
    googlecompute = {
      source  = "github.com/hashicorp/googlecompute"
      version = "~> 1"
    }
  }
}

packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = "~> 1"
    }
  }
}
variable "build_qemu" {
  type    = bool
  default = true
}

variable "build_ec2" {
  type    = bool
  default = true
}

variable "build_gce" {
  type    = bool
  default = true
}

variable "gcp_project_id" {
  type    = string
  default = "your-gcp-project-id"
}

variable "aws_region" {
  type    = string
  default = "your-aws-region"
}

variable "output_directory" {
  type    = string
  default = "output-ubuntu"
}

variable "cpu" {
  type    = string
  default = "2"
}

variable "disk_size" {
  type    = string
  default = "40000"
}

variable "headless" {
  type    = string
  default = "true"
}

variable "iso_checksum" {
  type    = string
  default = "1718f177dde4c461148ab7dcbdcf2f410c1f5daa694567f6a8bbb239d864b525"
}

variable "iso_url" {
  type    = string
  default = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
}

variable "name" {
  type    = string
  default = "jammy"
}

variable "ram" {
  type    = string
  default = "2048"
}

variable "ssh_password" {
  type    = string
  default = "ubuntu"
}

variable "ssh_username" {
  type    = string
  default = "ubuntu"
}

variable "version" {
  type    = string
  default = ""
}

variable "format" {
  type    = string
  default = "qcow2"
}

source "qemu" "jammy" {
  # accelerator      = "kvm"
  boot_command     = []
  disk_compression = true
  disk_interface   = "virtio"
  disk_image       = true
  disk_size        = var.disk_size
  format           = var.format
  headless         = var.headless
  iso_checksum     = var.iso_checksum
  iso_url          = var.iso_url
  net_device       = "virtio-net"
  output_directory = "${var.output_directory}"
  qemuargs = [
    ["-m", "${var.ram}M"],
    ["-smp", "${var.cpu}"],
    ["-cdrom", "cidata_root.iso"]
  ]
  communicator           = "ssh"
  shutdown_command       = "echo '${var.ssh_password}' | sudo -S shutdown -P now"
  ssh_password           = var.ssh_password
  ssh_username           = var.ssh_username
  ssh_timeout            = "10m"
}

source "amazon-ebs" "jammy" {
  ami_name      = "agentd-ubuntu-22.04-${formatdate("YYYYMMDDHHmmss", timestamp())}"
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
  ssh_username  = "ubuntu"
}

source "googlecompute" "ubuntu" {
  project_id = var.gcp_project_id
  source_image_family = "ubuntu-2204-lts"
  zone        = "us-central1-a"
  ssh_username = "ubuntu"
  image_name  = "agentd-ubuntu-22-04-${formatdate("YYYYMMDDHHmmss", timestamp())}"
}

build {
  // dynamic "source" {
  //   for_each = var.build_qemu ? ["source.qemu.jammy"] : []
  //   content {
  //     source = source.value
  //   }
  // }

  // dynamic "source" {
  //   for_each = var.build_ec2 ? ["source.amazon-ebs.jammy"] : []
  //   content {
  //     source = source.value
  //   }
  // }

  // dynamic "source" {
  //   for_each = var.build_gce ? ["source.googlecompute.ubuntu"] : []
  //   content {
  //     source = source.value
  //   }
  // }
  sources = [
    "source.qemu.jammy",
    "source.amazon-ebs.jammy",
    "source.googlecompute.ubuntu",
  ]


  provisioner "shell" {
    inline = [
      # Run install script
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
  }
  // post-processor "amazon-ami" {
  //   region = var.aws_region
  //   ami_users = ["all"]
  //   only = ["source.amazon-ebs.jammy"]
  // }

  // post-processor "shell-local" {
  //   inline = [
  //     "gcloud compute images add-iam-policy-binding ${build.ImageName} --member='allAuthenticatedUsers' --role='roles/compute.imageUser'",
  //   ]
  //   only = ["source.googlecompute.ubuntu"]
  // }

  // post-processor "shell-local" {
  //   only = ["source.qemu.jammy"]
  //   inline = [
  //     "echo \"copying artifacts to local latest directory...\"",
  //     "mkdir -p \"${BASE_DIR}/latest\"",
  //     "cp \"${OUTPUT_DIRECTORY}/packer-jammy\" \"${BASE_DIR}/latest/jammy.qcow2\"",
  //     "echo 'copying artifacts to GCS...'",
  //     "TIMESTAMP=$(date +%Y%m%d%H%M%S)",
  //     "OUTPUT_DIR='output-ubuntu'",
  //     // Commands for copying artifacts to GCS commented out for clarity
  //     "gsutil cp \"gs://agentsea-vms/jammy/latest/agentd-jammy.qcow2\" \"gs://agentsea-vms/jammy/${TIMESTAMP}/agentd-jammy.qcow2\"",
  //     "gsutil acl ch -u AllUsers:R \"gs://agentsea-vms/jammy/${TIMESTAMP}/agentd-jammy.qcow2\"",
  //   ]
  // }
}
