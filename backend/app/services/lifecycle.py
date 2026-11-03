"""Explicit lead lifecycle state machine (FR-03)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import ActorType, LifecycleStatus
from app.core.permissions import PermissionName, RoleSlug
from app.models.timeline_event import TimelineEvent
from app.repositories import leads as leads_repo

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.user import User

logger = logging.getLogger(__name__)

FUNNEL: tuple[LifecycleStatus, ...] = (
    LifecycleStatus.NEW_ENQUIRY,
    LifecycleStatus.CONTACTED,
    LifecycleStatus.ENGAGED,
    LifecycleStatus.QUALIFIED,
    LifecycleStatus.COUNSELLING_SCHEDULED,
    LifecycleStatus.COUNSELLING_COMPLETED,
    LifecycleStatus.APPLICATION_STARTED,
    LifecycleStatus.APPLICATION_SUBMITTED,
    LifecycleStatus.ADMISSION_OFFERED,
    LifecycleStatus.CONVERTED,
)

TERMINAL_STATES: frozenset[LifecycleStatus] = frozenset(
    {
        LifecycleStatus.LOST,
        LifecycleStatus.DISQUALIFIED,
        LifecycleStatus.UNRESPONSIVE,
        LifecycleStatus.OPTED_OUT,
        LifecycleStatus.CONVERTED,
    }
)
_CLOSING_STATES = frozenset(
    {
        LifecycleStatus.LOST,
        LifecycleStatus.DISQUALIFIED,
        LifecycleStatus.UNRESPONSIVE,
        LifecycleStatus.OPTED_OUT,
    }
)

LIFECYCLE_TRANSITIONS: dict[LifecycleStatus, frozenset[LifecycleStatus]] = {}
for index, state in enumerate(FUNNEL):
    targets: set[LifecycleStatus] = set()
    if index + 1 < len(FUNNEL):
        targets.add(FUNNEL[index + 1])
    if state is not LifecycleStatus.CONVERTED:
        targets.update(_CLOSING_STATES)
    LIFECYCLE_TRANSITIONS[state] = frozenset(targets)

for state in _CLOSING_STATES:
    LIFECYCLE_TRANSITIONS[state] = frozenset()


class LifecycleError(Exception):
    """Base class for lifecycle domain failures."""


class LeadNotFound(LifecycleError):
    """No lead has the requested id."""


class InvalidLifecycleTransition(LifecycleError):
    """The requested source/target state pair is not allowed for this actor."""


class TransitionNotPermitted(LifecycleError):
    """The actor may not perform this otherwise-valid transition."""


@dataclass(frozen=True)
class TransitionActor:
    """Who is asking for a lifecycle transition."""

    actor_type: ActorType
    actor_id: uuid.UUID | None = None
    role_slugs: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()

    @classmethod
    def from_user(cls, user: User) -> TransitionActor:
        """Build an actor from a loaded user with roles and permissions."""
        return cls(
            actor_type=ActorType.USER,
            actor_id=user.id,
            role_slugs=frozenset(str(role.slug) for role in user.roles),
            permissions=frozenset(
                permission.name for role in user.roles for permission in role.permissions
            ),
        )

    @classmethod
    def system(cls, actor_id: uuid.UUID | None = None) -> TransitionActor:
        return cls(actor_type=ActorType.SYSTEM, actor_id=actor_id)

    @classmethod
    def agent(cls, actor_id: uuid.UUID | None = None) -> TransitionActor:
        return cls(actor_type=ActorType.AGENT, actor_id=actor_id)

    @property
    def is_manager(self) -> bool:
        """Managers own the funnel; ``leads.view_all`` is the current proxy."""
        return (
            RoleSlug.ADMISSION_MANAGER.value in self.role_slugs
            or PermissionName.LEADS_VIEW_ALL.value in self.permissions
        )


def allowed_transitions(
    current: LifecycleStatus,
    *,
    actor: TransitionActor,
) -> frozenset[LifecycleStatus]:
    """Return the targets this actor may choose from ``current``."""
    targets = LIFECYCLE_TRANSITIONS[current]
    if current in TERMINAL_STATES:
        if actor.actor_type is ActorType.USER and actor.is_manager:
            return frozenset({LifecycleStatus.NEW_ENQUIRY})
        return frozenset()
    cannot_convert = actor.actor_type is ActorType.AGENT or (
        actor.actor_type is ActorType.USER and not actor.is_manager
    )
    if cannot_convert:
        targets = targets - {LifecycleStatus.CONVERTED}
    return targets


_DISPLAY_ORDER: tuple[LifecycleStatus, ...] = FUNNEL + tuple(
    state for state in LifecycleStatus if state in _CLOSING_STATES
)


def ordered_allowed_transitions(
    current: LifecycleStatus,
    *,
    actor: TransitionActor,
) -> list[LifecycleStatus]:
    """Return allowed targets in funnel order for API responses and buttons."""
    allowed = allowed_transitions(current, actor=actor)
    return [state for state in _DISPLAY_ORDER if state in allowed]


def validate_transition(
    current: LifecycleStatus,
    target: LifecycleStatus,
    *,
    actor: TransitionActor,
) -> None:
    """Raise when ``current -> target`` is not allowed for ``actor``."""
    if current in TERMINAL_STATES:
        if target is not LifecycleStatus.NEW_ENQUIRY:
            raise InvalidLifecycleTransition(
                f"Cannot move a lead from {current.value} to {target.value}"
            )
        if actor.actor_type is not ActorType.USER or not actor.is_manager:
            raise TransitionNotPermitted("Only an Admission Manager can reopen a terminal lead")
        return
    if target not in LIFECYCLE_TRANSITIONS[current]:
        raise InvalidLifecycleTransition(
            f"Cannot move a lead from {current.value} to {target.value}"
        )
    if target is LifecycleStatus.CONVERTED:
        if actor.actor_type is ActorType.AGENT:
            raise TransitionNotPermitted("An AI agent cannot mark a lead as converted")
        if actor.actor_type is ActorType.USER and not actor.is_manager:
            raise TransitionNotPermitted("Only a system event or Admission Manager can convert")


async def transition(
    session: AsyncSession,
    lead_id: uuid.UUID,
    to_state: LifecycleStatus,
    actor: TransitionActor | User,
    reason: str,
) -> Lead:
    """Validate and apply a lifecycle transition, writing one timeline event."""
    resolved_actor = (
        actor if isinstance(actor, TransitionActor) else TransitionActor.from_user(actor)
    )
    lead = await leads_repo.get(session, lead_id)
    if lead is None:
        raise LeadNotFound

    current = lead.lifecycle_status
    try:
        validate_transition(current, to_state, actor=resolved_actor)
    except LifecycleError:
        logger.warning(
            "Rejected lifecycle transition",
            extra={
                "lead_id": str(lead_id),
                "from_state": current.value,
                "to_state": to_state.value,
                "actor_type": resolved_actor.actor_type.value,
            },
        )
        raise

    lead.lifecycle_status = to_state
    session.add(
        TimelineEvent(
            student_id=lead.student_id,
            lead_id=lead.id,
            event_type="lifecycle_transition",
            actor_type=resolved_actor.actor_type,
            actor_id=resolved_actor.actor_id,
            payload={
                "from_state": current.value,
                "to_state": to_state.value,
                "reason": reason,
            },
        )
    )
    await session.commit()
    await session.refresh(lead)
    return lead
