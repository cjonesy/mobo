"""Type definitions for the Discord bot."""

import io
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotFile:
    """Represents a file to be sent with a Discord message."""

    content: bytes | io.BytesIO
    filename: str
    description: Optional[str] = None


@dataclass
class BotResponse:
    """Structured response from the bot containing text and files."""

    text: str
    files: Optional[list[BotFile]] = None

    def __post_init__(self) -> None:
        if self.files is None:
            self.files = []

    def add_file(
        self,
        content: bytes | io.BytesIO,
        filename: str,
        description: Optional[str] = None,
    ) -> None:
        """Add a file to the response."""
        if self.files is None:
            self.files = []
        self.files.append(
            BotFile(content=content, filename=filename, description=description)
        )

    def has_files(self) -> bool:
        """Check if response has any files."""
        return self.files is not None and len(self.files) > 0
