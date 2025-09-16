# 📋 Scripts Directory Usage Guide

The `scripts/` directory contains utility scripts that make development easier.
Currently contains database initialization script:

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

## 🔧 Development Workflow

The project uses the `justfile` for most development tasks. Here are the key
commands:

### Development Environment

```bash
# Start development environment (PostgreSQL + bot)
just dev

# Stop development environment
just dev-stop

# Reset database (clean slate)
just dev-reset

# Connect to development database
just dev-db
```

### Code Quality

```bash
# Run tests
just test

# Lint code
just lint

# Format code
just format

# Type check
just typecheck

# Run all quality checks
just check
```

### Docker Operations

```bash
# Build Docker image
just build

# Start all services with Docker
just up

# Stop services
just down

# View logs
just logs
```

## 📊 Typical Development Workflow

### First-Time Setup

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with your tokens

# 2. Start development environment (includes database initialization)
just dev
```

### Daily Development

```bash
# 1. Pull latest changes
git pull

# 2. Start development environment
just dev

# 3. Before committing
just check  # Runs lint, typecheck, and tests
```

## 🐛 Troubleshooting

### Database Issues

```bash
# Reset database if corrupted
python scripts/init_db.py --reset

# Or reset the entire development environment
just dev-reset

# Verify database manually
python scripts/init_db.py --verify-only
```

### Common Errors

**"Database connection failed"**:

- Ensure PostgreSQL is running: `just dev`
- Check database credentials in `.env`
- Try resetting: `just dev-reset`

**"Discord connection failed"**:

- Verify Discord token in `.env`
- Check bot permissions in Discord server
- Ensure bot is added to the target server

This scripts directory provides database initialization for your Discord bot
development!
