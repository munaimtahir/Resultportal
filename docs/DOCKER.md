# Docker Quick Reference

## Quick Start

```bash
./docker-setup.sh
```

This single script will set up everything you need to run the Result Portal.

## Manual Commands

### First Time Setup

```bash
# 1. Create environment file
cp .env.docker .env

# 2. Build and start services
docker compose up -d

# 3. Create a superuser (optional)
docker compose exec web python manage.py createsuperuser
```

### Daily Operations

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f web

# Run tests
docker compose exec web pytest

# Access Django shell
docker compose exec web python manage.py shell

# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser
```

### Data Import

```bash
# Copy CSV file to container
docker cp students.csv resultportal_web:/app/students.csv

# Import students
docker compose exec web python manage.py import_students /app/students.csv --commit

# Import results
docker compose exec web python manage.py import_results /app/results.csv --commit
```

### Troubleshooting

```bash
# Reset database (WARNING: Deletes all data)
docker compose down -v
docker compose up -d

# Rebuild containers from scratch
docker compose build --no-cache
docker compose up -d

# View all container logs
docker compose logs

# Check container status
docker compose ps

# Access database directly
docker compose exec db psql -U result_portal_user -d result_portal
```

## Environment Variables

Key variables in `.env`:

- `DB_NAME`: Database name (default: result_portal)
- `DB_USER`: Database user (default: result_portal_user)
- `DB_PASSWORD`: Database password
- `DJANGO_DEBUG`: Set to `True` for development
- `DJANGO_SECRET_KEY`: Secret key for Django
- `GOOGLE_CLIENT_ID`: Google OAuth client ID (optional)
- `GOOGLE_CLIENT_SECRET`: Google OAuth secret (optional)

## Ports

- **8000**: Web application (Django/Gunicorn)
- **5432**: PostgreSQL database

## Volumes

- `resultportal_postgres_data`: Database data (persisted)
- `resultportal_static_volume`: Static files

## Network

All services run on the `resultportal_network` bridge network.

## Production Considerations

For production deployment:

1. Change `DJANGO_DEBUG=False` in `.env`
2. Set a strong `DJANGO_SECRET_KEY`
3. Update `DJANGO_ALLOWED_HOSTS` with your domain
4. Configure `DJANGO_CSRF_TRUSTED_ORIGINS`
5. Set up proper SSL/TLS termination
6. Use Docker secrets for sensitive data
7. Enable log aggregation
8. Set up automated backups for volumes
9. Consider using Docker Swarm or Kubernetes for orchestration

## Useful Makefile Commands

```bash
# Docker commands via Makefile
make docker-build      # Build containers
make docker-up         # Start containers
make docker-down       # Stop containers
make docker-logs       # View logs
make docker-shell      # Open shell in web container
make docker-test       # Run tests
make docker-clean      # Remove containers and volumes
```

## Access Points

- **Application**: http://localhost:8000
- **Health Check**: http://localhost:8000/healthz
- **Admin Panel**: http://localhost:8000/admin
- **Database**: localhost:5432

## Support

For issues or questions, see the main README.md or check the logs:
```bash
docker compose logs -f
```
