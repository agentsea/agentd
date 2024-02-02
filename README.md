# agentd

A daemon that makes a desktop OS accessible to AI agents

## Install

Agentd is currently only tested on Ubuntu 22.04 cloud image.

We recommend using one of our base vms which is already configured.

```bash
wget https://storage.googleapis.com/agentsea-vms/ubuntu_2204.qcow2
```

If you want to install on a fresh Ubuntu VM, use the a [cloud images base](https://cloud-images.ubuntu.com/jammy/current/) qcow2 image.

```bash
curl -sSL https://raw.githubusercontent.com/agentsea/agentd/main/remote_install.sh | sudo bash
```

We also provide a cloud-init config in [user-data.tpl.yaml](user-data.tpl.yaml)

To run from this repo

```bash
make run-jammy
```
