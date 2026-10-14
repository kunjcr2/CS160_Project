"""Pending actions as Command classes (plan §4): one class per action type, registered in a
command registry.
"""

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
