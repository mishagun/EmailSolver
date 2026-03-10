#!/usr/bin/env bash
# One-time EC2 instance setup for EmailSolver
# Run this after SSH-ing into a fresh Amazon Linux 2023 instance:
#   ssh -i your-key.pem ec2-user@<elastic-ip>
#   bash ec2-setup.sh
set -euo pipefail

echo "=== EmailSolver EC2 Setup ==="

# Update system
echo "[1/6] Updating system..."
sudo dnf update -y

# Install Docker
echo "[2/6] Installing Docker..."
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

# Install Docker Compose plugin
echo "[3/6] Installing Docker Compose..."
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Create app directory
echo "[4/6] Setting up app directory..."
sudo mkdir -p /opt/emailsolver
sudo chown ec2-user:ec2-user /opt/emailsolver

# Clone repo
echo "[5/6] Cloning repository..."
git clone https://github.com/YOUR_USERNAME/EmailSolver.git /opt/emailsolver

# Systemd service for auto-start on boot
echo "[6/6] Creating systemd service..."
sudo tee /etc/systemd/system/emailsolver.service > /dev/null <<'EOF'
[Unit]
Description=EmailSolver Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/emailsolver
ExecStart=/usr/local/lib/docker/cli-plugins/docker-compose up -d
ExecStop=/usr/local/lib/docker/cli-plugins/docker-compose down
User=ec2-user

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable emailsolver

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Log out and back in (for docker group to take effect):"
echo "     exit"
echo "     ssh -i your-key.pem ec2-user@<elastic-ip>"
echo ""
echo "  2. Create your .env file:"
echo "     cd /opt/emailsolver"
echo "     cp .env.example .env"
echo "     nano .env   # fill in your secrets"
echo ""
echo "  3. Start the app:"
echo "     cd /opt/emailsolver"
echo "     docker compose up -d"
echo ""
echo "  4. Check status:"
echo "     docker compose ps"
echo "     docker compose logs -f"
