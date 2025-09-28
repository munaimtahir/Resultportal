# PMC Result Portal

A secure result portal for PMC students to view their examination results through Google Workspace authentication.

## Features

- **Google Workspace SSO**: Login restricted to `@pmc.edu.pk` domain
- **Student Self-Service**: Students can view only their own results
- **CSV Import System**: Bulk import students and results with dry-run preview
- **Admin Management**: Staff can upload, preview, and publish results
- **Audit Trail**: Full logging of all import operations
- **Secure Access**: Strict ownership guards and permission controls

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ (SQLite for development)
- Google Cloud project with OAuth2 credentials

### Installation

1. **Clone and setup environment**:
```bash
git clone <repository-url>
cd Resultportal
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your database and Google OAuth credentials
```

3. **Setup database**:
```bash
cd server
python manage.py migrate
python manage.py createsuperuser
```

4. **Run development server**:
```bash
python manage.py runserver
```

## Usage

### Importing Students

Import student roster from CSV file:

```bash
# Preview changes (dry-run)
python manage.py import_students students.csv --dry-run

# Commit changes to database  
python manage.py import_students students.csv --commit
```

**Required CSV format** (`students.csv`):
```csv
roll_no,first_name,last_name,display_name,official_email
PMC-001,John,Doe,John Doe,john.doe@pmc.edu.pk
PMC-002,Jane,Smith,Jane Smith,jane.smith@pmc.edu.pk
```

Optional columns: `recovery_email`, `batch_code`, `status`

### Importing Results

Import examination results from CSV file:

```bash
# Preview changes (dry-run)
python manage.py import_results results.csv --dry-run

# Commit changes to database
python manage.py import_results results.csv --commit
```

**Required CSV format** (`results.csv`):
```csv
respondent_id,roll_no,name,block,year,subject,written_marks,viva_marks,total_marks,grade,exam_date
resp-1,PMC-001,John Doe,E,2024,Pathology,70,20,90,A,2024-01-15
resp-2,PMC-001,John Doe,E,2024,Anatomy,80,15,95,A+,2024-01-16
```

### Make Commands

Use the Makefile for common operations:

```bash
# Setup development environment
make dev

# Run migrations
make migrate

# Create superuser
make superuser

# Run development server
make run

# Collect static files
make collect

# Import data
make import-students    # imports students.csv
make import-results     # imports results.csv
```

## Student Access

Students can access their results at:
- **Home**: `/` - Login and overview
- **Profile**: `/me/` - Student information
- **Results**: `/me/results/` - Published examination results

## Admin Features

Administrators can:
- Access Django admin at `/admin/`
- Import CSV files through management commands
- Publish/unpublish results to control student visibility
- View audit logs of all import operations

## Security Features

- **Domain Restriction**: Only `@pmc.edu.pk` Google accounts allowed
- **Ownership Guards**: Students can only see their own results
- **Publication Control**: Results are hidden until explicitly published
- **Audit Trail**: All imports logged with user, timestamp, and row counts
- **CSRF Protection**: All forms protected against cross-site attacks

## Production Deployment

1. **Environment Configuration**:
   - Set `DEBUG=false`
   - Configure PostgreSQL database
   - Set secure `SECRET_KEY`
   - Configure Google OAuth credentials

2. **Security Settings**:
   ```bash
   # Run deployment checks
   python manage.py check --deploy
   ```

3. **Static Files**:
   ```bash
   python manage.py collectstatic
   ```

4. **Process Management**:
   - Use Gunicorn for WSGI server
   - Configure Nginx for reverse proxy
   - Set up systemd service (see `DEPLOY.md`)

## Development

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.accounts
python manage.py test apps.results
```

### Project Structure

```
server/
├── apps/
│   ├── accounts/        # User and student models
│   ├── results/         # Results and import models  
│   └── core/           # Shared utilities
├── config/             # Django settings
├── templates/          # HTML templates
└── manage.py
```

## API Documentation

The application uses Django's built-in views and forms. No REST API is provided in the MVP version.

## Contributing

1. Follow Django best practices
2. Write tests for new features  
3. Update documentation for changes
4. Run tests before submitting PRs

## Support

For issues or questions:
1. Check the audit documentation in `DELIVERABLE_AUDIT.md`
2. Review setup instructions in `SETUP.md`
3. Check deployment guide in `DEPLOY.md`

## License

[Add your license information here]
