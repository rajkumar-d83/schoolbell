#!/bin/bash
# SchoolBell — deploy / redeploy the app
# Run as: sudo bash deploy_app.sh
set -e

APP_DIR=/home/schoolbell/app

echo "=== Pull latest code ==="
sudo -u schoolbell git -C "$APP_DIR" pull

echo "=== Install/update Python packages ==="
sudo -u schoolbell "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "=== Initialise / migrate database ==="
cd "$APP_DIR"
sudo -u schoolbell "$APP_DIR/venv/bin/python" init_db.py

echo "=== Copy service and nginx config ==="
cp "$APP_DIR/deploy/schoolbell.service" /etc/systemd/system/schoolbell.service
cp "$APP_DIR/deploy/nginx.conf"         /etc/nginx/sites-available/schoolbell

ln -sf /etc/nginx/sites-available/schoolbell /etc/nginx/sites-enabled/schoolbell
rm -f /etc/nginx/sites-enabled/default

echo "=== Restart services ==="
systemctl daemon-reload
systemctl enable schoolbell
systemctl restart schoolbell
nginx -t && systemctl reload nginx

echo ""
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "<your-ec2-ip>")
echo "======================================================"
echo " SchoolBell is LIVE at: http://$PUBLIC_IP"
echo "======================================================"
