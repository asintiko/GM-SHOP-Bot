"""
Database models and queries for GM SHOP Bot.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json
import structlog

from bot.database.connection import db
from bot.config import DEFAULT_CHAT_SETTINGS

logger = structlog.get_logger(__name__)


# =============================================================================
# CHATS
# =============================================================================

async def get_or_create_chat(chat_id: int, title: str = None) -> Dict[str, Any]:
    """Get chat from database or create if not exists."""
    chat = await db.fetchrow(
        "SELECT * FROM chats WHERE chat_id = $1",
        chat_id
    )

    if not chat:
        await db.execute(
            """
            INSERT INTO chats (chat_id, title, settings)
            VALUES ($1, $2, $3)
            """,
            chat_id,
            title,
            json.dumps(DEFAULT_CHAT_SETTINGS)
        )
        chat = await db.fetchrow(
            "SELECT * FROM chats WHERE chat_id = $1",
            chat_id
        )
        logger.info("chat_created", chat_id=chat_id, title=title)

    result = dict(chat)
    # Parse settings JSON if it's a string
    if isinstance(result.get('settings'), str):
        result['settings'] = json.loads(result['settings'])
    return result


async def update_chat_settings(chat_id: int, settings: Dict[str, Any]):
    """Update chat settings."""
    await db.execute(
        "UPDATE chats SET settings = $1 WHERE chat_id = $2",
        json.dumps(settings),
        chat_id
    )
    logger.info("chat_settings_updated", chat_id=chat_id)


async def get_chat_settings(chat_id: int) -> Dict[str, Any]:
    """Get chat settings."""
    settings = await db.fetchval(
        "SELECT settings FROM chats WHERE chat_id = $1",
        chat_id
    )

    # Parse JSON if it's a string
    if isinstance(settings, str):
        settings = json.loads(settings)

    return settings or DEFAULT_CHAT_SETTINGS


# =============================================================================
# USERS
# =============================================================================

async def get_or_create_user(
    user_id: int,
    first_name: str = None,
    last_name: str = None,
    username: str = None,
    is_bot: bool = False
) -> Dict[str, Any]:
    """Get user from database or create if not exists."""
    user = await db.fetchrow(
        "SELECT * FROM users WHERE user_id = $1",
        user_id
    )

    if not user:
        await db.execute(
            """
            INSERT INTO users (user_id, first_name, last_name, username, is_bot)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id, first_name, last_name, username, is_bot
        )
        user = await db.fetchrow(
            "SELECT * FROM users WHERE user_id = $1",
            user_id
        )
    else:
        # Update user info if changed
        await db.execute(
            """
            UPDATE users
            SET first_name = $2, last_name = $3, username = $4
            WHERE user_id = $1
            """,
            user_id, first_name, last_name, username
        )

    return dict(user)


# =============================================================================
# CHAT MEMBERS
# =============================================================================

async def get_or_create_chat_member(chat_id: int, user_id: int) -> Dict[str, Any]:
    """Get or create chat member record."""
    member = await db.fetchrow(
        "SELECT * FROM chat_members WHERE chat_id = $1 AND user_id = $2",
        chat_id, user_id
    )

    if not member:
        await db.execute(
            """
            INSERT INTO chat_members (chat_id, user_id)
            VALUES ($1, $2)
            """,
            chat_id, user_id
        )
        member = await db.fetchrow(
            "SELECT * FROM chat_members WHERE chat_id = $1 AND user_id = $2",
            chat_id, user_id
        )

    return dict(member)


async def increment_messages_count(chat_id: int, user_id: int):
    """Increment weekly and all-time message count for user."""
    await db.execute(
        """
        UPDATE chat_members
        SET messages_week = messages_week + 1,
            messages_all_time = messages_all_time + 1,
            last_message_at = NOW()
        WHERE chat_id = $1 AND user_id = $2
        """,
        chat_id, user_id
    )


async def reset_weekly_stats(chat_id: int):
    """Reset weekly statistics for all members."""
    await db.execute(
        """
        UPDATE chat_members
        SET messages_week = 0,
            replies_received_week = 0,
            reactions_received_week = 0
        WHERE chat_id = $1
        """,
        chat_id
    )
    logger.info("weekly_stats_reset", chat_id=chat_id)


# =============================================================================
# SANCTIONS
# =============================================================================

