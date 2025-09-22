FROM python:3.11-slim

# Install system dependencies for PostgreSQL
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy the source code and build files
COPY . .

# Install the package with all dependencies using UV
RUN uv pip install --system --no-cache .

# Create a non-root user and switch to it
RUN useradd -m botuser
USER botuser

# Set UV to not use virtual environments since we installed system-wide
ENV UV_SYSTEM_PYTHON=1

# Command to run the bot using the installed entry point
CMD ["mobo-run"]