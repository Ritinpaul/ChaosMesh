#!/usr/bin/env bash
# ChaosMesh Arena — OCI ARM64 Setup Script (Task 3.6)
# Sets up K3s, Docker, and Ollama on an Oracle Cloud Infrastructure ARM64 instance (e.g. Ampere A1).

set -euo pipefail

echo "==============================================="
echo "⚡ ChaosMesh Arena: OCI ARM64 Node Setup"
echo "==============================================="

# 1. Update and install prerequisites
echo "[1/4] Installing system dependencies..."
sudo apt-get update && sudo apt-get install -y \
    curl git vim tmux htop net-tools apt-transport-https ca-certificates software-properties-common

# 2. Install Docker
echo "[2/4] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "Docker installed. Please log out and back in to use docker without sudo."
else
    echo "Docker already installed."
fi

# 3. Install K3s (Lightweight Kubernetes)
echo "[3/4] Installing K3s..."
if ! command -v k3s &> /dev/null; then
    curl -sfL https://get.k3s.io | sh -
    mkdir -p ~/.kube
    sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
    sudo chown $USER:$USER ~/.kube/config
    echo "K3s installed."
else
    echo "K3s already installed."
fi

# 4. Install Ollama and pull default model
echo "[4/4] Installing Ollama (ARM64 Native)..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
    echo "Ollama installed. Starting service..."
    sudo systemctl enable ollama
    sudo systemctl start ollama
    
    echo "Pulling llama3.1:8b..."
    ollama pull llama3.1:8b
else
    echo "Ollama already installed."
fi

echo "==============================================="
echo "✅ Setup Complete!"
echo "Next steps:"
echo "1. Configure .env with your OpenRouter API key"
echo "2. Run: docker compose up -d"
echo "==============================================="
