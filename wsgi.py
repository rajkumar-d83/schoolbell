import os
from app import create_app
from werkzeug.middleware.proxy_fix import ProxyFix

app = create_app(os.environ.get('FLASK_CONFIG', 'production'))

# Trust nginx's X-Forwarded-Proto so Flask knows requests arrive over HTTPS.
# Without this, SESSION_COOKIE_SECURE blocks the session cookie on HTTP→gunicorn hops.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
