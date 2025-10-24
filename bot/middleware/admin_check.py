"""
Admin check middleware for moderation commands.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message
import structlog

from bot.database import models
from bot.config import settings

logger = structlog.get_logger(__name__)


class AdminCheckMiddleware(BaseMiddleware):
    """Middleware to check if user has admin/moderator rights."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Check admin rights and add to data."""

        if not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        chat_id = event.chat.id

        # Check if user is owner
        is_owner = user_id in settings.owner_ids

        # Check if user is staff (admin/moderator)
        user_role = None
        if chat_id < 0:  # Group chat
            user_role = await models.get_user_role(chat_id, user_id)

        # Add to data
        data["is_owner"] = is_owner
        data["user_role"] = user_role
        data["is_staff"] = is_owner or user_role is not None

        # Execute handler
        return await handler(event, data)
