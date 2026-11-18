"""CareMessagingProvider: what any "send a message to the care team" system must do
(PB-07, send only; replies and read status are deferred, plan §17).

The model (services and commands) talks ONLY to this interface, never to a real or
mock system directly. Today the only implementation is MockCareMessaging (mock.py).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class MessagingError(Exception):
    """Base class for every error from a care-messaging provider."""


class MessagingUnavailableError(MessagingError):
    """The messaging system is down or too slow. Safe to try again later."""


@dataclass(frozen=True)
class SentMessage:
    """A message accepted by the care-team messaging system."""

    external_ref: str  # this message's id in the messaging system
    sent_at: datetime  # UTC


class CareMessagingProvider(ABC):
    """What every care-team messaging system must be able to do.

    Can raise MessagingUnavailableError.
    """

    @abstractmethod
    def send(self, recipient_ref: str, body: str, *, sender_ref: str) -> SentMessage:
        """Send `body` to the recipient (a provider's external_ref).

        sender_ref is our user's id as text. Raises MessagingUnavailableError if the
        system can't be reached right now.
        """
