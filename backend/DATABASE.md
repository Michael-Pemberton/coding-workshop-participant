# Database Setup & Reference

## Overview

This application uses **PostgreSQL** as its primary database. The database schema is automatically initialized on Lambda cold start via the `DDL` constant in `backend/shared.py`.

## Prerequisites

**Local Development:**
- PostgreSQL 14+ (installed and running)
- `psql` command-line tool
- Environment variables properly configured (see below)

**AWS Deployment:**
- Amazon RDS Aurora PostgreSQL cluster (managed by Terraform)
- Credentials provided via environment variables

## Local Setup

### 1. Install PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql@16
brew services start postgresql@16
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 2. Create Database

```bash
createdb postgres
```

The default database is `postgres` (configured in `POSTGRES_NAME`). No manual schema creation is needed—it's auto-initialized when Lambda functions first run.

### 3. Verify Connection

```bash
psql -h localhost -U postgres -d postgres -c "SELECT version();"
```

Expected output: PostgreSQL version info.

### 4. Start Development Environment

The `start-dev.sh` script handles all setup (PostgreSQL, MongoDB, LocalStack, Lambda):

```bash
./bin/start-dev.sh
```

This will:
- Verify PostgreSQL is running and accessible on `0.0.0.0:5432`
- Start MongoDB (also required for some services)
- Start LocalStack (AWS emulator)
- Deploy Lambda functions with Terraform
- Start the React dev server

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_HOST` | `localhost` | Database hostname |
| `POSTGRES_PORT` | `5432` | Database port |
| `POSTGRES_NAME` | `postgres` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASS` | `postgres123` | Database password |
| `JWT_SECRET` | `dev-secret-key-change-in-production` | JWT signing key |
| `IS_LOCAL` | `false` | Local dev flag (disables SSL) |

**Local Dev (.env or shell):**
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_NAME=postgres
export POSTGRES_USER=postgres
export POSTGRES_PASS=postgres123
export IS_LOCAL=true
```

**AWS (set via Terraform):**
- Variables are auto-configured from RDS Aurora endpoint
- SSL is required (`sslmode=require`)
- Credentials are AWS-managed

## Database Schema

### Tables

#### `users`
Stores authenticated users and their roles.

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  user_role VARCHAR(50) NOT NULL DEFAULT 'viewer',  -- admin, manager, contributor, viewer
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `projects`
Team projects with budget and health tracking.

```sql
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255) NOT NULL,
  description TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'active',
  health VARCHAR(50) NOT NULL DEFAULT 'green',  -- RAG: green, amber, red
  start_date DATE,
  end_date DATE,
  budget_planned DECIMAL(15,2) DEFAULT 0.00,
  budget_consumed DECIMAL(15,2) DEFAULT 0.00,
  dependency_ids UUID[] DEFAULT '{}',  -- Array of project IDs this depends on
  is_deleted BOOLEAN DEFAULT FALSE,
  created_by UUID,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `people`
Team members with capacity allocation.

```sql
CREATE TABLE people (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  title VARCHAR(100),
  weekly_hours_capacity INTEGER DEFAULT 40,
  is_active BOOLEAN DEFAULT TRUE,
  is_deleted BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `assignments`
Links people to projects with hours per week.

```sql
CREATE TABLE assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id UUID NOT NULL,
  project_id UUID NOT NULL,
  role_on_project VARCHAR(100),
  hours_per_week INTEGER DEFAULT 0,
  start_date DATE,
  end_date DATE,
  is_deleted BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `deliverables`
Project milestones/deliverables with status tracking.

```sql
CREATE TABLE deliverables (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'pending',
  due_date DATE,
  depends_on_id UUID,  -- Another deliverable this depends on
  is_deleted BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `budget_items`
Budget line items per project.

```sql
CREATE TABLE budget_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL,
  category VARCHAR(100) NOT NULL DEFAULT 'other',
  description TEXT,
  amount_planned DECIMAL(15,2) DEFAULT 0.00,
  amount_consumed DECIMAL(15,2) DEFAULT 0.00,
  is_deleted BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Relationships

