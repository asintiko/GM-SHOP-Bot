"""
Content filters and patterns for spam detection.
Based on Appendix A from specification.
"""

import re
from typing import List, Tuple, Optional

# =============================================================================
# DEFAULT FILTER PATTERNS (from specification Appendix A)
# =============================================================================

# Earning/Scam/Casino patterns
EARNING_PATTERNS = [
    r'(?i)\b(заработ(ок|ать)|доход( без вложений)?|быстрые деньги|легкие деньги)\b',
    r'(?i)\b(ставк(и|а)|букмекер|каппер|повышу банк|раскрутка банка)\b',
    r'(?i)\b(казин(о)|1\s*win|most\s*bet|mel\s*bet|bet\s*winn?er)\b',
    r'(?i)\b(сигналы|инсайд|реф(?:ерал)?ка|реф(?:ерал)?ьная)\b',
    r'(?i)\b(в лс|в личку|пиши в личку).{0,15}(заработ|ставк|казин)\b',
    r'(?i)\b(крипт(а|о)|биткоин|btc|eth).{0,20}(заработ|доход|сигнал)\b',
]

# Positive karma patterns (for +1 karma)
POSITIVE_KARMA_PATTERNS = [
    r'(?i)^\s*\+\s*$',
    r'(?i)\b(спасибо|спс|благодарю|thx|thanks|ty|thank you)\b',
    r'(?i)\b(красава|красавчик|молодец|супер|отлично)\b',
]

# Negative karma patterns (for -1 karma)
NEGATIVE_KARMA_PATTERNS = [
    r'(?i)^\s*-\s*$',
    r'(?i)\b(фу|кринж|дизлайк|отстой)\b',
]


# =============================================================================
# FILTER CLASSES
# =============================================================================

class ContentFilter:
    """Content filter for detecting spam and inappropriate content."""

    def __init__(self, custom_patterns: List[str] = None):
        """
        Initialize content filter.

        Args:
            custom_patterns: Additional custom regex patterns to check
        """
        self.earning_patterns = [re.compile(p) for p in EARNING_PATTERNS]
        self.positive_karma_patterns = [re.compile(p) for p in POSITIVE_KARMA_PATTERNS]
        self.negative_karma_patterns = [re.compile(p) for p in NEGATIVE_KARMA_PATTERNS]

        if custom_patterns:
            self.custom_patterns = [re.compile(p) for p in custom_patterns]
        else:
            self.custom_patterns = []

    def check_earning_spam(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if text contains earning/casino spam.

        Args:
            text: Text to check

        Returns:
            Tuple of (is_spam, matched_pattern)
        """
        if not text:
            return False, None

        for pattern in self.earning_patterns:
            if pattern.search(text):
                return True, pattern.pattern

        return False, None

    def check_positive_karma(self, text: str) -> bool:
        """
        Check if text contains positive karma triggers.

        Args:
            text: Text to check

        Returns:
            True if positive karma trigger found
        """
        if not text:
            return False

        for pattern in self.positive_karma_patterns:
            if pattern.search(text):
                return True

        return False

    def check_negative_karma(self, text: str) -> bool:
        """
        Check if text contains negative karma triggers.

        Args:
            text: Text to check

        Returns:
            True if negative karma trigger found
        """
        if not text:
            return False

        for pattern in self.negative_karma_patterns:
            if pattern.search(text):
                return True

        return False

    def check_custom_filters(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check text against custom filters.

        Args:
            text: Text to check

        Returns:
            Tuple of (matched, pattern)
        """
        if not text:
            return False, None

        for pattern in self.custom_patterns:
            if pattern.search(text):
                return True, pattern.pattern

        return False, None


class LinkFilter:
    """Filter for checking URLs and links."""

    # Common link patterns
    URL_PATTERN = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    TELEGRAM_LINK_PATTERN = re.compile(
        r't\.me/(?:joinchat/)?[a-zA-Z0-9_]+'
    )

    def __init__(self, whitelist_domains: List[str] = None):
        """
        Initialize link filter.

        Args:
            whitelist_domains: List of whitelisted domains (e.g., ['t.me', 'google.com'])
        """
        self.whitelist_domains = whitelist_domains or ['t.me', 'telegram.me']

    def contains_link(self, text: str) -> bool:
        """Check if text contains any link."""
        if not text:
            return False
        return bool(self.URL_PATTERN.search(text))

    def is_whitelisted(self, url: str) -> bool:
        """Check if URL domain is whitelisted."""
        if not url:
            return False

        for domain in self.whitelist_domains:
            if domain in url:
                return True

        return False

    def check_unauthorized_link(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if text contains unauthorized link.

        Args:
            text: Text to check

        Returns:
            Tuple of (has_unauthorized_link, found_link)
        """
        if not text:
            return False, None

        # Find all links
        links = self.URL_PATTERN.findall(text)

        for link in links:
            if not self.is_whitelisted(link):
                return True, link

        # Check for Telegram invite links
        tg_links = self.TELEGRAM_LINK_PATTERN.findall(text)
        if tg_links and not self.is_whitelisted(text):
            return True, tg_links[0]

        return False, None


# =============================================================================
# GLOBAL FILTER INSTANCES
# =============================================================================

# Default content filter
content_filter = ContentFilter()

# Default link filter
link_filter = LinkFilter()


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    # Test earning spam
    test_texts = [
        "Хочу заработать без вложений!",
        "Казино 1win лучшее!",
        "Букмекерская контора",
        "Нормальное сообщение",
        "спасибо большое!",
        "фу, кринж",
        "+",
    ]

    print("Testing content filters:")
    for text in test_texts:
        is_spam, pattern = content_filter.check_earning_spam(text)
        is_positive = content_filter.check_positive_karma(text)
        is_negative = content_filter.check_negative_karma(text)

        print(f"\nText: '{text}'")
        print(f"  Spam: {is_spam}")
        print(f"  Positive karma: {is_positive}")
        print(f"  Negative karma: {is_negative}")
