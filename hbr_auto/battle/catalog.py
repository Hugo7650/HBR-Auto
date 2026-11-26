from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class SkillCategory(str, Enum):
    ACTIVE = "ACTIVE"
    EX = "EX"
    PASSIVE = "PASSIVE"
    SWITCH = "SWITCH"
    COMMAND = "COMMAND"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    value: str
    category: SkillCategory
    requires_equipment: bool = False
    display_name: str | None = None
    sp_cost: int | None = None


class AxleCatalog(Protocol):
    def resolve_skill(
        self,
        *,
        team: str | None,
        character_id: str,
        style: str | None,
        skill_value: str,
    ) -> SkillDefinition | None: ...


class EmptyAxleCatalog:
    """Fail-closed catalog used until a reviewed game-data source is configured."""

    def resolve_skill(
        self,
        *,
        team: str | None,
        character_id: str,
        style: str | None,
        skill_value: str,
    ) -> SkillDefinition | None:
        return None


class StaticAxleCatalog:
    """In-memory catalog intended for reviewed local data and unit tests."""

    def __init__(self, entries: dict[tuple[str, str, str], SkillDefinition] | None = None) -> None:
        self._entries = dict(entries or {})

    def register(
        self,
        character_id: str,
        style: str,
        skill: SkillDefinition,
    ) -> None:
        key = (character_id, style, skill.value)
        if key in self._entries:
            raise ValueError(f"Duplicate AxleCatalog entry: {key}")
        self._entries[key] = skill

    def resolve_skill(
        self,
        *,
        team: str | None,
        character_id: str,
        style: str | None,
        skill_value: str,
    ) -> SkillDefinition | None:
        if style is None:
            return None
        return self._entries.get((character_id, style, skill_value))
