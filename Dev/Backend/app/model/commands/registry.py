"""Maps pending_actions.action_type to its Command class.

A new feature action is one new Command class decorated with @register (plan §4,
Open-Closed): ActionService never changes.
"""

from app.model.entities import User

from .base import ActionCommand

_commands: dict[str, type[ActionCommand]] = {}


class UnknownActionType(Exception):  # noqa: N818
    pass


def register(command_class: type[ActionCommand]) -> type[ActionCommand]:
    _commands[command_class.action_type] = command_class
    return command_class


def build(action_type: str, user: User, payload: dict) -> ActionCommand:
    try:
        command_class = _commands[action_type]
    except KeyError:
        raise UnknownActionType(action_type) from None
    return command_class(user, payload)


def registered_types() -> list[str]:
    return sorted(_commands)
