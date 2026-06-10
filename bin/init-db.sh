#!/usr/bin/env bash
# Script: One-shot Postgres schema setup
# Purpose: Runs the DDL. Replaces the per-Lambda init_db() that used to run on
#          every cold start.
# Usage:   ./init-db.sh

set -e

PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-5432}"
PGUSER="${POSTGRES_USER:-postgres}"
PGPASSWORD="${POSTGRES_PASS:-postgres123}"
PGDATABASE="${POSTGRES_NAME:-postgres}"
export PGPASSWORD

PSQL="psql -v ON_ERROR_STOP=1 -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -q"

# Terminate any leftover "idle in transaction" backends that would hold table
# locks and block our ALTER TABLE statements. The backend lambdas don't always
# COMMIT/close on shutdown, so this is a routine occurrence under start-dev.sh.
$PSQL -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND datname = current_database() AND pid <> pg_backend_pid();" >/dev/null

$PSQL <<'SQL'
-- Fail fast instead of hanging if something is still holding a lock.
SET lock_timeout = '5s';
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE TABLE IF NOT EXISTS users (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(255) UNIQUE NOT NULL, name VARCHAR(255) NOT NULL, picture TEXT, user_role VARCHAR(50) NOT NULL DEFAULT 'viewer', is_active BOOLEAN DEFAULT TRUE, username VARCHAR(100) UNIQUE, password_hash TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100) UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
CREATE TABLE IF NOT EXISTS projects (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), title VARCHAR(255) NOT NULL, description TEXT, status VARCHAR(50) NOT NULL DEFAULT 'active', health VARCHAR(50) NOT NULL DEFAULT 'green', start_date DATE, end_date DATE, budget_planned DECIMAL(15,2) DEFAULT 0.00, budget_consumed DECIMAL(15,2) DEFAULT 0.00, dependency_ids UUID[] DEFAULT '{}', is_deleted BOOLEAN DEFAULT FALSE, created_by UUID, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS people (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(255) NOT NULL, email VARCHAR(255) UNIQUE NOT NULL, title VARCHAR(100), weekly_hours_capacity INTEGER DEFAULT 40, hourly_pay DECIMAL(15,2), is_active BOOLEAN DEFAULT TRUE, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
ALTER TABLE people ADD COLUMN IF NOT EXISTS hourly_pay DECIMAL(15,2);
CREATE TABLE IF NOT EXISTS assignments (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), person_id UUID NOT NULL, project_id UUID NOT NULL, role_on_project VARCHAR(100), hours_per_week INTEGER DEFAULT 0, start_date DATE, end_date DATE, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS deliverables (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL, title VARCHAR(255) NOT NULL, description TEXT, status VARCHAR(50) NOT NULL DEFAULT 'pending', due_date DATE, depends_on_id UUID, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS budget_items (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL, category VARCHAR(100) NOT NULL DEFAULT 'other', description TEXT, amount_planned DECIMAL(15,2) DEFAULT 0.00, amount_consumed DECIMAL(15,2) DEFAULT 0.00, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS staff_budget_overrides (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL, person_id UUID NOT NULL, amount_planned DECIMAL(15,2), amount_consumed DECIMAL(15,2), is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), UNIQUE(project_id, person_id));
SQL

echo "  ✓ DB schema applied"
