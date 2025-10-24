"""
Logging middleware for tracking all updates.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
import structlog

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """Middleware for logging all incoming updates."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery | ChatMemberUpdated,
        data: Dict[str, Any]
    ) -> Any:
        """Log the update and pass it to handler."""

        # Determine event type and extract info
        if isinstance(event, Message):
            logger.info(
                "message_received",
                chat_id=event.chat.id,
                user_id=event.from_user.id if event.from_user else None,
                message_id=event.message_id,
                text=event.text[:100] if event.text else None,
                content_type=event.content_type
            )
        elif isinstance(event, CallbackQuery):
            logger.info(
                "callback_query_received",
                chat_id=event.message.chat.id if event.message else None,
                user_id=event.from_user.id,
                callback_data=event.data
            )
        elif isinstance(event, ChatMemberUpdated):
            logger.info(
                "chat_member_updated",
                chat_id=event.chat.id,
                user_id=event.from_user.id if event.from_user else None,
                new_status=event.new_chat_member.status if event.new_chat_member else None
            )

        # Execute handler
        try:
            result = await handler(event, data)
            return result
        except Exception as e:
            logger.error(
                "handler_error",
                error=str(e),
                error_type=type(e).__name__,
                event_type=type(event).__name__
            )
            raise
