# agentd

A daemon that makes a desktop OS accessible to AI agents.

For a higher level interface see [AgentDesk](https://github.com/agentsea/agentdesk)

## Install

Agentd is currently only tested on Ubuntu 22.04 cloud image.

We recommend using one of our base vms which is already configured.

```bash
wget https://storage.googleapis.com/agentsea-vms/jammy/latest/agentd-jammy.qcow2
```

If you want to install on a fresh Ubuntu VM, use the a [cloud images base](https://cloud-images.ubuntu.com/jammy/current/) qcow2 image.

```bash
curl -sSL https://raw.githubusercontent.com/agentsea/agentd/main/remote_install.sh | sudo bash
```

To pack a fresh set of images

```bash
make pack
```

To run from this repo

```bash
make run-jammy
```