async def add_sanction(
    chat_id: int,
    target_user_id: int,
    moderator_id: int,
    sanction_type: str,
    reason: str = None,
    duration_seconds: int = None
) -> int:
    """Add a new sanction."""
    expires_at = None
    if duration_seconds:
        expires_at = datetime.now() + timedelta(seconds=duration_seconds)

    sanction_id = await db.fetchval(
        """
        INSERT INTO sanctions (chat_id, target_user_id, moderator_id, type, reason, duration_seconds, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """,
        chat_id, target_user_id, moderator_id, sanction_type, reason, duration_seconds, expires_at
    )

    logger.info(
        "sanction_added",
        chat_id=chat_id,
        target_user_id=target_user_id,
        type=sanction_type,
        duration_seconds=duration_seconds
    )

    return sanction_id


async def get_active_sanctions(chat_id: int, user_id: int, sanction_type: str = None) -> List[Dict]:
    """Get active sanctions for a user."""
    query = """
        SELECT * FROM sanctions
        WHERE chat_id = $1 AND target_user_id = $2 AND is_active = TRUE
        AND (expires_at IS NULL OR expires_at > NOW())
    """
    args = [chat_id, user_id]

    if sanction_type:
        query += " AND type = $3"
        args.append(sanction_type)

    sanctions = await db.fetch(query, *args)
    return [dict(s) for s in sanctions]


async def deactivate_sanction(sanction_id: int):
    """Deactivate a sanction."""
    await db.execute(
        "UPDATE sanctions SET is_active = FALSE WHERE id = $1",
        sanction_id
    )


async def get_warn_count(chat_id: int, user_id: int) -> int:
    """Get active warn count for user."""
    count = await db.fetchval(
        """
        SELECT COUNT(*) FROM sanctions
        WHERE chat_id = $1 AND target_user_id = $2
        AND type = 'warn' AND is_active = TRUE
        """,
        chat_id, user_id
    )
    return count or 0


async def remove_last_warn(chat_id: int, user_id: int) -> bool:
    """Remove last active warn from user. Returns True if warn was removed."""
    # Get last active warn
    warn_id = await db.fetchval(
        """
        SELECT id FROM sanctions
        WHERE chat_id = $1 AND target_user_id = $2
        AND type = 'warn' AND is_active = TRUE
        ORDER BY created_at DESC
        LIMIT 1
        """,
        chat_id, user_id
    )

    if warn_id:
        # Mark as inactive
        await db.execute(
            "UPDATE sanctions SET is_active = FALSE WHERE id = $1",
            warn_id
        )
        return True
    return False


# =============================================================================
# MESSAGE LOG (for antiflood)
# =============================================================================

async def log_message(chat_id: int, user_id: int, message_id: int):
    """Log a message for antiflood tracking."""
    await db.execute(
        "INSERT INTO message_log (chat_id, user_id, message_id) VALUES ($1, $2, $3)",
        chat_id, user_id, message_id
    )


async def get_recent_messages(chat_id: int, user_id: int, minutes: int = 3) -> List[Dict]:
    """Get recent messages from user."""
    since = datetime.now() - timedelta(minutes=minutes)
    messages = await db.fetch(
        """
        SELECT * FROM message_log
        WHERE chat_id = $1 AND user_id = $2 AND created_at > $3
        ORDER BY created_at DESC
        """,
        chat_id, user_id, since
    )
    return [dict(m) for m in messages]


async def cleanup_old_message_logs(days: int = 7):
    """Clean up old message logs."""
    cutoff = datetime.now() - timedelta(days=days)
    deleted = await db.execute(
        "DELETE FROM message_log WHERE created_at < $1",
        cutoff
    )
    logger.info("message_logs_cleaned", deleted=deleted)


# =============================================================================
# KARMA
# =============================================================================

async def add_karma_event(
    chat_id: int,
    from_user_id: int,
    to_user_id: int,
    delta: int,
    reason: str = None
):
    """Add karma event and update karma."""
    await db.execute(
        """
        INSERT INTO karma_events (chat_id, from_user_id, to_user_id, delta, reason)
        VALUES ($1, $2, $3, $4, $5)
        """,
        chat_id, from_user_id, to_user_id, delta, reason
    )

    await db.execute(
        """
        UPDATE chat_members
        SET karma = karma + $3
        WHERE chat_id = $1 AND user_id = $2
        """,
        chat_id, to_user_id, delta
    )

    logger.info(
        "karma_changed",
        chat_id=chat_id,
        from_user=from_user_id,
        to_user=to_user_id,
        delta=delta
    )


async def get_karma(chat_id: int, user_id: int) -> int:
    """Get user's karma."""
    karma = await db.fetchval(
        "SELECT karma FROM chat_members WHERE chat_id = $1 AND user_id = $2",
        chat_id, user_id
    )
    return karma or 0


