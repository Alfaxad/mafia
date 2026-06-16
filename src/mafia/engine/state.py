from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    MAFIA = "Mafia"
    DETECTIVE = "Detective"
    DOCTOR = "Doctor"
    VILLAGER = "Villager"


class Team(StrEnum):
    MAFIA = "mafia"
    TOWN = "town"


class Phase(StrEnum):
    LOBBY = "lobby"
    ROLE_ASSIGNMENT = "role_assignment"
    NIGHT = "night"
    DAWN = "dawn"
    DISCUSSION = "discussion"
    HOT_SEAT = "hot_seat"
    VOTE = "vote"
    RESOLUTION = "resolution"
    GAME_OVER = "game_over"


ROLE_LIST: tuple[Role, ...] = (
    Role.MAFIA,
    Role.MAFIA,
    Role.DETECTIVE,
    Role.DOCTOR,
    Role.VILLAGER,
    Role.VILLAGER,
    Role.VILLAGER,
)


DEFAULT_NAMES: tuple[str, ...] = (
    "You",
    "Nora",
    "Kai",
    "Mira",
    "Jules",
    "Lena",
    "Owen",
)


ROLE_TEAM: dict[Role, Team] = {
    Role.MAFIA: Team.MAFIA,
    Role.DETECTIVE: Team.TOWN,
    Role.DOCTOR: Team.TOWN,
    Role.VILLAGER: Team.TOWN,
}


@dataclass(slots=True)
class PlayerState:
    player_id: str
    display_name: str
    seat: int
    is_human: bool
    role: Role
    alive: bool = True
    persona: str = "measured"
    model_spec: str = "mafia-gemma-bf16"
    architecture: str = "holy_grail"
    public_status: str = "watching"
    private_memory: dict[str, Any] = field(default_factory=dict)
    revealed_role: Role | None = None

    @property
    def team(self) -> Team:
        return ROLE_TEAM[self.role]


@dataclass(slots=True)
class ClaimState:
    claimed_role: Role | None = None
    confidence: str = "unclaimed"
    counterclaimed_by: list[str] = field(default_factory=list)
    key_quote: str = ""
    night_story: str = ""
    last_vote: str | None = None


@dataclass(slots=True)
class Event:
    seq: int
    type: str
    phase: Phase
    day: int
    actor: str | None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NightActions:
    mafia_votes: dict[str, str] = field(default_factory=dict)
    detective_checks: dict[str, str] = field(default_factory=dict)
    doctor_protects: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class GameState:
    game_id: str
    seed: int
    phase: Phase
    day_number: int
    players: dict[str, PlayerState]
    human_player_id: str
    claims: dict[str, ClaimState] = field(default_factory=dict)
    votes: dict[str, str] = field(default_factory=dict)
    locked_votes: set[str] = field(default_factory=set)
    hot_seat_target: str | None = None
    night_actions: NightActions = field(default_factory=NightActions)
    events: list[Event] = field(default_factory=list)
    winner: Team | None = None
    eliminated_order: list[str] = field(default_factory=list)
    dawn_message: str = ""
    moderator_turns: int = 0
    ai_turns: int = 0
    invalid_actions: int = 0
    validator_repairs: int = 0
    model_calls: list[dict[str, Any]] = field(default_factory=list)

    def alive_players(self) -> list[str]:
        return [pid for pid, player in self.players.items() if player.alive]

    def mafia_alive(self) -> list[str]:
        return [
            pid
            for pid, player in self.players.items()
            if player.alive and player.team == Team.MAFIA
        ]

    def town_alive(self) -> list[str]:
        return [
            pid
            for pid, player in self.players.items()
            if player.alive and player.team == Team.TOWN
        ]

    def next_seq(self) -> int:
        return len(self.events) + 1

    def append_event(
        self,
        event_type: str,
        actor: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Event:
        event = Event(
            seq=self.next_seq(),
            type=event_type,
            phase=self.phase,
            day=self.day_number,
            actor=actor,
            payload=payload or {},
        )
        self.events.append(event)
        return event
