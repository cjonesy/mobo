"""
Event handlers for Discord client.

This module contains specialized handlers for different types of Discord events
and error scenarios, keeping the main client clean and focused.
"""

import logging
import tempfile
from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass

import discord
import httpx

from ..core.workflow import execute_workflow, format_workflow_summary
from ..tools.discord_context import set_discord_context, clear_discord_context

logger = logging.getLogger(__name__)


class MessageResult(Enum):
    """Result of message processing."""

    NOT_HANDLED = "not_handled"  # Bot chose not to respond
    PROCESSED = "processed"  # Message was processed and response sent
    ERROR = "error"  # Error occurred during processing


@dataclass
class ProcessingContext:
    """Context needed for message processing."""

    workflow: Any
    bot_user: discord.User
    debug_mode: bool
    record_execution_time: callable
    client: discord.Client


class MessageProcessor:
    """
    Handles the complete message processing pipeline.

    This service encapsulates all message handling logic, from determining
    whether to respond through sending the final response, making the
    main client much simpler.
    """

    def __init__(self, context: ProcessingContext):
        self.context = context

    async def handle_message(self, message: discord.Message) -> MessageResult:
        """
        Handle a Discord message through the complete pipeline.

        Args:
            message: Discord message to process

        Returns:
            MessageResult indicating what happened
        """
        try:
            # Step 1: Determine if we should respond
            should_respond, reason = await self._should_respond(message)
            if not should_respond:
                logger.info(f"🚫 Not responding to {message.author.name}: {reason}")
                return MessageResult.NOT_HANDLED

            logger.info(
                f"📨 Processing message from {message.author.name}: {message.content[:50]}..."
            )

            # Step 2: Process the message
            async with message.channel.typing():
                response_text, response_files, execution_time = (
                    await self._process_message(message)
                )

            # Step 3: Send response if we have content
            if response_text and response_text.strip() or response_files:
                await self._send_response(message, response_text, response_files)
                logger.info(f"✅ Sent response to {message.author.name}")

                # Record execution time
                self.context.record_execution_time(execution_time)

                return MessageResult.PROCESSED
            else:
                logger.info(
                    f"🔇 Bot staying silent for message from {message.author.name}"
                )
                return MessageResult.NOT_HANDLED

        except Exception as e:
            logger.exception(
                f"❌ Error processing message from {message.author.name}: {e}"
            )

            # Don't send error response
            logger.info(f"🔇 Bot staying silent due to processing error")

            return MessageResult.ERROR

    async def _should_respond(self, message: discord.Message) -> tuple[bool, str]:
        """Determine whether the bot should respond to a message."""
        # Ignore bot users
        if message.author.bot:
            return False, "Message from a bot"

        # Ignore messages from the bot itself
        if message.author == self.context.bot_user:
            return False, "Message from bot itself"

        # DMs: always respond
        if message.guild is None:
            return True, "Direct message"

        # In guilds: respond if mentioned
        try:
            if self.context.bot_user and self.context.bot_user in message.mentions:
                return True, "Bot was mentioned"
        except Exception:
            pass

        # Or if it's a reply to the bot
        try:
            if message.reference and message.reference.resolved:
                referenced = message.reference.resolved
                if (
                    isinstance(referenced, discord.Message)
                    and referenced.author == self.context.bot_user
                ):
                    return True, "Reply to the bot"
        except Exception:
            pass

        return False, "No bot mention or reply in guild channel"

    async def _process_message(
        self, message: discord.Message
    ) -> tuple[str, list[Dict[str, Any]], float]:
        """
        Process a message through the workflow.

        Returns:
            Tuple of (response_text, response_files, execution_time)
        """
        if not self.context.workflow:
            logger.error("❌ Workflow not initialized")
            return None, [], 0.0

        # Clean the message content
        cleaned_content = self._clean_message_content(message.content)

        # Handle empty messages (mentions with no content)
        if not cleaned_content.strip():
            cleaned_content = await self._handle_mention_only_message(message)

        # Set Discord context for tools
        set_discord_context(
            guild_id=str(message.guild.id) if message.guild else None,
            channel_id=str(message.channel.id),
            user_id=str(self.context.bot_user.id),
            message_author_id=str(message.author.id),
            client_user=self.context.bot_user,
            message=message,
            client=self.context.client,
        )

        try:
            # Execute the workflow
            final_state = await execute_workflow(
                workflow=self.context.workflow,
                user_message=cleaned_content,
                user_id=str(message.author.id),
                channel_id=str(message.channel.id),
            )
        finally:
            # Clear context after workflow execution
            clear_discord_context()

        execution_time = final_state["execution_time"]

        # Log workflow summary in debug mode
        if self.context.debug_mode:
            logger.debug(
                f"🔄 Workflow Summary:\n{format_workflow_summary(final_state)}"
            )

        # Format response
        response_text = final_state.get("final_response")
        response_files = []

        # Check for artifacts from tools (images, files, etc.)
        preserved_artifacts = final_state.get("extracted_artifacts", [])

        for artifact in preserved_artifacts:
            # Process image artifacts
            if isinstance(artifact, dict) and artifact.get("type") == "image":
                response_files.append(
                    {
                        "url": artifact["url"],
                        "description": "Generated image",
                        "filename": artifact["filename"],
                        "extension": artifact["extension"],
                    }
                )

        return response_text, response_files, execution_time

    async def _prepare_discord_files(
        self, file_data: list[Dict[str, Any]]
    ) -> tuple[list[discord.File], list[tempfile.NamedTemporaryFile]]:
        """
        Download and prepare files for Discord upload.

        Args:
            file_data: List of file info dicts with url, filename, extension

        Returns:
            Tuple of (discord_files, temp_files) for upload and cleanup
        """
        discord_files: list[discord.File] = []
        temp_files: list[tempfile.NamedTemporaryFile] = []

        for file_info in file_data:
            try:
                async with httpx.AsyncClient() as client:
                    file_response = await client.get(file_info["url"])
                    if file_response.status_code == 200:
                        temp_file = tempfile.NamedTemporaryFile(
                            suffix=file_info["extension"], delete=False
                        )
                        temp_file.write(file_response.content)
                        temp_file.flush()

                        discord_file = discord.File(
                            temp_file.name, filename=file_info["filename"]
                        )
                        discord_files.append(discord_file)
                        temp_files.append(temp_file)

            except Exception as e:
                logger.exception(f"Error preparing file attachment: {e}")

        return discord_files, temp_files

    async def _send_response(
        self,
        original_message: discord.Message,
        text: str,
        file_data: list[Dict[str, Any]],
    ):
        """Send the bot's response to Discord."""
        # Prepare Discord files for upload
        discord_files, temp_files = await self._prepare_discord_files(file_data)

        try:
            if discord_files:
                await original_message.reply(text, files=discord_files)
            else:
                await original_message.reply(text)
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    temp_file.close()
                except Exception:
                    pass

    def _clean_message_content(self, content: str) -> str:
        """Clean message content by removing the bot mention and trimming whitespace."""
        if not content:
            return ""

        bot_user = self.context.bot_user
        cleaned = content
        if bot_user:
            # Remove both mention formats <@id> and <@!id>
            mention_plain = f"<@{bot_user.id}>"
            mention_nick = f"<@!{bot_user.id}>"
            cleaned = cleaned.replace(mention_plain, "").replace(mention_nick, "")

        return cleaned.strip()

    async def _handle_mention_only_message(self, message: discord.Message) -> str:
        """Handle messages that only mention the bot with no content."""
        try:
            # Get conversation context
            context_messages = []
            async for msg in message.channel.history(limit=10, before=message):
                if not msg.author.bot and msg.content.strip():
                    context_messages.append(f"{msg.author.display_name}: {msg.content}")
                if len(context_messages) >= 3:  # Limit context
                    break

            if context_messages:
                context_messages.reverse()  # Chronological order
                context = "\n".join(context_messages)
                return f"[User mentioned me without a message. Recent conversation:]\n{context}"
            else:
                return "[User mentioned me without a message. No recent conversation context.]"

        except Exception as e:
            logger.exception(f"Error getting mention context: {e}")
            return "[User mentioned me without a message, but I couldn't get context.]"


