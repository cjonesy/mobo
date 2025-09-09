#!/usr/bin/env python3
"""
Database migration system.

This script handles database schema migrations for the Discord bot.
It tracks migration versions and applies changes incrementally.
"""

import asyncio
import logging
import sys
import textwrap
from datetime import datetime, UTC
from pathlib import Path
from typing import List, Dict, Any

# Add the src directory to the Python path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from mobo.config import get_settings
from mobo.utils.logging import setup_logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, Column, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)

# Migration tracking table
Base = declarative_base()


class Migration(Base):
    """Track applied migrations."""

    __tablename__ = "migrations"

    id = Column(Integer, primary_key=True)
    version = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    applied_at = Column(DateTime, default=lambda: datetime.now(UTC))


class MigrationSystem:
    """Handles database migrations."""

    def __init__(self):
        self.settings = get_settings()
        self.engine = create_async_engine(self.settings.database_url_for_sqlalchemy)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.migrations_dir = Path(__file__).parent / "migrations"
        self.migrations_dir.mkdir(exist_ok=True)

    async def initialize_migration_table(self):
        """Create the migrations tracking table if it doesn't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Migration tracking table initialized")

    async def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT version FROM migrations ORDER BY applied_at")
            )
            return [row.version for row in result.fetchall()]

    async def mark_migration_applied(self, version: str, name: str):
        """Mark a migration as applied."""
        async with self.session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO migrations (version, name, applied_at) "
                    "VALUES (:version, :name, :applied_at)"
                ),
                {"version": version, "name": name, "applied_at": datetime.now(UTC)},
            )
            await session.commit()

    def get_available_migrations(self) -> List[Dict[str, str]]:
        """Get list of available migration files."""
        migrations = []

        for migration_file in sorted(self.migrations_dir.glob("*.sql")):
            # Extract version from filename (e.g., "001_add_user_preferences.sql")
            parts = migration_file.stem.split("_", 1)
            if len(parts) == 2:
                version, name = parts
                migrations.append(
                    {
                        "version": version,
                        "name": name.replace("_", " ").title(),
                        "file": migration_file,
                    }
                )

        return migrations

    async def apply_migration(self, migration: Dict[str, str]):
        """Apply a single migration."""
        logger.info(
            f"📦 Applying migration {migration['version']}: {migration['name']}"
        )

        # Read migration SQL
        sql_content = migration["file"].read_text()

        async with self.engine.begin() as conn:
            # Split and execute SQL statements
            statements = [
                stmt.strip() for stmt in sql_content.split(";") if stmt.strip()
            ]

            for statement in statements:
                logger.debug(f"Executing: {statement[:100]}...")
                await conn.execute(text(statement))

        # Mark as applied
        await self.mark_migration_applied(migration["version"], migration["name"])
        logger.info(f"✅ Migration {migration['version']} applied successfully")

    async def migrate(self):
        """Apply all pending migrations."""
        await self.initialize_migration_table()

        applied_migrations = await self.get_applied_migrations()
        available_migrations = self.get_available_migrations()

        pending_migrations = [
            m for m in available_migrations if m["version"] not in applied_migrations
        ]

        if not pending_migrations:
            logger.info("✅ No pending migrations")
            return

        logger.info(f"📦 Found {len(pending_migrations)} pending migrations")

        for migration in pending_migrations:
            await self.apply_migration(migration)

        logger.info("🎉 All migrations applied successfully!")

    async def status(self):
        """Show migration status."""
        await self.initialize_migration_table()

        applied_migrations = await self.get_applied_migrations()
        available_migrations = self.get_available_migrations()

        print("\n📊 Migration Status:")
        print("=" * 50)

        for migration in available_migrations:
            status = (
                "✅ Applied"
                if migration["version"] in applied_migrations
                else "⏳ Pending"
            )
            print(f"{migration['version']}: {migration['name']} - {status}")

        pending_count = len(
            [m for m in available_migrations if m["version"] not in applied_migrations]
        )
        print(f"\nTotal migrations: {len(available_migrations)}")
        print(f"Applied: {len(applied_migrations)}")
        print(f"Pending: {pending_count}")

    async def create_migration(self, name: str):
        """Create a new migration file."""
        # Get next version number
        available_migrations = self.get_available_migrations()
        if available_migrations:
            last_version = max(int(m["version"]) for m in available_migrations)
            new_version = f"{last_version + 1:03d}"
        else:
            new_version = "001"

        # Create filename
        clean_name = name.lower().replace(" ", "_").replace("-", "_")
        filename = f"{new_version}_{clean_name}.sql"
        migration_file = self.migrations_dir / filename

        # Create migration template
        template = textwrap.dedent(
            f"""
            -- Migration: {new_version}_{clean_name}
            -- Description: {name}
            -- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

            -- Add your migration SQL here
            -- Example:
            -- ALTER TABLE users ADD COLUMN new_field TEXT;

            -- Don't forget to add rollback instructions in comments if needed
            -- Rollback: ALTER TABLE users DROP COLUMN new_field;
            """
        ).strip()

        migration_file.write_text(template)
        logger.info(f"📝 Created migration file: {migration_file}")
        print(f"Migration file created: {migration_file}")
        print(
            "Edit the file to add your SQL statements, then run: python scripts/migrate.py"
        )

    async def rollback(self, version: str):
        """Rollback a migration (manual process)."""
        logger.warning("⚠️ Rollback is a manual process")
        print(f"\nTo rollback migration {version}:")
        print("1. Check the migration file for rollback instructions")
        print("2. Manually execute the rollback SQL")
        print("3. Remove the migration record:")
        print(f"   DELETE FROM migrations WHERE version = '{version}';")

    async def close(self):
        """Close database connections."""
        await self.engine.dispose()


# =============================================================================
# PREDEFINED MIGRATIONS
# =============================================================================


def create_initial_migrations():
    """Create initial migration files if they don't exist."""
    migrations_dir = Path(__file__).parent / "migrations"
    migrations_dir.mkdir(exist_ok=True)

    # Migration 001: Add user preferences
    migration_001 = migrations_dir / "001_add_user_preferences.sql"
    if not migration_001.exists():
        migration_001.write_text(
            """-- Migration: 001_add_user_preferences
-- Description: Add user preference columns to user_profiles table
-- Created: 2024-01-01 00:00:00

-- Add preference columns if they don't exist
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS preferred_response_length TEXT DEFAULT 'medium';

ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC';

ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS last_active TIMESTAMP DEFAULT now();

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_user_profiles_last_active
ON user_profiles (last_active);

-- Rollback:
-- ALTER TABLE user_profiles DROP COLUMN preferred_response_length;
-- ALTER TABLE user_profiles DROP COLUMN timezone;
-- ALTER TABLE user_profiles DROP COLUMN last_active;
-- DROP INDEX idx_user_profiles_last_active;
"""
        )

    # Migration 002: Add conversation indexing
    migration_002 = migrations_dir / "002_improve_conversation_indexing.sql"
    if not migration_002.exists():
        migration_002.write_text(
            """-- Migration: 002_improve_conversation_indexing
-- Description: Improve conversation memory indexing for better performance
-- Created: 2024-01-01 00:00:00

-- Add composite index for better query performance
CREATE INDEX IF NOT EXISTS idx_conversation_user_channel_time
ON conversation_memory (user_id, channel_id, timestamp DESC);

-- Add index for content search
CREATE INDEX IF NOT EXISTS idx_conversation_content_search
ON conversation_memory USING gin(to_tsvector('english', content));

-- Add metadata column for future extensibility
ALTER TABLE conversation_memory
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Create index on metadata for JSON queries
CREATE INDEX IF NOT EXISTS idx_conversation_metadata
ON conversation_memory USING gin(metadata);

-- Rollback:
-- DROP INDEX idx_conversation_user_channel_time;
-- DROP INDEX idx_conversation_content_search;
-- ALTER TABLE conversation_memory DROP COLUMN metadata;
-- DROP INDEX idx_conversation_metadata;
"""
        )

    logger.info("📝 Initial migration files created")


async def main():
    """Main migration function."""
    setup_logging()
    logger.info("🚀 Database migration script started")

    migration_system = MigrationSystem()

    try:
        await migration_system.migrate()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        await migration_system.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database migration system")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument(
        "--create", type=str, help="Create a new migration with the given name"
    )
    parser.add_argument(
        "--rollback",
        type=str,
        help="Show rollback instructions for a migration version",
    )
    parser.add_argument(
        "--init-migrations", action="store_true", help="Create initial migration files"
    )

    args = parser.parse_args()

    if args.init_migrations:
        setup_logging()
        create_initial_migrations()
    elif args.create:

        async def create():
            setup_logging()
            migration_system = MigrationSystem()
            try:
                await migration_system.create_migration(args.create)
            finally:
                await migration_system.close()

        asyncio.run(create())
    elif args.status:

        async def status():
            setup_logging()
            migration_system = MigrationSystem()
            try:
                await migration_system.status()
            finally:
                await migration_system.close()

        asyncio.run(status())
    elif args.rollback:

        async def rollback():
            setup_logging()
            migration_system = MigrationSystem()
            try:
                await migration_system.rollback(args.rollback)
            finally:
                await migration_system.close()

        asyncio.run(rollback())
    else:
        asyncio.run(main())
