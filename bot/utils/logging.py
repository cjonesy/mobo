"""
Logging configuration and utilities for the Discord bot.

This module provides structured logging setup with proper formatting,
log levels, and integration with external services.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds colors to log levels for console output.

    This makes logs easier to read during development and debugging.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        """Format the log record with colors."""
        # Get the original formatted message
        message = super().format(record)

        # Add color codes
        level_name = record.levelname
        if level_name in self.COLORS:
            colored_level = (
                f"{self.COLORS[level_name]}{level_name}{self.COLORS['RESET']}"
            )
            message = message.replace(level_name, colored_level, 1)

        return message


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    This is useful for production environments where logs are processed
    by log aggregation systems like ELK stack or CloudWatch.
    """

    def format(self, record):
        """Format the log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
            ):
                log_entry[key] = value

        return json.dumps(log_entry)


class BotLoggerAdapter(logging.LoggerAdapter):
    """
    Custom logger adapter that adds bot-specific context to log messages.

    This automatically includes information like user IDs, channel IDs,
    and guild IDs in log messages for better traceability.
    """

    def process(self, msg, kwargs):
        """Add extra context to log messages."""
        extra = kwargs.get("extra", {})

        # Add bot context if available
        if hasattr(self, "bot_context"):
            extra.update(self.bot_context)

        # Add default context from adapter
        extra.update(self.extra)

        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(
    level: str = "INFO",
    log_format: str = "colored",
    log_file: Optional[str] = None,
    json_logs: bool = False,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Set up logging configuration for the bot.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ("colored", "simple", "detailed")
        log_file: Optional file path for file logging
        json_logs: Whether to use JSON formatting for structured logs
        max_file_size: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    if json_logs:
        console_formatter = JSONFormatter()
    else:
        if log_format == "colored":
            console_formatter = ColoredFormatter(
                "%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        elif log_format == "detailed":
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        else:  # simple
            console_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
            )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Set up file handler if requested
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_file_size, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)

        if json_logs:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Configure specific loggers
    _configure_external_loggers()

    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(f"🔧 Logging configured - Level: {level}, Format: {log_format}")
    if log_file:
        logger.info(f"📁 File logging enabled: {log_file}")


def _configure_external_loggers():
    """Configure log levels for external libraries."""
    # Discord.py can be quite verbose
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)

    # HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # OpenAI can be verbose
    logging.getLogger("openai").setLevel(logging.WARNING)

    # Asyncio debugging can be noisy
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # SQLAlchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)


def get_logger(name: str, **context) -> BotLoggerAdapter:
    """
    Get a logger with bot-specific context.

    Args:
        name: Logger name (usually __name__)
        **context: Additional context to include in all log messages

    Returns:
        Configured logger adapter
    """
    logger = logging.getLogger(name)
    return BotLoggerAdapter(logger, context)


def log_function_call(include_args: bool = False, include_result: bool = False):
    """
    Decorator to log function calls.

    Args:
        include_args: Whether to log function arguments
        include_result: Whether to log function result

    Returns:
        Decorator function
    """

    def decorator(func):
        import functools

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)

            # Log function entry
            if include_args:
                logger.debug(
                    f"🔄 Calling {func.__name__} with args={args}, kwargs={kwargs}"
                )
            else:
                logger.debug(f"🔄 Calling {func.__name__}")

            try:
                result = await func(*args, **kwargs)

                # Log function exit
                if include_result:
                    logger.debug(f"✅ {func.__name__} returned: {result}")
                else:
                    logger.debug(f"✅ {func.__name__} completed successfully")

                return result

            except Exception as e:
                logger.error(f"❌ {func.__name__} failed: {e}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)

            # Log function entry
            if include_args:
                logger.debug(
                    f"🔄 Calling {func.__name__} with args={args}, kwargs={kwargs}"
                )
            else:
                logger.debug(f"🔄 Calling {func.__name__}")

            try:
                result = func(*args, **kwargs)

                # Log function exit
                if include_result:
                    logger.debug(f"✅ {func.__name__} returned: {result}")
                else:
                    logger.debug(f"✅ {func.__name__} completed successfully")

                return result

            except Exception as e:
                logger.error(f"❌ {func.__name__} failed: {e}")
                raise

        # Return appropriate wrapper based on whether function is async
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def log_execution_time(threshold_ms: float = 100.0):
    """
    Decorator to log slow function executions.

    Args:
        threshold_ms: Log warning if execution takes longer than this (milliseconds)

    Returns:
        Decorator function
    """

    def decorator(func):
        import functools
        import time

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000

                if execution_time > threshold_ms:
                    logger.warning(
                        f"⏱️ {func.__name__} took {execution_time:.1f}ms (threshold: {threshold_ms}ms)"
                    )
                else:
                    logger.debug(f"⏱️ {func.__name__} took {execution_time:.1f}ms")

                return result

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(
                    f"❌ {func.__name__} failed after {execution_time:.1f}ms: {e}"
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000

                if execution_time > threshold_ms:
                    logger.warning(
                        f"⏱️ {func.__name__} took {execution_time:.1f}ms (threshold: {threshold_ms}ms)"
                    )
                else:
                    logger.debug(f"⏱️ {func.__name__} took {execution_time:.1f}ms")

                return result

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(
                    f"❌ {func.__name__} failed after {execution_time:.1f}ms: {e}"
                )
                raise

        # Return appropriate wrapper
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class LogContext:
    """
    Context manager for adding temporary context to log messages.

    Example:
        with LogContext(user_id="123", channel_id="456"):
            logger.info("Processing message")  # Will include user_id and channel_id
    """

    def __init__(self, **context):
        self.context = context
        self.old_factory = None

    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def configure_development_logging():
    """Quick setup for development with colored output and debug level."""
    setup_logging(level="DEBUG", log_format="colored")


def configure_production_logging(log_file: str = "bot.log"):
    """Quick setup for production with file logging and JSON format."""
    setup_logging(level="INFO", log_format="simple", log_file=log_file, json_logs=True)


def get_log_stats() -> Dict[str, Any]:
    """
    Get statistics about current logging configuration.

    Returns:
        Dictionary with logging statistics
    """
    root_logger = logging.getLogger()

    stats = {
        "level": logging.getLevelName(root_logger.level),
        "handlers": [],
        "loggers": {},
    }

    # Handler information
    for handler in root_logger.handlers:
        handler_info = {
            "type": type(handler).__name__,
            "level": logging.getLevelName(handler.level),
            "formatter": (
                type(handler.formatter).__name__ if handler.formatter else None
            ),
        }

        if hasattr(handler, "baseFilename"):
            handler_info["file"] = handler.baseFilename

        stats["handlers"].append(handler_info)

    # Count loggers by level
    for name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            level_name = logging.getLevelName(logger.level)
            if level_name not in stats["loggers"]:
                stats["loggers"][level_name] = 0
            stats["loggers"][level_name] += 1

    return stats


def silence_noisy_loggers():
    """Silence commonly noisy loggers for cleaner output."""
    noisy_loggers = [
        "discord.client",
        "discord.gateway",
        "discord.http",
        "httpx",
        "httpcore",
        "openai._base_client",
        "asyncio",
        "urllib3",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)
