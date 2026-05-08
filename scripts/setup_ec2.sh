#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y ca-certificates curl git make python3 python3-pip python3-venv openjdk-17-jdk

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"

echo "EC2 base setup complete."
echo "Log out and back in for docker group membership to apply."
echo "Then clone the repository and run:"
echo "  python3 -m venv .venv"
echo "  source .venv/bin/activate"
echo "  make install"
echo "  make smoke"