class ErrorHandler:
    """
    Handles various error scenarios and provides appropriate responses.

    This class manages different types of errors that can occur during
    bot operation and provides appropriate user-facing responses.
    """

    def __init__(self):
        self.error_counts = {}  # Track error frequency

    async def handle_message_error(self, message: discord.Message, error: Exception):
        """
        Handle errors that occur during message processing.

        Args:
            message: The message that caused the error
            error: The exception that occurred
        """
        error_type = type(error).__name__
        self._increment_error_count(error_type)

        logger.error(f"Message processing error for {message.author.name}: {error}")

        # Log error without sending response
        logger.info(f"🔇 Bot staying silent due to message error")

    async def handle_client_error(self, event: str, args: tuple, kwargs: dict):
        """
        Handle Discord client-level errors.

        Args:
            event: Discord event name where error occurred
            args: Event arguments
            kwargs: Event keyword arguments
        """
        logger.error(f"Discord client error in {event}: {args}, {kwargs}")

        # You could implement specific handling for different event types
        if event == "on_guild_join":
            logger.error("Error processing guild join")
        elif event == "on_message":
            logger.error("Error in message event handler")

        self._increment_error_count(f"client_{event}")

    async def handle_workflow_error(self, user_id: str, error: Exception) -> None:
        """
        Handle errors from the LangGraph workflow.

        Args:
            user_id: Discord user ID
            error: The workflow error

        Returns:
            None - bot stays silent on workflow errors
        """
        error_type = type(error).__name__
        self._increment_error_count(f"workflow_{error_type}")

        logger.error(f"Workflow error for user {user_id}: {error}")

        # Log error without response
        return None

    def _increment_error_count(self, error_type: str):
        """Track error frequency for monitoring."""
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1

        # Log if error is becoming frequent
        if self.error_counts[error_type] % 10 == 0:
            logger.warning(
                f"Error type '{error_type}' has occurred {self.error_counts[error_type]} times"
            )

    def get_error_summary(self) -> dict:
        """Get summary of errors encountered."""
        return self.error_counts.copy()


