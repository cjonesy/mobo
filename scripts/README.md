# 📋 Scripts Directory Usage Guide

The `scripts/` directory contains utility scripts that make development and
deployment easier. Here's how to use each script:

## 🗄️ Database Initialization (`scripts/init_db.py`)

### Basic Usage

```bash
# Initialize database (creates tables + verifies setup)
python scripts/init_db.py

# Only verify existing database
python scripts/init_db.py --verify-only

# Reset database (WARNING: Deletes all data!)
python scripts/init_db.py --reset
```

### What It Does

- Creates database tables for conversations and user profiles
- Sets up PostgreSQL extensions (like pgvector)
- Verifies database connectivity and operations
- Provides safe database reset functionality

### Example Output

```
🚀 Database initialization script started
✅ Configuration validated
📊 Database Configuration:
  URL: postgresql+asyncpg://bot:password@localhost:5432/discord_bot
  Type: PostgreSQL
  Echo: False
  Pool Size: 10
  Max Overflow: 20

🗄️ Starting database initialization...
📚 Initializing conversation memory...
✅ Conversation memory initialized
👤 Initializing user profiles...
✅ User profiles initialized
🎉 Database initialization completed successfully!
```

## 🔄 Database Migrations (`scripts/migrate.py`)

### Basic Usage

```bash
# Apply all pending migrations
python scripts/migrate.py

# Show migration status
python scripts/migrate.py --status

# Create a new migration
python scripts/migrate.py --create "Add user preferences"

# Show rollback instructions
python scripts/migrate.py --rollback 001

# Create initial migration files
python scripts/migrate.py --init-migrations
```

### Migration Workflow

1. **Create Migration**: `--create "Description"`
2. **Edit Migration File**: Add your SQL in
   `scripts/migrations/XXX_description.sql`
3. **Apply Migration**: Run without arguments
4. **Verify**: Check with `--status`

### Example Migration File

```sql
-- Migration: 001_add_user_preferences
-- Description: Add user preference columns
-- Created: 2024-01-15 10:30:00

ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS preferred_response_length TEXT DEFAULT 'medium';

ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC';

-- Rollback:
-- ALTER TABLE user_profiles DROP COLUMN preferred_response_length;
-- ALTER TABLE user_profiles DROP COLUMN timezone;
```

## 🚀 Deployment (`scripts/deploy.py`)

### Development Commands

```bash
# Comprehensive health check
python scripts/deploy.py --health-check

# Run tests
python scripts/deploy.py --test

# Lint and format code
python scripts/deploy.py --lint

# Create production environment template
python scripts/deploy.py --create-prod-env
```

### Docker Commands

```bash
# Build Docker image
python scripts/deploy.py --build-docker

# Build with custom tag
python scripts/deploy.py --build-docker discord-bot:v1.0.0

# Deploy with Docker Compose
python scripts/deploy.py --deploy-docker
```

### Production Commands

```bash
# Full deployment pipeline
python scripts/deploy.py --full-deploy

# Backup database (PostgreSQL only)
python scripts/deploy.py --backup-db

# Backup with custom filename
python scripts/deploy.py --backup-db my_backup.sql
```

## 🔧 Integration with pyproject.toml

Add these to your `pyproject.toml` for convenience:

```toml
[project.scripts]
bot = "bot.main:run_bot"
bot-dev = "bot.main:run_dev"
bot-init-db = "scripts.init_db:main"
bot-migrate = "scripts.migrate:main"
bot-deploy = "scripts.deploy:main"
```

Then use:

```bash
uv run bot-init-db
uv run bot-migrate --status
uv run bot-deploy --health-check
```

## 📊 Typical Development Workflow

### First-Time Setup

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with your tokens

# 2. Initialize database
python scripts/init_db.py

# 3. Run health check
python scripts/deploy.py --health-check

# 4. Start bot
uv run bot-dev
```

### Daily Development

```bash
# 1. Pull latest changes
git pull

# 2. Apply any new migrations
python scripts/migrate.py

# 3. Run tests before coding
python scripts/deploy.py --test

# 4. Start development bot
uv run bot-dev

# 5. Before committing
python scripts/deploy.py --lint
python scripts/deploy.py --test
```

### Production Deployment

```bash
# 1. Create production config
python scripts/deploy.py --create-prod-env
# Edit .env.production with production values

# 2. Full deployment pipeline
python scripts/deploy.py --full-deploy

# 3. Monitor health
python scripts/deploy.py --health-check
```

## 🐛 Troubleshooting

### Database Issues

```bash
# Reset database if corrupted
python scripts/init_db.py --reset

# Check migration status
python scripts/migrate.py --status

# Verify database manually
python scripts/init_db.py --verify-only
```

### Deployment Issues

```bash
# Check all dependencies
python scripts/deploy.py --health-check

# Test without deployment
python scripts/deploy.py --test --lint

# Check Docker build
python scripts/deploy.py --build-docker
```

### Common Errors

**"Migration failed"**:

- Check SQL syntax in migration file
- Ensure database permissions
- Check if migration was partially applied

**"Health check failed"**:

- Verify API keys in environment
- Check database connectivity
- Ensure Discord token is valid

**"Docker build failed"**:

- Check Dockerfile syntax
- Ensure all files are present
- Check Docker daemon is running

## 🔒 Security Considerations

### Production Environment

- Never commit `.env.production` to git
- Use strong database passwords
- Rotate API keys regularly
- Limit admin user IDs

### Database Backups

```bash
# Regular backups (PostgreSQL)
python scripts/deploy.py --backup-db daily_backup_$(date +%Y%m%d).sql

# Automated backups in cron
0 2 * * * cd /path/to/bot && python scripts/deploy.py --backup-db
```

### Migration Safety

- Always backup before migrations
- Test migrations on staging first
- Include rollback instructions
- Review SQL carefully

## 📈 Monitoring and Maintenance

### Regular Health Checks

```bash
# Daily health check
python scripts/deploy.py --health-check

# Database status
python scripts/migrate.py --status

# Service status (Docker)
docker-compose ps
docker-compose logs bot
```

### Performance Monitoring

```bash
# Check database performance
python -c "
from bot.memory.conversation import ConversationMemory
import asyncio
import time

async def test_perf():
    cm = ConversationMemory('your_db_url')
    start = time.time()
    await cm.get_recent_messages('test', limit=100)
    print(f'Query took: {time.time() - start:.2f}s')
    await cm.close()

asyncio.run(test_perf())
"
```

This scripts directory provides a complete toolkit for managing your Discord bot
from development through production deployment!
