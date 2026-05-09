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

echo "=== Fix static file permissions ==="
chmod 755 /home/schoolbell
chmod -R 755 "$APP_DIR/app/static"
chmod -R 755 "$APP_DIR/uploads"

echo "=== Copy service config ==="
cp "$APP_DIR/deploy/schoolbell.service" /etc/systemd/system/schoolbell.service

# Only copy nginx config if not already managed by certbot (avoid overwriting SSL setup)
if grep -q "ssl_certificate" /etc/nginx/sites-available/schoolbell 2>/dev/null; then
  echo "    nginx config has SSL — skipping overwrite; patching timeouts/limits in place"
  sudo sed -i 's/proxy_read_timeout [0-9]*s/proxy_read_timeout 300s/' /etc/nginx/sites-available/schoolbell
  sudo sed -i 's/client_max_body_size [0-9]*M/client_max_body_size 20M/' /etc/nginx/sites-available/schoolbell
else
  cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/schoolbell
fi

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
