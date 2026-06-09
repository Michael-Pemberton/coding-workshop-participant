"""PostgreSQL connection management with module-level connection pooling."""
import logging
from typing import Optional

import psycopg

logger = logging.getLogger(__name__)

_connection: Optional[psycopg.Connection] = None

DDL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE TABLE IF NOT EXISTS users (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(255) UNIQUE NOT NULL, name VARCHAR(255) NOT NULL, picture TEXT, user_role VARCHAR(50) NOT NULL DEFAULT 'viewer', is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS projects (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), title VARCHAR(255) NOT NULL, description TEXT, status VARCHAR(50) NOT NULL DEFAULT 'active', health VARCHAR(50) NOT NULL DEFAULT 'green', start_date DATE, end_date DATE, budget_planned DECIMAL(15,2) DEFAULT 0.00, budget_consumed DECIMAL(15,2) DEFAULT 0.00, dependency_ids UUID[] DEFAULT '{}', is_deleted BOOLEAN DEFAULT FALSE, created_by UUID, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS people (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(255) NOT NULL, email VARCHAR(255) UNIQUE NOT NULL, title VARCHAR(100), weekly_hours_capacity INTEGER DEFAULT 40, is_active BOOLEAN DEFAULT TRUE, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS assignments (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), person_id UUID NOT NULL, project_id UUID NOT NULL, role_on_project VARCHAR(100), hours_per_week INTEGER DEFAULT 0, start_date DATE, end_date DATE, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS deliverables (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL, title VARCHAR(255) NOT NULL, description TEXT, status VARCHAR(50) NOT NULL DEFAULT 'pending', due_date DATE, depends_on_id UUID, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
CREATE TABLE IF NOT EXISTS budget_items (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), project_id UUID NOT NULL, category VARCHAR(100) NOT NULL DEFAULT 'other', description TEXT, amount_planned DECIMAL(15,2) DEFAULT 0.00, amount_consumed DECIMAL(15,2) DEFAULT 0.00, is_deleted BOOLEAN DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());
"""


def get_connection(dsn: str) -> psycopg.Connection:
    """
    Returns a live PostgreSQL connection, reusing the module-level pool.

    Args:
        dsn: psycopg connection string.

    Returns:
        psycopg.Connection: An open database connection.
    """
    global _connection
    try:
        if _connection is None or _connection.closed:
            _connection = psycopg.connect(dsn)
            logger.info("Database connection established")
    except Exception as exc:
        logger.error("Failed to connect to database: %s", exc)
        _connection = None
        raise
    return _connection


def init_db(dsn: str) -> None:
    """
    Runs idempotent DDL to create all application tables if they do not exist.

    Safe to call on every Lambda cold start.

    Args:
        dsn: psycopg connection string.
    """
    conn = get_connection(dsn)
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()
    logger.info("Database schema initialized")
