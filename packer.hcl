variable "ssh_public_key_path" {
  description = "Path to the SSH public key"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

locals {
  ssh_public_key_content = file(var.ssh_public_key_path)
}

source "qemu" "ubuntu" {
  accelerator     = "kvm"
  disk_image      = true
  disk_size       = "10240" # Disk size in MB, adjust as needed
  format          = "qcow2"
  http_directory  = "meta"
  http_port_min   = 8060
  http_port_max   = 8060
  iso_url         = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  iso_checksum    = "auto"
  ssh_username    = "agentsea"
//   ssh_keypair_name    = "your-keypair-name" # Adjust as needed, if you're using key pairs managed by a cloud provider
  ssh_private_key_file = var.ssh_public_key_path # Ensure this path points to the corresponding private key
  output_directory    = "output-ubuntu"
  vm_name         = "jammy"
}

build {
  sources = ["source.qemu.ubuntu"]

  provisioner "file" {
    content     = templatefile("${path.root}/user-data.tpl", { ssh_public_key = local.ssh_public_key_content })
    destination = "/tmp/user-data"
  }

  provisioner "shell" {
    inline = [
      "sudo mkdir -p /var/lib/cloud/seed/nocloud",
      "sudo mv /tmp/user-data /var/lib/cloud/seed/nocloud/"
    ]
  }

  provisioner "shell" {
    inline = [
      "echo 'cloud-init status --wait' | at now + 1 minute"
    ]
  }
}
