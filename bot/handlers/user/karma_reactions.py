"""
Karma system based on message reactions.
"""

from aiogram import Router, Bot
from aiogram.types import MessageReactionUpdated, ReactionTypeEmoji
from datetime import datetime, timedelta
import structlog

from bot.database import models

logger = structlog.get_logger(__name__)
router = Router(name="karma_reactions")

# Positive reactions: +1 karma
POSITIVE_REACTIONS = ["👍", "👌", "❤", "🔥", "🎉", "❤️"]

# Negative reactions: -1 karma
NEGATIVE_REACTIONS = ["👎", "💩", "🤮"]

# Cooldown in hours
KARMA_COOLDOWN_HOURS = 12

# Anti ping-pong protection window (minutes)
PING_PONG_WINDOW_MINUTES = 30


@router.message_reaction(lambda r: r.chat.type in ["group", "supergroup"])
async def handle_reaction(event: MessageReactionUpdated, bot: Bot):
    """Handle message reactions for karma system."""
    chat_id = event.chat.id
    from_user_id = event.user.id

    # Get message author from message_log
    to_user_id = await models.db.fetchval(
        """
        SELECT user_id FROM message_log
        WHERE chat_id = $1 AND message_id = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        chat_id, event.message_id
    )

    if not to_user_id:
        logger.debug("message_author_not_found", chat_id=chat_id, message_id=event.message_id)
        return

    # Check if karma is enabled
    settings = await models.get_chat_settings(chat_id)
    if not settings.get("karma", {}).get("enabled", True):
        return

    # Cannot give karma to yourself
    if from_user_id == to_user_id:
        return

    # Determine karma delta based on reactions
    old_reactions = set()
    new_reactions = set()

    for reaction in event.old_reaction:
        if isinstance(reaction, ReactionTypeEmoji):
            old_reactions.add(reaction.emoji)

    for reaction in event.new_reaction:
        if isinstance(reaction, ReactionTypeEmoji):
            new_reactions.add(reaction.emoji)

    # Calculate what changed
    added_reactions = new_reactions - old_reactions
    removed_reactions = old_reactions - new_reactions

    karma_delta = 0

    # Process added reactions
    for emoji in added_reactions:
        if emoji in POSITIVE_REACTIONS:
            karma_delta += 1
        elif emoji in NEGATIVE_REACTIONS:
            karma_delta -= 1

    # Process removed reactions (reverse the karma)
    for emoji in removed_reactions:
        if emoji in POSITIVE_REACTIONS:
            karma_delta -= 1
        elif emoji in NEGATIVE_REACTIONS:
            karma_delta += 1

    if karma_delta == 0:
        return

    # Check cooldown
    cooldown_ok = await models.check_karma_cooldown(
        chat_id,
        from_user_id,
        to_user_id,
        hours=KARMA_COOLDOWN_HOURS
    )

    if not cooldown_ok:
        logger.debug(
            "karma_cooldown_active",
            chat_id=chat_id,
            from_user=from_user_id,
            to_user=to_user_id
        )
        return

    # Check anti ping-pong (A gives B, B gives A within short time)
    ping_pong_check = await check_ping_pong(
        chat_id,
        from_user_id,
        to_user_id,
        minutes=PING_PONG_WINDOW_MINUTES
    )

    if not ping_pong_check:
        logger.debug(
            "karma_ping_pong_detected",
            chat_id=chat_id,
            from_user=from_user_id,
            to_user=to_user_id
        )
        return

    # Add karma event
    reason = "reaction_" + ("+1" if karma_delta > 0 else "-1")
    await models.add_karma_event(
        chat_id,
        from_user_id,
        to_user_id,
        karma_delta,
        reason=reason
    )

    # Get new karma value
    new_karma = await models.get_karma(chat_id, to_user_id)

    # Check if notifications are enabled
    if settings.get("karma", {}).get("notify_on_change", True):
        # Get user display names
        from_user_name = await models.get_display_name(chat_id, from_user_id)
        to_user_name = await models.get_display_name(chat_id, to_user_id)

        # Send notification to chat
        emoji = "👍" if karma_delta > 0 else "👎"
        action = "повысили" if karma_delta > 0 else "понизили"

        notification_text = (
            f"{emoji} <b>{action.capitalize()}!</b>\n\n"
            f"<b>{from_user_name}</b> {action} рейтинг пользователя <b>{to_user_name}</b>.\n"
            f"Теперь его рейтинг: <b>{new_karma}</b> ❤️"
        )

        try:
            await bot.send_message(chat_id, notification_text)
        except Exception as e:
            logger.error("failed_to_send_karma_notification", error=str(e))

    logger.info(
        "karma_by_reaction",
        chat_id=chat_id,
        from_user=from_user_id,
        to_user=to_user_id,
        delta=karma_delta,
        new_karma=new_karma
    )


async def check_ping_pong(
    chat_id: int,
    from_user_id: int,
    to_user_id: int,
    minutes: int
) -> bool:
    """
    Check if there's a recent karma event from to_user to from_user (ping-pong).

    Returns:
        True if ping-pong is NOT detected (safe to proceed)
        False if ping-pong is detected (block karma)
    """
    since = datetime.now() - timedelta(minutes=minutes)

    # Check if to_user gave karma to from_user recently
    reverse_karma = await models.db.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM karma_events
            WHERE chat_id = $1
            AND from_user_id = $2
            AND to_user_id = $3
            AND created_at > $4
        )
        """,
        chat_id, to_user_id, from_user_id, since
    )

    return not reverse_karma
