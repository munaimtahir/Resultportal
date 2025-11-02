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

## Analytics Operations

### Computing Analytics

The Result Portal includes an analytics system that computes statistical aggregates, component-wise metrics, and anomaly detection for exam results.

#### Manual Analytics Computation

To compute analytics for a specific exam:
```bash
cd /srv/result-portal/server
source ../venv/bin/activate
python manage.py compute_analytics --exam EXAM-CODE
```

To compute analytics for all exams:
```bash
python manage.py compute_analytics --all
```

#### Automated Analytics Computation

Analytics should be recomputed after result imports to keep data current. You can schedule this using cron or systemd timers.

**Option 1: Cron (recommended for simplicity)**

Add to the `resultportal` user's crontab (`sudo -u resultportal crontab -e`):
```cron
# Compute analytics daily at 2 AM
0 2 * * * cd /srv/result-portal/server && /srv/result-portal/venv/bin/python manage.py compute_analytics --all >> /srv/result-portal/logs/analytics.log 2>&1
```

**Option 2: Systemd timer**

Create `/etc/systemd/system/result-portal-analytics.service`:
```ini
[Unit]
Description=Result Portal Analytics Computation
After=network.target

[Service]
Type=oneshot
User=resultportal
WorkingDirectory=/srv/result-portal/server
Environment="DJANGO_SETTINGS_MODULE=config.settings"
EnvironmentFile=/srv/result-portal/.env
ExecStart=/srv/result-portal/venv/bin/python manage.py compute_analytics --all
```

Create `/etc/systemd/system/result-portal-analytics.timer`:
```ini
[Unit]
Description=Run Result Portal Analytics Daily
Requires=result-portal-analytics.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start the timer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now result-portal-analytics.timer
```

Check timer status:
```bash
sudo systemctl status result-portal-analytics.timer
sudo systemctl list-timers result-portal-analytics.timer
```

#### Accessing Analytics Dashboard

Analytics are available to staff users at:
- Dashboard: `https://your-domain.com/analytics/dashboard/`
- Exam details: `https://your-domain.com/analytics/exam/<exam_id>/`

The dashboard displays:
- Recent exam aggregates (mean, median, pass rate, grade distribution)
- Component-wise statistics (theory, practical, total)
- Anomaly flags (low pass rates, high variance, low participation)

#### Integration with Result Import Workflow

For optimal automation, consider computing analytics immediately after result imports:

1. Import results using the CSV import interface or management command
2. Run analytics computation for the specific exam
3. Review the analytics dashboard for any anomalies

Example workflow script:
```bash
#!/bin/bash
# import-and-analyze.sh
cd /srv/result-portal/server
source ../venv/bin/activate

# Import results
python manage.py import_results /path/to/results.csv

# Compute analytics for the imported exam
python manage.py compute_analytics --exam EXAM-CODE

echo "Import and analytics computation complete"
```

#### Monitoring and Maintenance

- Analytics computation logs are written to the configured Django logging system
- Check for anomaly flags regularly via the dashboard
- Recompute analytics if result data is corrected or updated
- Analytics data is stored in the database and can be backed up with standard database backup procedures