async def check_karma_cooldown(
    chat_id: int,
    from_user_id: int,
    to_user_id: int,
    hours: int = 12
) -> bool:
    """Check if karma cooldown has passed."""
    since = datetime.now() - timedelta(hours=hours)
    exists = await db.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM karma_events
            WHERE chat_id = $1 AND from_user_id = $2 AND to_user_id = $3
            AND created_at > $4
        )
        """,
        chat_id, from_user_id, to_user_id, since
    )
    return not exists


# =============================================================================
# STAFF (admin roles)
# =============================================================================

async def add_staff(chat_id: int, user_id: int, role: str, added_by: int):
    """Add staff member."""
    await db.execute(
        """
        INSERT INTO staff (chat_id, user_id, role, added_by)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id, user_id) DO UPDATE SET role = $3
        """,
        chat_id, user_id, role, added_by
    )
    logger.info("staff_added", chat_id=chat_id, user_id=user_id, role=role)


async def remove_staff(chat_id: int, user_id: int):
    """Remove staff member."""
    await db.execute(
        "DELETE FROM staff WHERE chat_id = $1 AND user_id = $2",
        chat_id, user_id
    )
    logger.info("staff_removed", chat_id=chat_id, user_id=user_id)


async def get_user_role(chat_id: int, user_id: int) -> Optional[str]:
    """Get user's role in chat."""
    from bot.config import settings

    # Check if user is owner
    if user_id in settings.owner_ids:
        return "owner"

    # Check database role
    role = await db.fetchval(
        "SELECT role FROM staff WHERE chat_id = $1 AND user_id = $2",
        chat_id, user_id
    )
    return role


async def is_staff(chat_id: int, user_id: int) -> bool:
    """Check if user is staff."""
    role = await get_user_role(chat_id, user_id)
    return role is not None


async def set_user_role(chat_id: int, user_id: int, role: str):
    """Set user role (moderator, admin)."""
    # Check if user already has a role
    existing_role = await db.fetchval(
        "SELECT role FROM staff WHERE chat_id = $1 AND user_id = $2",
        chat_id, user_id
    )

    if existing_role:
        # Update existing role
        await db.execute(
            "UPDATE staff SET role = $1 WHERE chat_id = $2 AND user_id = $3",
            role, chat_id, user_id
        )
    else:
        # Insert new role
        await db.execute(
            "INSERT INTO staff (chat_id, user_id, role) VALUES ($1, $2, $3)",
            chat_id, user_id, role
        )


async def remove_user_role(chat_id: int, user_id: int):
    """Remove user role from chat."""
    await db.execute(
        "DELETE FROM staff WHERE chat_id = $1 AND user_id = $2",
        chat_id, user_id
    )


# =============================================================================
# AUDIT LOG
# =============================================================================

async def add_audit_log(
    chat_id: int,
    actor_id: int,
    action: str,
    payload: Dict[str, Any] = None
):
    """Add entry to audit log."""
    await db.execute(
        """
        INSERT INTO audit_log (chat_id, actor_id, action, payload)
        VALUES ($1, $2, $3, $4)
        """,
        chat_id, actor_id, action, json.dumps(payload or {})
    )


# =============================================================================
# STATISTICS
# =============================================================================

async def get_sanctions_count_7d(chat_id: int, user_id: int, sanction_type: str) -> int:
    """Get sanctions count for last 7 days."""
    since = datetime.now() - timedelta(days=7)
    count = await db.fetchval(
        """
        SELECT COUNT(*) FROM sanctions
        WHERE chat_id = $1 AND target_user_id = $2 AND type = $3
        AND created_at > $4
        """,
        chat_id, user_id, sanction_type, since
    )
    return count or 0


async def get_sanctions_count_all(chat_id: int, user_id: int, sanction_type: str) -> int:
    """Get all-time sanctions count."""
    count = await db.fetchval(
        """
        SELECT COUNT(*) FROM sanctions
        WHERE chat_id = $1 AND target_user_id = $2 AND type = $3
        """,
        chat_id, user_id, sanction_type
    )
    return count or 0


async def get_giveaway_wins_count(chat_id: int, user_id: int) -> int:
    """Get giveaway wins count for user."""
    count = await db.fetchval(
        """
        SELECT COUNT(*) FROM giveaway_winners
        WHERE chat_id = $1 AND user_id = $2
        """,
        chat_id, user_id
    )
    return count or 0


async def get_giveaway_entries_count(chat_id: int, user_id: int) -> int:
    """Get giveaway entries count for user."""
    count = await db.fetchval(
        """
        SELECT COUNT(DISTINCT giveaway_id) FROM giveaway_entries
        WHERE chat_id = $1 AND user_id = $2
        """,
        chat_id, user_id
    )
    return count or 0