class AdminHandler:
    """
    Handles admin-specific commands and functionality.

    This class manages commands that only administrators can use,
    such as bot management, debugging, and configuration changes.
    """

    def __init__(self, settings, error_handler: Optional[ErrorHandler] = None):
        self.settings = settings
        self.error_handler = error_handler

    async def handle_admin_command(self, message: discord.Message) -> Optional[str]:
        """
        Handle admin commands if user has permissions.

        Args:
            message: Discord message with potential admin command

        Returns:
            Response string if command was handled, None otherwise
        """
        user_id = str(message.author.id)

        # Check if user is admin
        if not self.settings.is_admin(user_id):
            return None

        content = message.content.strip().lower()

        # Handle different admin commands
        if content.startswith("!errors"):
            return await self._handle_errors_command()
        elif content.startswith("!model"):
            return await self._handle_model_command(content)
        elif content.startswith("!reload"):
            return await self._handle_reload_command()
        elif content.startswith("!debug"):
            return await self._handle_debug_command(content)

        return None

    async def _handle_errors_command(self) -> str:
        """Handle !errors admin command."""
        if not self.error_handler:
            return "Error handler not available."

        error_summary = self.error_handler.get_error_summary()

        if not error_summary:
            return "✅ No errors recorded!"

        error_lines = [f"**Error Summary:**"]
        for error_type, count in sorted(
            error_summary.items(), key=lambda x: x[1], reverse=True
        ):
            error_lines.append(f"• {error_type}: {count}")

        return "\n".join(error_lines)

    async def _handle_model_command(self, content: str) -> str:
        """Handle !model admin command."""
        parts = content.split(maxsplit=1)
        if len(parts) < 2:
            return f"Current model:\n• Chatbot: {self.settings.chatbot_model}\n• Image: {self.settings.image_model}"

        new_model = parts[1].strip()

        # For now, just return the command - full implementation would update config
        return f"Would change model to: {new_model}\n(Full implementation needed)"

    async def _handle_reload_command(self) -> str:
        """Handle !reload admin command."""
        # For now, just return status - full implementation would reload components
        return "🔄 Reload command received (Full implementation needed)"

    async def _handle_debug_command(self, content: str) -> str:
        """Handle !debug admin command."""
        parts = content.split(maxsplit=1)
        if len(parts) < 2:
            return f"Debug mode: {'ON' if self.settings.debug_mode else 'OFF'}"

        action = parts[1].strip().lower()
        if action in ["on", "true", "enable"]:
            self.settings.debug_mode = True
            return "🐛 Debug mode enabled"
        elif action in ["off", "false", "disable"]:
            self.settings.debug_mode = False
            return "🐛 Debug mode disabled"
        else:
            return "Usage: !debug [on|off]"
