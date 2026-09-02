#!/usr/bin/env bash
set -e

echo "========================================="
echo "  Deploying DebtLens Microservices Stack"
echo "========================================="

# Ensure .env file exists
if [ ! -f .env ]; then
    echo "[!] .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "[*] Please review .env configuration before proceeding."
fi

# Pull the latest container images from registry
echo "[*] Pulling latest container images..."
docker compose pull

# Start/Recreate containers with zero downtime if possible
echo "[*] Launching containers in detached mode..."
docker compose up -d --remove-orphans

# Clean up dangling images to preserve disk space on EC2
echo "[*] Pruning dangling images..."
docker image prune -f

echo "========================================="
echo "  Deployment Complete! Container Status:"
echo "========================================="
docker compose ps
