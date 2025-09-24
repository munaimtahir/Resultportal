# Deployment (Ubuntu 22.04)

## Install system packages
```bash
sudo apt update && sudo apt install -y python3-venv python3-dev build-essential   libpq-dev postgresql postgresql-contrib nginx certbot python3-certbot-nginx
```

## App user & directories
```bash
sudo useradd -m -d /srv/result-portal -s /bin/bash resultportal || true
sudo mkdir -p /srv/result-portal && sudo chown -R resultportal: /srv/result-portal
```

## App setup
```bash
sudo -iu resultportal bash <<'BASH'
python3 -m venv venv
source venv/bin/activate
pip install django psycopg2-binary social-auth-app-django python-dotenv gunicorn
mkdir -p server
# (copy project files to /srv/result-portal)
BASH
```

## Gunicorn systemd
Create `/etc/systemd/system/result-portal.service`:
```
[Unit]
Description=Result Portal Gunicorn
After=network.target

[Service]
User=resultportal
WorkingDirectory=/srv/result-portal/server
Environment="DJANGO_SETTINGS_MODULE=config.settings"
EnvironmentFile=/srv/result-portal/.env
ExecStart=/srv/result-portal/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8003 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now result-portal
```

## Nginx
`/etc/nginx/sites-available/result-portal`:
```
server {
    listen 80;
    server_name results.pmc.edu.pk;

    location /static/ {
        alias /srv/result-portal/server/static/;
    }
    location / {
        proxy_pass http://127.0.0.1:8003;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/result-portal /etc/nginx/sites-enabled/result-portal
sudo nginx -t && sudo systemctl reload nginx
```

## HTTPS
```bash
sudo certbot --nginx -d results.pmc.edu.pk
```

## Collect static
```bash
source /srv/result-portal/venv/bin/activate
cd /srv/result-portal/server
python manage.py collectstatic --noinput
```
