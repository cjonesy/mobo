# Testing Strategy

## Database Requirements

The bot requires PostgreSQL with pgvector for vector search capabilities. All
tests run against PostgreSQL to ensure compatibility with the production
environment.

## Database Setup

### 1. Install PostgreSQL and pgvector

```bash
# macOS
brew install postgresql pgvector

# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib
# Follow pgvector installation guide for your system

# Start PostgreSQL
brew services start postgresql  # macOS
sudo systemctl start postgresql  # Linux
```

### 2. Create Test Database

```sql
-- Connect to PostgreSQL
psql postgres

-- Create test database and user
CREATE DATABASE mobo_test;
CREATE USER mobo_test WITH PASSWORD 'test_password';
GRANT ALL PRIVILEGES ON DATABASE mobo_test TO mobo_test;

-- Connect to test database
\c mobo_test

-- Enable pgvector extension
CREATE EXTENSION vector;
```

### 3. Set Environment Variable

```bash
# Default (if using above setup)
export TEST_POSTGRES_URL="postgresql+asyncpg://mobo_test:test_password@localhost:5432/mobo_test"

# Or customize for your setup
export TEST_POSTGRES_URL="postgresql+asyncpg://username:password@host:port/database"
```

## Running Tests

### All Tests

```bash
# Run complete test suite
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=bot

# Run specific test file
uv run pytest tests/test_memory.py -v
```

### Test Categories

```bash
# Run only memory tests
uv run pytest tests/test_memory.py

# Run only tool tests
uv run pytest tests/test_tools.py

# Run only workflow tests
uv run pytest tests/test_workflow.py
```

### Test Markers

```bash
# Skip slow tests during development
uv run pytest tests/ -m "not slow"

# Run only slow/integration tests
uv run pytest tests/ -m "slow"
```

## Test Database Management

The test fixture automatically:

- Creates the pgvector extension
- Creates all database tables
- Provides isolated sessions for each test
- Cleans up after tests complete

### Manual Database Reset

```bash
# If you need to reset the test database
psql -c "DROP DATABASE mobo_test; CREATE DATABASE mobo_test;" postgres
psql -c "CREATE EXTENSION vector;" mobo_test
```

## Current Test Coverage

| Component             | Status     | Description                                   |
| --------------------- | ---------- | --------------------------------------------- |
| **Memory Models**     | ✅ Full    | Database schema, relationships, validation    |
| **Tools System**      | ✅ Full    | Base classes, parameter validation, API tools |
| **Workflow Engine**   | ✅ Core    | State management, node execution              |
| **Vector Operations** | ✅ Full    | Embeddings, similarity search                 |
| **Integration**       | ⚠️ Partial | End-to-end workflow testing                   |

## Troubleshooting

### "PostgreSQL test database not available"

- Ensure PostgreSQL is running
- Check `TEST_POSTGRES_URL` environment variable
- Verify database exists and pgvector extension is installed
- Check connection permissions

### "CREATE EXTENSION vector" errors

- Install pgvector extension for your PostgreSQL version
- Ensure user has CREATE privileges on the database

### Connection timeout/refused

- Check PostgreSQL is running on the correct port
- Verify firewall settings
- For Docker: ensure container is accessible

## CI/CD Integration

For automated testing in CI/CD:

```yaml
# Example GitHub Actions setup
services:
  postgres:
    image: pgvector/pgvector:pg16
    env:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: mobo_test
    options: >-
      --health-cmd pg_isready --health-interval 10s --health-timeout 5s
      --health-retries 5

env:
  TEST_POSTGRES_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/mobo_test
```

## Performance Considerations

- Tests create/drop tables for each session
- Consider using database transactions for test isolation in large test suites
- Vector operations may be slower than basic CRUD tests
- Mark integration tests with `@pytest.mark.slow` for optional skipping
