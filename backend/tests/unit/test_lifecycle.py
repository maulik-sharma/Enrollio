"""Lifecycle transition matrix and actor rules."""

from __future__ import annotations

import pytest

from app.core.domain import ActorType, LifecycleStatus
from app.core.permissions import PermissionName, RoleSlug
from app.services.lifecycle import (
    FUNNEL,
    LIFECYCLE_TRANSITIONS,
    TERMINAL_STATES,
    InvalidLifecycleTransition,
    TransitionActor,
    TransitionNotPermitted,
    allowed_transitions,
    validate_transition,
)

MANAGER = TransitionActor(
    actor_type=ActorType.USER,
    role_slugs=frozenset({RoleSlug.ADMISSION_MANAGER.value}),
    permissions=frozenset({PermissionName.LEADS_VIEW_ALL.value}),
)
COUNSELLOR = TransitionActor(
    actor_type=ActorType.USER,
    role_slugs=frozenset({RoleSlug.ADMISSION_COUNSELLOR.value}),
    permissions=frozenset({PermissionName.LEADS_VIEW_ASSIGNED.value}),
)
SYSTEM = TransitionActor.system()
AGENT = TransitionActor.agent()
ALL_STATES = frozenset(LifecycleStatus)


@pytest.mark.parametrize("current", list(ALL_STATES))
def test_every_allowed_manager_transition_passes(current: LifecycleStatus) -> None:
    for target in allowed_transitions(current, actor=MANAGER):
        validate_transition(current, target, actor=MANAGER)


@pytest.mark.parametrize("current", list(ALL_STATES))
def test_every_disallowed_manager_transition_is_rejected(current: LifecycleStatus) -> None:
    allowed = allowed_transitions(current, actor=MANAGER)
    for target in ALL_STATES - allowed:
        if target is current:
            continue
        with pytest.raises(InvalidLifecycleTransition):
            validate_transition(current, target, actor=MANAGER)


def test_forward_funnel_is_linear() -> None:
    for current, target in zip(FUNNEL, FUNNEL[1:], strict=False):
        assert target in LIFECYCLE_TRANSITIONS[current]


def test_any_active_state_can_be_closed() -> None:
    for current in ALL_STATES - TERMINAL_STATES:
        for closing in {
            LifecycleStatus.LOST,
            LifecycleStatus.DISQUALIFIED,
            LifecycleStatus.UNRESPONSIVE,
            LifecycleStatus.OPTED_OUT,
        }:
            assert closing in LIFECYCLE_TRANSITIONS[current]


def test_agent_cannot_convert() -> None:
    with pytest.raises(TransitionNotPermitted):
        validate_transition(
            LifecycleStatus.ADMISSION_OFFERED, LifecycleStatus.CONVERTED, actor=AGENT
        )


def test_counsellor_cannot_convert() -> None:
    with pytest.raises(TransitionNotPermitted):
        validate_transition(
            LifecycleStatus.ADMISSION_OFFERED,
            LifecycleStatus.CONVERTED,
            actor=COUNSELLOR,
        )


def test_system_can_convert() -> None:
    validate_transition(
        LifecycleStatus.ADMISSION_OFFERED,
        LifecycleStatus.CONVERTED,
        actor=SYSTEM,
    )


@pytest.mark.parametrize("terminal", list(TERMINAL_STATES))
def test_only_a_manager_can_reopen_a_terminal_lead(terminal: LifecycleStatus) -> None:
    validate_transition(terminal, LifecycleStatus.NEW_ENQUIRY, actor=MANAGER)
    with pytest.raises(TransitionNotPermitted):
        validate_transition(terminal, LifecycleStatus.NEW_ENQUIRY, actor=COUNSELLOR)
    with pytest.raises(TransitionNotPermitted):
        validate_transition(terminal, LifecycleStatus.NEW_ENQUIRY, actor=SYSTEM)