async def get_chat_members_count(chat_id: int) -> int:
    """Get total members count in chat."""
    count = await db.fetchval(
        "SELECT COUNT(*) FROM chat_members WHERE chat_id = $1",
        chat_id
    )
    return count or 0


async def get_messages_count(chat_id: int, hours: int = None, days: int = None) -> int:
    """Get messages count for time period."""
    if hours:
        since = datetime.now() - timedelta(hours=hours)
    elif days:
        since = datetime.now() - timedelta(days=days)
    else:
        # All time
        count = await db.fetchval(
            "SELECT SUM(messages_all_time) FROM chat_members WHERE chat_id = $1",
            chat_id
        )
        return count or 0

    count = await db.fetchval(
        """
        SELECT COUNT(*) FROM message_log
        WHERE chat_id = $1 AND created_at > $2
        """,
        chat_id, since
    )
    return count or 0


async def get_top_by_messages(chat_id: int, limit: int = 10) -> List[Dict]:
    """Get top users by messages count (7d)."""
    users = await db.fetch(
        """
        SELECT user_id, messages_week
        FROM chat_members
        WHERE chat_id = $1 AND messages_week > 0
        ORDER BY messages_week DESC
        LIMIT $2
        """,
        chat_id, limit
    )
    return [dict(u) for u in users]


async def get_top_by_messages_all_time(chat_id: int, limit: int = 10) -> List[Dict]:
    """Get top users by messages count (all time)."""
    users = await db.fetch(
        """
        SELECT user_id, messages_all_time
        FROM chat_members
        WHERE chat_id = $1 AND messages_all_time > 0
        ORDER BY messages_all_time DESC
        LIMIT $2
        """,
        chat_id, limit
    )
    return [dict(u) for u in users]


async def get_top_by_karma_7d(chat_id: int, limit: int = 10) -> List[Dict]:
    """Get top users by karma delta in last 7 days."""
    since = datetime.now() - timedelta(days=7)
    users = await db.fetch(
        """
        SELECT to_user_id as user_id, SUM(delta) as karma_delta
        FROM karma_events
        WHERE chat_id = $1 AND created_at > $2
        GROUP BY to_user_id
        HAVING SUM(delta) > 0
        ORDER BY karma_delta DESC
        LIMIT $3
        """,
        chat_id, since, limit
    )
    return [dict(u) for u in users]
# =============================================================================
# NICKNAMES
# =============================================================================

async def set_nickname(chat_id: int, user_id: int, nickname: str) -> tuple[bool, str]:
    """
    Set user nickname in chat.

    Returns:
        (success, error_message)
    """
    # Validate nickname
    if len(nickname) < 2 or len(nickname) > 32:
        return False, "Прозвище должно быть от 2 до 32 символов"

    # Check if allowed characters (letters, numbers, underscore, dash)
    import re
    if not re.match(r'^[\w\-]+$', nickname, re.UNICODE):
        return False, "Прозвище может содержать только буквы, цифры, _ и -"

    # Check if nickname is already taken by another user
    existing_user = await db.fetchval(
        """
        SELECT user_id FROM chat_members
        WHERE chat_id = $1 AND LOWER(nickname) = LOWER($2) AND user_id != $3
        """,
        chat_id, nickname, user_id
    )

    if existing_user:
        return False, "Это прозвище уже занято другим пользователем"

    # Set nickname
    try:
        await db.execute(
            """
            UPDATE chat_members
            SET nickname = $3
            WHERE chat_id = $1 AND user_id = $2
            """,
            chat_id, user_id, nickname
        )
        logger.info("nickname_set", chat_id=chat_id, user_id=user_id, nickname=nickname)
        return True, ""
    except Exception as e:
        logger.error("nickname_set_failed", chat_id=chat_id, user_id=user_id, error=str(e))
        return False, "Ошибка при установке прозвища"


async def remove_nickname(chat_id: int, user_id: int):
    """Remove user nickname."""
    await db.execute(
        """
        UPDATE chat_members
        SET nickname = NULL
        WHERE chat_id = $1 AND user_id = $2
        """,
        chat_id, user_id
    )
    logger.info("nickname_removed", chat_id=chat_id, user_id=user_id)


async def get_display_name(chat_id: int, user_id: int) -> str:
    """
    Get user display name (nickname or first_name).

    Returns:
        Display name as string
    """
    # Get nickname from chat_members
    member = await db.fetchrow(
        "SELECT nickname FROM chat_members WHERE chat_id = $1 AND user_id = $2",
        chat_id, user_id
    )

    if member and member['nickname']:
        return member['nickname']

    # Fallback to user's first name
    user = await db.fetchrow(
        "SELECT first_name FROM users WHERE user_id = $1",
        user_id
    )

    return user['first_name'] if user else f"User {user_id}"
