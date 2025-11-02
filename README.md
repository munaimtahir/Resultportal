# PMC Result Portal

A comprehensive result management system for PMC (Pakistan Medical Council) with multi-stage verification workflow, analytics dashboards, and secure student access.

## Features

### Core Functionality
- **Multi-Stage Verification Workflow**: DRAFT → SUBMITTED → VERIFIED → PUBLISHED with audit trail
- **Google Workspace SSO**: Login restricted to `@pmc.edu.pk` domain
- **Student Self-Service**: Students can view published results and apply for rechecks
- **CSV Import System**: Bulk import students and results with comprehensive validation
- **Year/Class Management**: Organize students and exams by academic year
- **Exam Management**: Track exams with recheck deadlines and metadata
- **Admin Management**: Staff can upload, verify, and publish results
- **Audit Trail**: Full logging of all operations and status changes

### Analytics & Insights
- **Exam Aggregates**: Mean, median, standard deviation, pass rates, grade distribution
- **Component Analysis**: Separate statistics for theory and practical components
- **Comparison Metrics**: Year-over-year trends and performance analysis
- **Anomaly Detection**: Automatic flagging of unusual patterns
- **Dashboard-Ready**: Pre-computed aggregates for Principal, Controller, and HOD views

### Security & Access Control
- **Token-Based Student Access**: Lightweight authentication for students without Google accounts
- **Strict Ownership Guards**: Students can only see their own results
- **Publication Control**: Results hidden until explicitly published
- **Feature Flags**: Configurable system behavior (FEATURE_RESULTS_ONLY, ALLOW_PUBLISH)

## Quick Start

### Option 1: Docker (Recommended)

The fastest way to get started is using Docker. This handles all dependencies and database setup automatically.

#### Prerequisites
- Docker and Docker Compose installed
- No other services running on ports 8000 and 5432

#### Quick Setup (One Command)

```bash
./docker-setup.sh
```

This script will:
- Check Docker installation
- Create `.env` file from `.env.docker`
- Build containers
- Start all services
- Verify everything is running

#### Manual Setup

1. **Clone the repository**:
```bash
git clone <repository-url>
cd Resultportal
```

2. **Setup environment**:
```bash
cp .env.docker .env
# Optionally edit .env for Google OAuth credentials
```

3. **Build and start services**:
```bash
docker compose up -d
```

This single command will:
- Build the Django application container
- Start PostgreSQL database
- Run database migrations
- Collect static files
- Start the web server on http://localhost:8000

4. **Create a superuser** (optional):
```bash
docker compose exec web python manage.py createsuperuser
```

5. **View logs**:
```bash
docker compose logs -f web
```

6. **Stop services**:
```bash
docker compose down
```

7. **Stop and remove all data**:
```bash
docker compose down -v  # Warning: This deletes the database
```

#### Import Data with Docker

```bash
# Import students
docker compose exec web python manage.py import_students /app/students.csv --commit

# Import results
docker compose exec web python manage.py import_results /app/results.csv --commit
```

To import files from your host machine, copy them to the container first:
```bash
docker cp students.csv resultportal_web:/app/students.csv
docker compose exec web python manage.py import_students /app/students.csv --commit
```

#### Run Tests with Docker

```bash
docker compose exec web pytest
```

#### Docker Troubleshooting

**Port already in use:**
```bash
# Check what's using port 8000 or 5432
sudo lsof -i :8000
sudo lsof -i :5432

# Stop the conflicting service or use different ports in docker-compose.yml
```

**Database issues:**
```bash
# Reset the database completely
docker compose down -v
docker compose up -d
```

**View detailed logs:**
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f web
docker compose logs -f db
```

**Container won't start:**
```bash
# Rebuild without cache
docker compose build --no-cache
docker compose up -d
```

**Permission issues:**
```bash
# Ensure Docker daemon is running
sudo systemctl status docker

# Add your user to docker group (Linux)
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

### Option 2: Local Installation

#### Prerequisites

- Python 3.11+ or 3.12
- PostgreSQL 14+ (SQLite for development)
- Google Cloud project with OAuth2 credentials (optional for admin access)

#### Installation

1. **Clone and setup environment**:
```bash
git clone <repository-url>
cd Resultportal
make install  # or: pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your database and Google OAuth credentials
```

3. **Setup database**:
```bash
make migrate  # or: cd server && python manage.py migrate
python manage.py createsuperuser
```

4. **Run development server**:
```bash
make run  # or: cd server && python manage.py runserver
```

5. **Run tests**:
```bash
make test  # or: cd server && pytest --cov=apps
```

## Data Models

### Accounts App
- **YearClass**: Academic year/class (1st Year, 2nd Year, etc.)
- **Student**: Student records with year_class, roll_number, contact info
- **StudentAccessToken**: One-time access tokens for lightweight authentication

### Results App
- **Exam**: Exam definitions with recheck deadlines and metadata
- **Result**: Individual subject results with workflow status (DRAFT/SUBMITTED/VERIFIED/PUBLISHED)
- **ImportBatch**: Audit trail for CSV imports with error/warning tracking

### Analytics App
- **ExamAggregate**: Statistical summaries (mean, median, std dev, pass rates)
- **ComponentAggregate**: Component-wise statistics (theory, practical)
- **ComparisonAggregate**: Year-over-year comparison metrics
- **TrendAggregate**: Multi-session trend analysis
- **AnomalyFlag**: Detected anomalies and alerts

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

Common development tasks using the Makefile:

