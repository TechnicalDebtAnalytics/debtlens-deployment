# DebtLens Deployment & Orchestration

This repository orchestrates the production multi-container deployment for the DebtLens platform on an AWS EC2 VM using **Docker Compose** and container images published via **GitHub Container Registry (GHCR)**.

---

## 🏛️ Architecture & Services

| Service | Technology | Port (Host:Container) | Description |
| :--- | :--- | :--- | :--- |
| **`debtlens-frontend`** | React + Vite + Nginx | `80:80` | Frontend dashboard & UI |
| **`debtlens-main-backend`** | Spring Boot (Java 17) | `8080:8080` | Core API, Auth0, DB persistence & Job coordination |
| **`debtlens-analysis-service`** | Spring Boot (Java 17) | `8082:8082` | AST parsing, code metrics extraction & analysis |
| **`debtlens-ml-service`** | FastAPI (Python 3.11) | `8000:8000` | Machine Learning inference (SATD & Bug prediction) |

All 4 services communicate over an isolated Docker bridge network: `debtlens-network`.

---

## 🚀 CI/CD & Automated Image Publishing

Every push to `main` (or designated development branches) automatically runs unit tests and builds multi-architecture Docker images pushed to GHCR:
- `ghcr.io/<your-github-username>/debtlens-frontend:latest`
- `ghcr.io/<your-github-username>/debtlens-main-backend:latest`
- `ghcr.io/<your-github-username>/debtlens-analysis-service:latest`
- `ghcr.io/<your-github-username>/debtlens-ml-service:latest`

---

## 🛠️ AWS EC2 Initial Setup & Deployment Guide

### Step 1: Install Docker & Docker Compose on AWS EC2 (Ubuntu)

```bash
# Update package lists
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine and Docker Compose plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow running docker without sudo
sudo usermod -aG docker $USER
newgrp docker
```

---

### Step 2: Log in to GitHub Container Registry (GHCR)

To pull private or organization images from GHCR on the EC2 instance:

```bash
# Create a GitHub Personal Access Token (Classic) with 'read:packages' permission
# Then log in:
echo "<YOUR_GITHUB_PAT_TOKEN>" | docker login ghcr.io -u <YOUR_GITHUB_USERNAME> --password-stdin
```

---

### Step 3: Clone & Configure Deployment Repository

```bash
# Clone the deployment repository onto EC2
git clone https://github.com/<YOUR_GITHUB_USERNAME>/debtlens-deployment.git
cd debtlens-deployment

# Copy example configuration to .env
cp .env.example .env

# Edit .env with your actual secrets/credentials
nano .env
```

---

### Step 4: Deploy / Update Containers

To pull the latest images and start all 4 services:

```bash
# Make deploy script executable
chmod +x deploy.sh

# Run automated deployment
./deploy.sh
```

Or manually:

```bash
docker compose pull
docker compose up -d
```

---

## 🔍 Useful Management Commands

```bash
# View running status
docker compose ps

# View real-time logs across all services
docker compose logs -f

# View logs for a specific service
docker compose logs -f main-backend
docker compose logs -f ml-service
docker compose logs -f analysis-service
docker compose logs -f frontend

# Restart a specific service
docker compose restart main-backend

# Stop all services
docker compose down
```
