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
  default = "ab7be4d3c42143ece5da5ac3773c27e1d30940d306523b776dd2e4a488fbc28a"
}

variable "iso_url" {
  type    = string
  default = "https://cloud-images.ubuntu.com/jammy/20240131/jammy-server-cloudimg-amd64.img"
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
  output_directory = "artifacts/qemu/${var.name}${var.version}"
  qemuargs = [
    ["-m", "${var.ram}M"],
    ["-smp", "${var.cpu}"],
    ["-cdrom", "cidata.iso"]
  ]
  communicator           = "ssh"
  shutdown_command       = "echo '${var.ssh_password}' | sudo -S shutdown -P now"
  ssh_password           = var.ssh_password
  ssh_username           = var.ssh_username
  ssh_timeout            = "10m"
}

provisioner "file" {
  source      = "install_desktop.sh"
  destination = "/tmp/desktop.sh"
}

build {
  sources = [
    "source.qemu.jammy",
  ]

  provisioner "shell" {
    script = "/tmp/desktop.sh"
  }
}
