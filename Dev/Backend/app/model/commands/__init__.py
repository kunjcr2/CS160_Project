"""Pending actions as Command classes (plan §4): one class per action type, registered in a
command registry.
"""

# Importing a command module registers it.
from . import book_appointment  # noqa: F401
from .base import ActionCommand, ActionNotPossible
from .registry import UnknownActionType, build, register, registered_types

__all__ = [
    "ActionCommand",
    "ActionNotPossible",
    "UnknownActionType",
    "build",
    "register",
    "registered_types",
]
