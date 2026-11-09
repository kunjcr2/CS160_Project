"""ActionCommand: the base class every confirmable action implements (plan §4, §5.3)."""

from abc import ABC, abstractmethod
from typing import ClassVar

from sqlalchemy.orm import Session

from app.model.entities import User


class ActionNotPossible(Exception):  # noqa: N818 (domain name, not a programming error)
    """The action can't run right now (e.g. the slot was just taken).

    `message` is the sentence shown or spoken to the user; `code` is for the frontend.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ActionCommand(ABC):
    """One user-confirmable action. Rebuilt from `pending_actions.payload` at confirm time,
    so everything it needs must be in the payload (plain JSON values only).
    """

    action_type: ClassVar[str]  # stored in pending_actions.action_type
    reversible: ClassVar[bool] = False  # explicit capability (plan §4, LSP)

    def __init__(self, user: User, payload: dict) -> None:
        self.user = user
        self.payload = payload

    @abstractmethod
    def summary(self, session: Session) -> str:
        """The plain-language read-back, ending with the question (e.g. "Should I book it?")."""

    @abstractmethod
    def revalidate(self, session: Session) -> None:
        """Raise ActionNotPossible if the action can no longer run. Called at propose time
        and again at confirm time."""

    @abstractmethod
    def execute(self, session: Session) -> dict:
        """Perform the action and return a JSON-serializable result. Raise ActionNotPossible
        for expected failures; any partial database writes are rolled back."""

    @abstractmethod
    def success_message(self, result: dict) -> str:
        """The sentence to say after execute() succeeded."""
