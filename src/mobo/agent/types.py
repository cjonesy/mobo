"""Type definitions for the Discord bot."""

from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class BotFile:
    """Represents a file URL to be sent with a Discord message."""

    url: str
    description: Optional[str] = None


@dataclass
class BotResponse:
    """Structured response from the bot containing text and files."""

    text: str
    files: Optional[list[BotFile]] = None
    _temp_files: Optional[list[Any]] = None

    def __post_init__(self) -> None:
        if self.files is None:
            self.files = []

    def add_file(
        self,
        url: str,
        description: Optional[str] = None,
    ) -> None:
        """Add a file URL to the response."""
        if self.files is None:
            self.files = []
        self.files.append(
            BotFile(
                url=url,
                description=description,
            )
        )

    def has_files(self) -> bool:
        """Check if response has any files."""
        return self.files is not None and len(self.files) > 0
