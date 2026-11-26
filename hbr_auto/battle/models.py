from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TurnKind(str, Enum):
    NORMAL = "NORMAL"
    SWITCH = "SWITCH"
    EXTRA = "EXTRA"
    EMPTY = "EMPTY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ResonanceSupportSpec:
    team: str | None = None
    character_id: str | None = None
    style: str | None = None
    style_id: str | None = None
    rank: str | None = None
    image: str | None = None
    crucial: bool = False

    @property
    def is_empty(self) -> bool:
        return not any((self.team, self.character_id, self.style, self.style_id, self.rank, self.image))


@dataclass(frozen=True, slots=True)
class ProgressionSnapshot:
    rank: str | None = None
    flower: bool | None = None
    earring: str | None = None
    spiritual: str | None = None
    reincarnation: str | None = None


@dataclass(frozen=True, slots=True)
class PartyMemberSpec:
    slot: int
    character_id: str
    team: str | None = None
    style: str | None = None
    style_id: str | None = None
    passive_skills: tuple[str, ...] = ()
    support: ResonanceSupportSpec = field(default_factory=ResonanceSupportSpec)
    progression: ProgressionSnapshot = field(default_factory=ProgressionSnapshot)


@dataclass(frozen=True, slots=True)
class PartyProfile:
    tab_id: str
    members: tuple[PartyMemberSpec | None, ...]

    def __post_init__(self) -> None:
        if len(self.members) != 6:
            raise ValueError("A PartyProfile must contain exactly six ordered slots")
        for index, member in enumerate(self.members, start=1):
            if member is not None and member.slot != index:
                raise ValueError("PartyProfile member slot does not match tuple position")

    def member(self, slot: int) -> PartyMemberSpec | None:
        if not 1 <= slot <= 6:
            raise IndexError(f"Party slot must be in 1..6, got {slot}")
        return self.members[slot - 1]


@dataclass(frozen=True, slots=True)
class OverdriveInstruction:
    raw: str
    level: int | None = None
    bonus: int | None = None

    @property
    def supported(self) -> bool:
        return self.level is not None


@dataclass(frozen=True, slots=True)
class BattleAction:
    slot: int
    team_tab: str
    character_id: str | None
    style: str | None
    style_id: str | None
    active_form_id: str | None
    skill_value: str | None
    target_value: str | None
    is_1_damage: bool = False


@dataclass(frozen=True, slots=True)
class BattleTurn:
    index: int
    label: str
    kind: TurnKind
    overdrive: OverdriveInstruction | None
    actions: tuple[BattleAction | None, ...]

    def __post_init__(self) -> None:
        if len(self.actions) != 3:
            raise ValueError("Each BattleTurn must contain exactly three action slots")


@dataclass(frozen=True, slots=True)
class BattlePlan:
    name: str
    source_version: str
    language: str | None
    parties: tuple[PartyProfile, ...]
    turns: tuple[BattleTurn, ...]
    warnings: tuple[str, ...] = ()
    source_path: str | None = None
    payload_sha256: str | None = None

    def party(self, tab_id: str) -> PartyProfile:
        for profile in self.parties:
            if profile.tab_id == tab_id:
                return profile
        raise KeyError(f"Unknown AxleTool team tab: {tab_id}")

    @property
    def action_count(self) -> int:
        return sum(action is not None for turn in self.turns for action in turn.actions)

    @property
    def fingerprint(self) -> str:
        """Stable content fingerprint used to bind preparation approval to this exact plan."""
        encoded = json.dumps(
            asdict(self),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=lambda value: value.value if isinstance(value, Enum) else str(value),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
