#cloud-config
chpasswd:
  list: |
    agentsea:sailor
  expire: False
users:
  - name: agentsea
    ssh_authorized_keys:
      - {{ ssh_public_key }}
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: sudo
    shell: /bin/bash
runcmd:
  - growpart /dev/sda 1
  - resize2fs /dev/sda1
  - "curl -sSL https://raw.githubusercontent.com/agentsea/agentd/main/remote_install.sh | sudo bash"
