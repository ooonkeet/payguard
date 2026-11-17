"""Strict Payment State Machine preventing invalid transaction state transitions."""

from typing import Dict, Set

from app.core.exceptions import InvalidStateTransitionError
from app.schemas.payment import PaymentStatus

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    PaymentStatus.CREATED.value: {PaymentStatus.PROCESSING.value},
    PaymentStatus.PROCESSING.value: {
        PaymentStatus.SUCCESS.value,
        PaymentStatus.FAILED.value,
        PaymentStatus.PENDING.value,
    },
    PaymentStatus.PENDING.value: {
        PaymentStatus.SUCCESS.value,
        PaymentStatus.FAILED.value,
    },
    PaymentStatus.SUCCESS.value: {PaymentStatus.REFUNDED.value},
    PaymentStatus.FAILED.value: set(),
    PaymentStatus.REFUNDED.value: set(),
}


def can_transition(current_status: str, target_status: str) -> bool:
    """Return True if transitioning from current_status to target_status is allowed."""
    return target_status in ALLOWED_TRANSITIONS.get(current_status, set())


def validate_transition(current_status: str, target_status: str) -> None:
    """Raise InvalidStateTransitionError if transition is not permitted."""
    if not can_transition(current_status, target_status):
        raise InvalidStateTransitionError(current_status=current_status, target_status=target_status)