```bash
# Install dependencies
make install

# Run database migrations
make migrate

# Create superuser
make superuser

# Run development server
make run

# Run tests with coverage
make test

# Format code
make fmt

# Run linters
make lint

# Collect static files
make collect

# Import data
make import-students    # imports students.csv
make import-results     # imports results.csv

# Compute analytics (when implemented)
make analytics
```

## Result Verification Workflow

Results follow a multi-stage verification workflow:

1. **DRAFT**: Initially created from CSV import
2. **SUBMITTED**: Assistant submits for verification
3. **VERIFIED**: Admin verifies the results
4. **PUBLISHED**: Results made visible to students
5. **RETURNED**: Admin can return for correction (from SUBMITTED state)

Each status change is logged in the audit trail (`status_log` JSON field).

## Student Access

### With Google Workspace Account
Students can login at `/` using their `@pmc.edu.pk` Google account.

### With Access Token (Lightweight Auth)
For students without Google accounts:
1. Visit `/student-access/` (when implemented)
2. Enter roll number + email/phone
3. Receive one-time access token
4. View published results
5. Apply for recheck if deadline not passed

## Monitoring

Health check endpoint available at `/healthz`:

```bash
curl http://localhost:8000/healthz
# {"status": "ok", "database": "connected"}
```

## Testing

Run the test suite:

```bash
# All tests with coverage
make test

# Specific app tests
cd server
python manage.py test apps.accounts
python manage.py test apps.results
python manage.py test apps.analytics

# With pytest
cd server
pytest apps/accounts/tests.py -v
pytest apps/results/tests.py -v
```

Current test coverage: **42 tests** covering:
- Model validation and constraints
- Status workflow transitions
- CSV import with validation
- Token generation and expiration
- Year/Class relationships
- Audit trail logging

## Development

### Code Quality

```bash
# Format code
make fmt

# Run linters
make lint

# Both tools configured in pyproject.toml
```

### CI/CD

GitHub Actions workflow runs on every push:
- Matrix build (Python 3.11, 3.12)
- Linting (ruff, black)
- Tests with coverage
- CodeQL security scanning

## Project Structure

```
Resultportal/
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI pipeline
├── server/
│   ├── apps/
│   │   ├── accounts/        # User, Student, YearClass, AccessToken models
│   │   ├── results/         # Exam, Result, ImportBatch models + workflow
│   │   ├── analytics/       # Aggregates, trends, anomaly detection
│   │   └── core/           # Shared utilities, healthz endpoint
│   ├── config/             # Django settings, URLs, WSGI
│   ├── templates/          # HTML templates
│   ├── static/             # Static assets
│   └── manage.py
├── requirements.txt        # Python dependencies
├── pytest.ini              # Pytest configuration
├── pyproject.toml          # Tool configurations (ruff, black, pytest)
├── Makefile                # Common development tasks
├── .env.example            # Environment variables template
└── README.md               # This file
```

## Environment Variables

Key settings in `.env`:

```bash
# Core
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your.domain.com,localhost

# Database
DB_ENGINE=postgresql  # or sqlite
DB_NAME=result_portal
DB_USER=db_user
DB_PASSWORD=db_password

# Google OAuth (for admin access)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Feature Flags
FEATURE_RESULTS_ONLY=false  # Restrict to results-only mode
ALLOW_PUBLISH=true          # Enable result publishing
```

## Production Deployment

See `DEPLOY.md` for detailed deployment instructions.

Quick checklist:
1. Set `DEBUG=false`
2. Configure PostgreSQL database
3. Set secure `SECRET_KEY`
4. Configure `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
5. Set up Google OAuth credentials
6. Run `make collect` for static files
7. Use Gunicorn + Nginx for serving
8. Set up systemd service for process management

## API Endpoints (Future)

Analytics dashboards (planned):
```
/admin/analytics/exams/<id>/snapshot/      # KPI snapshot
/admin/analytics/exams/<id>/components/     # Component breakdown
/admin/analytics/exams/<id>/comparisons/    # Year-over-year
/admin/analytics/years/<year_id>/trends/    # Multi-session trends
/admin/analytics/exams/<id>/integrity/      # Data quality checks
/admin/analytics/exams/<id>/governance/     # Governance metrics
/admin/analytics/exams/<id>/equity/         # Equity analysis
/admin/analytics/exams/<id>/export.csv      # CSV export
/admin/analytics/executive.pdf              # Executive summary PDF
```

## Roadmap

### ✅ Phase 1 - Foundation (Complete)
- Extended data models with workflow
- Comprehensive test suite (42 tests)
- CI/CD pipeline
- Development tooling
- Analytics models scaffold

### 🚧 Phase 2 - Import Enhancement (In Progress)
- Enhanced CSV validation
- Year/Class integration
- Exam linking
- Template generation

### 📋 Phase 3 - Verification UI (Planned)
- Admin dashboard for pending results
- Bulk verification actions
- Audit trail visualization

### 📋 Phase 4 - Student Portal (Planned)
- Token-based authentication
- Result viewing
- Recheck application

### 📋 Phase 5 - Analytics Engine (Planned)
- Statistical computations
- Dashboard APIs
- PDF/CSV exports

## Contributing

1. Follow Django best practices
2. Write tests for new features
3. Run `make fmt` before committing
4. Ensure `make test` passes
5. Update documentation

## License

[To be determined]

## Support

For issues or questions:
1. Check documentation in `DELIVERABLE_AUDIT.md`
2. Review setup instructions in `SETUP.md`
3. Check deployment guide in `DEPLOY.md`
4. Review analytics documentation in `ANALYTICS.md` (when available)
