"""
Pydantic schemas for structured tool responses.

These models provide type-safe, validated responses from tools,
replacing manual JSON string construction.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ToolResponse(BaseModel):
    """Base response model for all tool operations."""

    success: bool = Field(description="Whether the operation was successful")
    error: Optional[str] = Field(
        default=None, description="Error message if operation failed"
    )


class EmojiData(BaseModel):
    """Individual emoji information."""

    name: str = Field(description="Emoji name for use in reactions")
    message_embed_format: str = Field(
        description="Ready-to-use format for message embedding"
    )
    reaction_format: str = Field(description="Ready-to-use format for reactions")
    id: str = Field(description="Discord emoji ID")


class EmojiListResponse(ToolResponse):
    """Response for listing available emoji."""

    emojis: List[EmojiData] = Field(
        default_factory=list, description="Array of emoji objects"
    )
    total: int = Field(default=0, description="Total number of emoji available")


class UserData(BaseModel):
    """Individual user information."""

    name: str = Field(description="User's username")
    id: str = Field(description="Discord user ID")
    display_name: str = Field(description="Server-specific display name")
    global_name: Optional[str] = Field(description="Global display name")
    nickname: Optional[str] = Field(description="Server-specific nickname")
    mention: str = Field(description="Mention format (@user)")
    status: str = Field(description="Online status (online/idle/dnd/offline/unknown)")


class UserListResponse(ToolResponse):
    """Response for listing channel users."""

    users: List[UserData] = Field(
        default_factory=list, description="Array of human users"
    )
    bots: List[UserData] = Field(default_factory=list, description="Array of bot users")
    total: int = Field(default=0, description="Total number of users and bots")


class UserProfile(BaseModel):
    """Detailed user profile information."""

    name: str = Field(description="User's display name")
    id: str = Field(description="Discord user ID")
    display_name: str = Field(description="Server-specific display name")
    global_name: Optional[str] = Field(description="Global display name")
    mention: str = Field(description="Mention format (@user)")
    nickname: Optional[str] = Field(description="Server-specific nickname")
    bot: bool = Field(description="True if user is a bot")
    joined_at: str = Field(description="When user joined this server (ISO format)")
    created_at: str = Field(description="When user account was created (ISO format)")
    roles: List[str] = Field(description="Array of role names the user has")
    status: str = Field(description="Online status (online/idle/dnd/offline)")
    avatar_url: str = Field(description="URL to user's avatar image")
    activity: str = Field(description="Current activity")


class UserProfileResponse(ToolResponse):
    """Response for getting user profile."""

    profile: Optional[UserProfile] = Field(
        default=None, description="User profile data"
    )


class StickerData(BaseModel):
    """Individual sticker information."""

    name: str = Field(description="Sticker name for use with send_sticker")
    id: str = Field(description="Discord sticker ID")
    description: str = Field(description="Description of what the sticker shows")


class StickerListResponse(ToolResponse):
    """Response for listing available stickers."""

    stickers: List[StickerData] = Field(
        default_factory=list, description="Array of available stickers"
    )


class SimpleResponse(ToolResponse):
    """Simple success/error response for operations that don't return data."""

    pass
