# Local Setup (Dev)

## Prereqs
- Ubuntu 22.04 (or macOS), Python 3.10+, Postgres 14+
- Google Cloud project with OAuth client (Web App)

## Steps
```bash
python3 -m venv venv && source venv/bin/activate
pip install django psycopg2-binary social-auth-app-django python-dotenv gunicorn
cp .env.example .env
# edit .env with DB + Google OAuth creds
```

### Database
```bash
sudo -u postgres psql <<'SQL'
CREATE USER result_portal_user WITH PASSWORD 'Strong_DB_Pass_ChangeMe';
CREATE DATABASE result_portal OWNER result_portal_user;
GRANT ALL PRIVILEGES ON DATABASE result_portal TO result_portal_user;
SQL
```

### Django
```bash
cd server
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

### Google OAuth (summary)
- Authorized JS origins: `https://results.pmc.edu.pk` (and http for dev)
- Redirect URI: `https://results.pmc.edu.pk/oauth/complete/google-oauth2/`
- Put client ID/secret in `.env`.

### CSS Framework
The project uses Tailwind CSS for styling, loaded via CDN in the base template. This provides:
- Utility-first CSS classes for rapid UI development
- Consistent design system with the slate color palette
- Responsive design utilities
- No build process required

If you prefer to host Tailwind locally or use a different version, you can replace the CDN link in `server/templates/base.html`.
