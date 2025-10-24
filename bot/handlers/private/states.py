"""
FSM states for admin panel settings editors.
"""

from aiogram.fsm.state import State, StatesGroup


class RulesEditor(StatesGroup):
    """States for rules text editor."""
    chat_id = State()  # Store chat_id we're editing
    editing = State()  # Waiting for new rules text


class WelcomeEditor(StatesGroup):
    """States for welcome message editor."""
    chat_id = State()  # Store chat_id we're editing
    editing_text = State()  # Waiting for new welcome text
    editing_auto_delete = State()  # Waiting for auto-delete minutes


class GiveawayWizard(StatesGroup):
    """States for giveaway creation wizard."""
    chat_id = State()
    title = State()
    description = State()
    duration_hours = State()
    winners_count = State()
    requirements = State()
