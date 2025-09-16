# Run with `just <command>`

# Set shell
set shell := ["bash", "-c"]

# Default recipe - show available commands
default:
    @echo "📋 Available commands:"
    @just --list

# === DEVELOPMENT ===

# Start development environment (PostgreSQL in Docker, bot locally)
dev:
    @echo "🚀 Starting development environment..."
    @echo "🐘 Starting PostgreSQL in Docker..."
    docker-compose up -d postgres
    @echo "⏳ Waiting for PostgreSQL to be ready..."
    @i=1; while [ $i -le 30 ]; do \
        if docker-compose exec postgres pg_isready -U mobo >/dev/null 2>&1; then \
            echo "✅ PostgreSQL ready!"; \
            break; \
        fi; \
        if [ $i -eq 30 ]; then \
            echo "❌ PostgreSQL failed to start after 30 seconds"; \
            echo "🔍 Checking logs:"; \
            docker-compose logs postgres; \
            exit 1; \
        fi; \
        echo "  Attempt $i/30..."; \
        sleep 1; \
        i=$((i+1)); \
    done
    @echo "🗄️ Initializing database schema..."
    uv run python scripts/init_db.py
    @echo "🤖 Starting Discord bot locally..."
    uv run mobo-dev

# Stop development environment
dev-stop:
    @echo "🛑 Stopping development environment..."
    docker-compose down

# Restart development environment
dev-restart: dev-stop dev

# Show development logs
dev-logs:
    @echo "📋 PostgreSQL logs:"
    docker-compose logs postgres

# Connect to development database
dev-db:
    @echo "🐘 Connecting to development PostgreSQL..."
    docker-compose exec postgres psql -U mobo -d mobo

# Reset development database (clean slate)
dev-reset:
    @echo "🗑️  Resetting development database..."
    docker-compose down postgres
    docker volume rm mobo_postgres_data 2>/dev/null || true
    @echo "✅ Database reset complete. Run 'just dev' to start fresh."

# === SETUP & INSTALLATION ===

# Install UV dependency manager
install-uv:
    @echo "🔧 Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies with UV
install:
    @echo "📦 Installing dependencies with uv..."
    uv sync

# Run the bot locally (assumes external database)
run:
    @echo "🤖 Starting Discord bot locally..."
    uv run python -m mobo.main

# === TESTING & QUALITY ===

# Run tests
test:
    @echo "🧪 Running tests..."
    @if [ -d "tests" ]; then \
        uv run pytest tests/; \
    else \
        echo "💡 Create tests/ directory and add tests to enable this command"; \
    fi

# Lint code
lint:
    @echo "🔍 Linting code..."
    uv run ruff check --fix src/

# Format code
format:
    @echo "🎨 Formatting code..."
    uv run ruff format src/

# Type check code
typecheck:
    @echo "🔎 Type checking code..."
    uv run mypy src/

# Run all quality checks
check: lint typecheck test

# === DOCKER OPERATIONS ===

# Build docker image
build:
    @echo "🐳 Building Docker image..."
    docker-compose build

# Start full services with docker-compose (bot + postgres)
up:
    @echo "🚀 Starting all services with Docker..."
    docker-compose up -d

# Stop services
down:
    @echo "🛑 Stopping all services..."
    docker-compose down

# View logs from services
logs SERVICE="":
    @if [ "{{SERVICE}}" = "" ]; then \
        echo "📋 Showing all service logs..."; \
        docker-compose logs -f; \
    else \
        echo "📋 Showing logs for {{SERVICE}}..."; \
        docker-compose logs -f {{SERVICE}}; \
    fi

# === UTILITIES ===

# Clean up development environment
clean:
    @echo "🧹 Cleaning up..."
    docker-compose down
    docker system prune -f
    @echo "✅ Cleanup completed"
