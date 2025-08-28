#!/usr/bin/env python3
"""
Deployment helper script.

This script handles deployment tasks like building Docker images,
running health checks, and preparing the bot for production.
"""

import asyncio
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bot.config import get_settings, validate_required_settings, print_config_summary
from bot.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class DeploymentManager:
    """Handles deployment tasks and health checks."""

    def __init__(self):
        self.settings = get_settings()
        self.project_root = Path(__file__).parent.parent

    def run_command(
        self, command: str, check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run a shell command and return the result."""
        logger.info(f"🔧 Running: {command}")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=check,
            )

            if result.stdout:
                logger.debug(f"stdout: {result.stdout}")
            if result.stderr and result.returncode != 0:
                logger.error(f"stderr: {result.stderr}")

            return result

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Command failed: {e}")
            if e.stdout:
                logger.error(f"stdout: {e.stdout}")
            if e.stderr:
                logger.error(f"stderr: {e.stderr}")
            raise

    def check_dependencies(self) -> Dict[str, bool]:
        """Check that required dependencies are available."""
        logger.info("🔍 Checking dependencies...")

        checks = {}

        # Check Docker
        try:
            result = self.run_command("docker --version", check=False)
            checks["docker"] = result.returncode == 0
        except Exception:
            checks["docker"] = False

        # Check UV
        try:
            result = self.run_command("uv --version", check=False)
            checks["uv"] = result.returncode == 0
        except Exception:
            checks["uv"] = False

        # Check Git
        try:
            result = self.run_command("git --version", check=False)
            checks["git"] = result.returncode == 0
        except Exception:
            checks["git"] = False

        # Print results
        for tool, available in checks.items():
            status = "✅" if available else "❌"
            logger.info(f"  {tool}: {status}")

        return checks

    def build_docker_image(self, tag: Optional[str] = None) -> str:
        """Build Docker image for the bot."""
        if tag is None:
            tag = f"discord-bot:latest"

        logger.info(f"🐳 Building Docker image: {tag}")

        # Build the image
        self.run_command(f"docker build -t {tag} .")

        # Get image info
        result = self.run_command(
            f"docker images {tag} --format 'table {{.Repository}}:{{.Tag}}\\t{{.Size}}\\t{{.CreatedAt}}'"
        )
        logger.info(f"✅ Docker image built successfully")
        logger.info(f"Image info:\n{result.stdout}")

        return tag

    def run_tests(self):
        """Run the test suite."""
        logger.info("🧪 Running tests...")

        try:
            self.run_command("uv run pytest tests/ -v")
            logger.info("✅ All tests passed")
        except subprocess.CalledProcessError:
            logger.error("❌ Some tests failed")
            raise

    def lint_and_format(self):
        """Run linting and formatting."""
        logger.info("🎨 Running linting and formatting...")

        # Format with black
        self.run_command("uv run black bot/ scripts/")

        # Lint with ruff
        self.run_command("uv run ruff check bot/ scripts/ --fix")

        # Type check with mypy
        try:
            self.run_command("uv run mypy bot/")
            logger.info("✅ Type checking passed")
        except subprocess.CalledProcessError:
            logger.warning("⚠️ Type checking found issues (non-blocking)")

        logger.info("✅ Linting and formatting completed")

    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        logger.info("🏥 Performing health check...")

        health_status = {
            "config": False,
            "database": False,
            "apis": {},
            "overall": False,
        }

        try:
            # Check configuration
            validate_required_settings()
            health_status["config"] = True
            logger.info("✅ Configuration check passed")
        except Exception as e:
            logger.error(f"❌ Configuration check failed: {e}")

        # Check database connectivity
        try:
            from bot.memory.langgraph_memory import LangGraphMemory

            memory = LangGraphMemory(self.settings.database_url)
            await memory.initialize()

            # Test database operations - check if user profile can be created/retrieved
            test_profile = await memory.get_user_profile("health_check")
            if test_profile:
                health_status["database"] = True
                logger.info("✅ Database check passed")
            else:
                logger.error("❌ Database check failed: Could not retrieve test profile")

            await memory.close()

        except Exception as e:
            logger.error(f"❌ Database check failed: {e}")

        # Check external APIs
        health_status["apis"]["openrouter"] = await self._check_openrouter_api()

        if self.settings.openai_api_key.get_secret_value():
            health_status["apis"]["openai"] = await self._check_openai_api()

        if self.settings.giphy_api_key.get_secret_value():
            health_status["apis"]["giphy"] = await self._check_giphy_api()

        # Overall health
        health_status["overall"] = (
            health_status["config"]
            and health_status["database"]
            and health_status["apis"].get("openrouter", False)
        )

        return health_status

    async def _check_openrouter_api(self) -> bool:
        """Check OpenRouter API connectivity."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.settings.openrouter_base_url}/models",
                    headers={
                        "Authorization": f"Bearer {self.settings.openrouter_api_key.get_secret_value()}"
                    },
                )

                if response.status_code == 200:
                    logger.info("✅ OpenRouter API check passed")
                    return True
                else:
                    logger.error(
                        f"❌ OpenRouter API check failed: {response.status_code}"
                    )
                    return False

        except Exception as e:
            logger.error(f"❌ OpenRouter API check failed: {e}")
            return False

    async def _check_openai_api(self) -> bool:
        """Check OpenAI API connectivity."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value()
            )

            # Try to list models
            models = await client.models.list()

            if models.data:
                logger.info("✅ OpenAI API check passed")
                return True
            else:
                logger.error("❌ OpenAI API check failed: No models available")
                return False

        except Exception as e:
            logger.error(f"❌ OpenAI API check failed: {e}")
            return False

    async def _check_giphy_api(self) -> bool:
        """Check Giphy API connectivity."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.giphy.com/v1/gifs/trending",
                    params={
                        "api_key": self.settings.giphy_api_key.get_secret_value(),
                        "limit": 1,
                    },
                )

                if response.status_code == 200:
                    logger.info("✅ Giphy API check passed")
                    return True
                else:
                    logger.error(f"❌ Giphy API check failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"❌ Giphy API check failed: {e}")
            return False

    def create_production_env(self):
        """Create a production environment file template."""
        production_env = self.project_root / ".env.production"

        if production_env.exists():
            logger.warning("⚠️ .env.production already exists, backing up...")
            backup_path = production_env.with_suffix(
                f".production.backup.{int(time.time())}"
            )
            production_env.rename(backup_path)
            logger.info(f"📄 Backed up to: {backup_path}")

        template = """# ==============================================================================
# PRODUCTION ENVIRONMENT CONFIGURATION
# ==============================================================================
# This file contains production-ready configuration templates
# Fill in your actual values and rename to .env for production deployment

# ==============================================================================
# REQUIRED CONFIGURATION
# ==============================================================================

# Discord Bot Token
DISCORD_TOKEN=your_production_discord_token_here

# OpenRouter API Key
OPENROUTER_API_KEY=your_production_openrouter_key_here

# ==============================================================================
# LLM CONFIGURATION
# ==============================================================================

# Main Chatbot Model (needs tool calling capabilities)
CHATBOT_MODEL=openai/gpt-4o
CHATBOT_TEMPERATURE=0.7

# ==============================================================================
# PERSONALITY CONFIGURATION
# ==============================================================================

# Option 1: Direct prompt (recommended for production)
PERSONALITY_PROMPT="You are a helpful and friendly Discord bot assistant with a great sense of humor. You love helping users and making conversations engaging with images and GIFs when appropriate."

# Option 2: URL (for dynamic personality updates)
# PERSONALITY_PROMPT_URL=https://your-server.com/personality.txt

# ==============================================================================
# DATABASE CONFIGURATION (PRODUCTION)
# ==============================================================================

# PostgreSQL for production (recommended)
DATABASE_URL=postgresql://username:password@localhost:5432/discord_bot_prod

# Connection settings
DATABASE_ECHO=false
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# ==============================================================================
# EXTERNAL API KEYS
# ==============================================================================

# OpenAI API Key (for DALL-E image generation)
OPENAI_API_KEY=your_production_openai_key_here

# Giphy API Key (for GIF search)
GIPHY_API_KEY=your_production_giphy_key_here

# ==============================================================================
# PRODUCTION SETTINGS
# ==============================================================================

# Admin User IDs (comma-separated Discord user IDs)
ADMIN_USER_IDS=123456789012345678,987654321098765432

# Logging
LOG_LEVEL=INFO
DEBUG_MODE=false

# Bot behavior
MAX_BOT_RESPONSES=3

# ==============================================================================
# SECURITY NOTES
# ==============================================================================
# 1. Never commit this file to version control
# 2. Use strong, unique passwords for database
# 3. Rotate API keys regularly
# 4. Limit admin user IDs to trusted users only
# 5. Use environment-specific Discord tokens (dev vs prod bots)
"""

        production_env.write_text(template)
        logger.info(f"📄 Created production environment template: {production_env}")
        print(f"\nProduction environment template created at: {production_env}")
        print("Edit the file with your production values before deployment.")

    def deploy_docker(self, environment: str = "production"):
        """Deploy using Docker Compose."""
        logger.info(f"🚀 Deploying with Docker Compose (environment: {environment})")

        # Check if docker-compose.yml exists
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            logger.error("❌ docker-compose.yml not found")
            raise FileNotFoundError(
                "docker-compose.yml is required for Docker deployment"
            )

        # Build and deploy
        self.run_command("docker-compose down")
        self.run_command("docker-compose build")
        self.run_command("docker-compose up -d")

        # Wait for services to start
        logger.info("⏳ Waiting for services to start...")
        time.sleep(10)

        # Check service health
        result = self.run_command("docker-compose ps", check=False)
        logger.info(f"Service status:\n{result.stdout}")

        logger.info("✅ Docker deployment completed")

    def backup_database(self, backup_path: Optional[str] = None):
        """Create a database backup."""
        if not self.settings.is_postgresql():
            logger.warning("⚠️ Database backup only supported for PostgreSQL")
            return

        if backup_path is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_discord_bot_{timestamp}.sql"

        logger.info(f"💾 Creating database backup: {backup_path}")

        # Extract database info from URL
        db_url = self.settings.database_url
        # This is a simplified extraction - you might want to use urllib.parse for robustness

        self.run_command(f"pg_dump {db_url} > {backup_path}")
        logger.info(f"✅ Database backup created: {backup_path}")

    def print_deployment_summary(self):
        """Print a summary of deployment configuration."""
        print("\n🚀 Deployment Summary")
        print("=" * 50)
        print(f"Project Root: {self.project_root}")
        print(f"Database Type: PostgreSQL")
        print(f"Database URL: {self.settings.database_url}")
        print(f"Chatbot Model: {self.settings.chatbot_model}")
        print(f"Log Level: {self.settings.log_level}")
        print(f"Debug Mode: {self.settings.debug_mode}")
        print(f"Admin Users: {len(self.settings.admin_user_ids)} configured")

        # Check optional features
        features = []
        if self.settings.openai_api_key.get_secret_value():
            features.append("Image Generation (OpenAI)")
        if self.settings.giphy_api_key.get_secret_value():
            features.append("GIF Search (Giphy)")

        if features:
            print(f"Enabled Features: {', '.join(features)}")

        print()


async def main():
    """Main deployment function."""
    setup_logging()
    logger.info("🚀 Deployment script started")

    deployment_manager = DeploymentManager()

    try:
        # Check dependencies
        deps = deployment_manager.check_dependencies()
        missing_deps = [dep for dep, available in deps.items() if not available]

        if missing_deps:
            logger.warning(f"⚠️ Missing dependencies: {', '.join(missing_deps)}")

        # Run health check
        health_status = await deployment_manager.health_check()

        if health_status["overall"]:
            logger.info("✅ Health check passed - ready for deployment!")
        else:
            logger.error("❌ Health check failed - fix issues before deploying")
            sys.exit(1)

        # Print deployment summary
        deployment_manager.print_deployment_summary()

    except Exception as e:
        logger.error(f"❌ Deployment preparation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Deployment helper script")
    parser.add_argument(
        "--health-check", action="store_true", help="Run comprehensive health check"
    )
    parser.add_argument(
        "--build-docker",
        type=str,
        nargs="?",
        const="discord-bot:latest",
        help="Build Docker image with optional tag",
    )
    parser.add_argument("--test", action="store_true", help="Run test suite")
    parser.add_argument(
        "--lint", action="store_true", help="Run linting and formatting"
    )
    parser.add_argument(
        "--create-prod-env",
        action="store_true",
        help="Create production environment template",
    )
    parser.add_argument(
        "--deploy-docker", action="store_true", help="Deploy using Docker Compose"
    )
    parser.add_argument(
        "--backup-db",
        type=str,
        nargs="?",
        const=None,
        help="Create database backup (PostgreSQL only)",
    )
    parser.add_argument(
        "--full-deploy",
        action="store_true",
        help="Run full deployment pipeline (test, lint, build, deploy)",
    )

    args = parser.parse_args()

    deployment_manager = DeploymentManager()

    try:
        if args.health_check:

            async def health_check():
                setup_logging()
                health_status = await deployment_manager.health_check()

                print("\n🏥 Health Check Results:")
                print("=" * 30)
                print(f"Configuration: {'✅' if health_status['config'] else '❌'}")
                print(f"Database: {'✅' if health_status['database'] else '❌'}")

                for api, status in health_status["apis"].items():
                    print(f"{api.title()} API: {'✅' if status else '❌'}")

                print(
                    f"Overall: {'✅ HEALTHY' if health_status['overall'] else '❌ UNHEALTHY'}"
                )

            asyncio.run(health_check())

        elif args.build_docker:
            setup_logging()
            deployment_manager.build_docker_image(args.build_docker)

        elif args.test:
            setup_logging()
            deployment_manager.run_tests()

        elif args.lint:
            setup_logging()
            deployment_manager.lint_and_format()

        elif args.create_prod_env:
            setup_logging()
            deployment_manager.create_production_env()

        elif args.deploy_docker:
            setup_logging()
            deployment_manager.deploy_docker()

        elif args.backup_db is not None:
            setup_logging()
            deployment_manager.backup_database(args.backup_db)

        elif args.full_deploy:
            setup_logging()
            logger.info("🚀 Starting full deployment pipeline...")

            # Run tests
            deployment_manager.run_tests()

            # Lint and format
            deployment_manager.lint_and_format()

            # Build Docker image
            deployment_manager.build_docker_image()

            # Deploy
            deployment_manager.deploy_docker()

            # Final health check
            async def final_check():
                await asyncio.sleep(15)  # Wait for services
                health_status = await deployment_manager.health_check()
                if health_status["overall"]:
                    logger.info("✅ Full deployment completed successfully!")
                else:
                    logger.error("❌ Deployment completed but health check failed")
                    sys.exit(1)

            asyncio.run(final_check())

        else:
            asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("🛑 Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Deployment failed: {e}")
        sys.exit(1)
