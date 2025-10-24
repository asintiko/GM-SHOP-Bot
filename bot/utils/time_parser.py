"""
Time parser for moderation commands.
Supports formats like: 50m, 3h, 2d, 1w, 1h30m, etc.
"""

import re
from typing import Optional


def parse_time(time_str: str) -> Optional[int]:
    """
    Parse time string to seconds.

    Supported formats:
    - 50м, 50мин, 50 минут (minutes)
    - 3ч, 3h, 3 часа (hours)
    - 2д, 2d, 2 дня (days)
    - 1w, 1н, 1 неделя (weeks)
    - Combined: 1h30m, 1д12ч, etc.

    Args:
        time_str: Time string to parse

    Returns:
        Number of seconds or None if parsing failed
    """
    if not time_str:
        return None

    # Normalize input
    time_str = time_str.lower().strip()

    # Pattern for time components
    # Supports both Cyrillic and Latin letters
    pattern = r'(\d+)\s*([а-яa-z]+)'

    matches = re.findall(pattern, time_str)

    if not matches:
        return None

    total_seconds = 0

    for amount, unit in matches:
        amount = int(amount)

        # Seconds
        if unit in ['s', 'с', 'сек', 'секунд', 'секунды']:
            total_seconds += amount

        # Minutes
        elif unit in ['m', 'min', 'м', 'мин', 'минут', 'минуты', 'минута']:
            total_seconds += amount * 60

        # Hours
        elif unit in ['h', 'hour', 'ч', 'час', 'часа', 'часов']:
            total_seconds += amount * 3600

        # Days
        elif unit in ['d', 'day', 'д', 'дн', 'день', 'дня', 'дней']:
            total_seconds += amount * 86400

        # Weeks
        elif unit in ['w', 'week', 'н', 'нед', 'неделя', 'недели', 'недель']:
            total_seconds += amount * 604800

        else:
            # Unknown unit
            return None

    return total_seconds if total_seconds > 0 else None


def format_time(seconds: int) -> str:
    """
    Format seconds to human-readable time string.

    Args:
        seconds: Number of seconds

    Returns:
        Formatted time string (e.g., "2д 3ч 15м")
    """
    if seconds == 0:
        return "0 секунд"

    parts = []

    # Weeks
    weeks = seconds // 604800
    if weeks:
        parts.append(f"{weeks}н")
        seconds %= 604800

    # Days
    days = seconds // 86400
    if days:
        parts.append(f"{days}д")
        seconds %= 86400

    # Hours
    hours = seconds // 3600
    if hours:
        parts.append(f"{hours}ч")
        seconds %= 3600

    # Minutes
    minutes = seconds // 60
    if minutes:
        parts.append(f"{minutes}м")
        seconds %= 60

    # Seconds
    if seconds:
        parts.append(f"{seconds}с")

    return " ".join(parts)


# Tests (can be removed in production)
if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("50m", 3000),
        ("50м", 3000),
        ("50 минут", 3000),
        ("3h", 10800),
        ("3ч", 10800),
        ("2d", 172800),
        ("2д", 172800),
        ("1w", 604800),
        ("1h30m", 5400),
        ("1д12ч", 129600),
        ("invalid", None),
    ]

    for input_str, expected in test_cases:
        result = parse_time(input_str)
        status = "✓" if result == expected else "✗"
        print(f"{status} parse_time('{input_str}') = {result} (expected {expected})")
