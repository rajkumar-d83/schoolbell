#!/bin/bash
# SchoolBell — one-shot server setup for Ubuntu 22.04 on EC2
# Run as: sudo bash setup_server.sh
set -e

echo "=== [1/7] System update ==="
apt-get update -y && apt-get upgrade -y

echo "=== [2/7] Install dependencies ==="
apt-get install -y python3.12 python3.12-venv python3-pip nginx git ufw certbot python3-certbot-nginx

echo "=== [3/7] Create app user ==="
id -u schoolbell &>/dev/null || useradd -m -s /bin/bash schoolbell

echo "=== [4/7] Clone repo ==="
APP_DIR=/home/schoolbell/app
if [ -d "$APP_DIR" ]; then
  echo "Repo already exists — pulling latest..."
  sudo -u schoolbell git -C "$APP_DIR" pull
else
  sudo -u schoolbell git clone https://github.com/rajkumar-d83/schoolbell.git "$APP_DIR"
fi

echo "=== [5/7] Python virtual environment ==="
sudo -u schoolbell python3.12 -m venv "$APP_DIR/venv"
sudo -u schoolbell "$APP_DIR/venv/bin/pip" install --upgrade pip
sudo -u schoolbell "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "=== [6/7] Folders and permissions ==="
mkdir -p "$APP_DIR/uploads"
mkdir -p "$APP_DIR/logs"
chown -R schoolbell:schoolbell "$APP_DIR"
# Allow nginx (www-data) to read static files and uploads
chmod 755 /home/schoolbell
chmod -R 755 "$APP_DIR/app/static"
chmod -R 755 "$APP_DIR/uploads"

echo "=== [7/7] Firewall ==="
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo ""
echo "======================================================"
echo " Server setup complete!"
echo " Next: copy your .env file, then run deploy_app.sh"
echo "======================================================"
