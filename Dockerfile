FROM python:3.11-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy UV configuration files first for better layer caching
COPY pyproject.toml .

# Install dependencies using UV
RUN uv pip install --system --no-cache .

# Copy the application code
COPY . .

# Create a non-root user and switch to it
RUN useradd -m botuser
USER botuser

# Command to run the bot
CMD ["python", "-m", "src.mobo"]