```
users 1---* projects (created_by)
projects 1---* assignments (project_id)
projects 1---* deliverables (project_id)
projects 1---* budget_items (project_id)
people 1---* assignments (person_id)
deliverables * --- 0..1 deliverables (depends_on_id)
```

## Useful psql Commands

### Connect
```bash
psql -h localhost -U postgres -d postgres
```

### Inspect Schema
```sql
-- List all tables
\dt

-- Describe a table
\d projects

-- List all columns in projects table
SELECT column_name, data_type FROM information_schema.columns 
WHERE table_name = 'projects';
```

### View Data
```sql
-- List all projects
SELECT id, title, status, health FROM projects WHERE is_deleted = FALSE;

-- Count rows per table
SELECT 'users' AS table_name, COUNT(*) FROM users
UNION ALL
SELECT 'projects', COUNT(*) FROM projects
UNION ALL
SELECT 'people', COUNT(*) FROM people;

-- Find overallocated people
SELECT p.name, p.weekly_hours_capacity, 
       SUM(a.hours_per_week) AS total_allocated
FROM people p
LEFT JOIN assignments a ON a.person_id = p.id AND a.is_deleted = FALSE
WHERE p.is_deleted = FALSE
GROUP BY p.id, p.name, p.weekly_hours_capacity
HAVING SUM(a.hours_per_week) > p.weekly_hours_capacity;
```

## Reset / Clear Data

### Delete All Data (Keep Schema)
```sql
-- Disable foreign key checks (if needed)
DELETE FROM budget_items WHERE is_deleted = FALSE;
DELETE FROM deliverables WHERE is_deleted = FALSE;
DELETE FROM assignments WHERE is_deleted = FALSE;
DELETE FROM projects WHERE is_deleted = FALSE;
DELETE FROM people WHERE is_deleted = FALSE;
DELETE FROM users WHERE is_deleted = FALSE;

-- Or soft-delete everything
UPDATE budget_items SET is_deleted = TRUE;
UPDATE deliverables SET is_deleted = TRUE;
UPDATE assignments SET is_deleted = TRUE;
UPDATE projects SET is_deleted = TRUE;
UPDATE people SET is_deleted = TRUE;
```

### Drop & Recreate Database
```bash
dropdb postgres
createdb postgres
# Then run Lambda functions to auto-initialize schema
```

## Local vs AWS

| Aspect | Local | AWS |
|--------|-------|-----|
| **Host** | `localhost` or `172.17.0.1` (Docker) | RDS endpoint (e.g., `mydb.xxxxx.us-east-1.rds.amazonaws.com`) |
| **SSL** | Disabled (`IS_LOCAL=true`) | Required (`sslmode=require`) |
| **Auth** | Basic username/password | IAM-managed or RDS credentials |
| **Backup** | Manual or OS-level | Automatic (AWS RDS) |
| **Schema Init** | Lambda cold start | Lambda cold start |

## Troubleshooting

### "Connection refused"
- Verify PostgreSQL is running: `pg_isready`
- Check bindings: `ss -ltn | grep 5432` (should show `0.0.0.0:5432` or `127.0.0.1:5432`)
- Linux: PostgreSQL may need `listen_addresses = '*'` in `/etc/postgresql/postgresql.conf`

### "Permission denied"
- Verify credentials in environment variables
- Check PostgreSQL user exists: `psql -l`
- Reset password: `ALTER USER postgres WITH PASSWORD 'new_password';`

### "relation does not exist"
- Tables are created on first Lambda invocation (cold start)
- Verify Lambda has run: check CloudWatch logs
- Or manually run: `psql -f backend/shared.py` (extract DDL)

### Tests Fail with DB Connection Error
- Set `IS_LOCAL=true`: `export IS_LOCAL=true`
- Ensure PostgreSQL is running: `pg_isready`
- Check environment variables are set

## See Also

- **Backend README:** `backend/README.md` — Lambda services, environment variables
- **Frontend README:** `frontend/README.md` — React app setup
- **Infrastructure:** `infra/README.md` — Terraform and AWS resources
- **Tests:** `backend/tests/` — Pytest fixtures and examples
