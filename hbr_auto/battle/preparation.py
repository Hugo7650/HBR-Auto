from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .catalog import AxleCatalog, SkillCategory
from .models import BattleAction, BattlePlan, PartyMemberSpec, PartyProfile, ResonanceSupportSpec


class PreparationStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    ANALYZING = "ANALYZING"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    APPLYING = "APPLYING"
    VERIFYING = "VERIFYING"
    READY = "READY"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ChangeKind(str, Enum):
    SET_PARTY_MEMBER = "SET_PARTY_MEMBER"
    SET_STYLE = "SET_STYLE"
    SET_PASSIVE_SKILLS = "SET_PASSIVE_SKILLS"
    EQUIP_EX_SKILL = "EQUIP_EX_SKILL"
    SET_RESONANCE_SUPPORT = "SET_RESONANCE_SUPPORT"


@dataclass(frozen=True, slots=True)
class SkillKey:
    character_id: str
    style: str
    skill_value: str


@dataclass(frozen=True, slots=True)
class RequiredSkill:
    team_tab: str
    character_id: str
    style: str
    skill_value: str
    category: SkillCategory
    requires_equipment: bool
    display_name: str | None = None

    @property
    def key(self) -> SkillKey:
        return SkillKey(self.character_id, self.style, self.skill_value)


@dataclass(frozen=True, slots=True)
class RequiredPassiveSkill:
    team_tab: str
    slot: int
    character_id: str
    style: str
    skill_value: str
    display_name: str | None = None

    @property
    def key(self) -> SkillKey:
        return SkillKey(self.character_id, self.style, self.skill_value)


@dataclass(frozen=True, slots=True)
class PreparationPlan:
    battle_plan_name: str
    battle_plan_fingerprint: str
    profiles: tuple[PartyProfile, ...]
    required_skills: tuple[RequiredSkill, ...]
    required_passive_skills: tuple[RequiredPassiveSkill, ...] = ()
    unresolved_skill_values: tuple[tuple[str, str | None, str | None], ...] = ()
    unresolved_passive_values: tuple[tuple[str, int, str, str], ...] = ()

    def profile(self, tab_id: str) -> PartyProfile:
        for profile in self.profiles:
            if profile.tab_id == tab_id:
                return profile
        raise KeyError(f"Unknown PartyProfile tab: {tab_id}")


@dataclass(frozen=True, slots=True)
class PartySlotState:
    slot: int
    character_id: str | None
    style: str | None
    style_id: str | None
    passive_skills: tuple[str, ...] | None
    support: ResonanceSupportSpec | None
    known: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.slot <= 6:
            raise ValueError("Party slot must be in 1..6")


@dataclass(frozen=True, slots=True)
class PartyState:
    members: tuple[PartySlotState | None, ...]
    learned_skills: frozenset[SkillKey] | None
    equipped_ex_skills: frozenset[SkillKey] | None
    passive_slot_mapping_confirmed: bool = False
    support_state_verified: bool = False
    screenshot_evidence: str | None = None
    learned_passive_skills: frozenset[SkillKey] | None = None

    def __post_init__(self) -> None:
        if len(self.members) != 6:
            raise ValueError("PartyState must contain exactly six slot observations")


@dataclass(frozen=True, slots=True)
class PreparationChange:
    kind: ChangeKind
    slot: int
    current_value: str | None
    target_value: str | None
    description: str
    requires_confirmation: bool = True


@dataclass(frozen=True, slots=True)
class PreparationBlocker:
    code: str
    message: str
    fatal: bool = True
    slot: int | None = None


@dataclass(frozen=True, slots=True)
class PreparationDiff:
    changes: tuple[PreparationChange, ...] = ()
    blockers: tuple[PreparationBlocker, ...] = ()

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)

    @property
    def blocked(self) -> bool:
        return any(blocker.fatal for blocker in self.blockers)


@dataclass(frozen=True, slots=True)
class PreparationReport:
    status: PreparationStatus
    plan: PreparationPlan
    selected_tab: str | None
    diff: PreparationDiff
    verified_items: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    user_confirmed: bool = False

    @property
    def ready(self) -> bool:
        return self.status is PreparationStatus.READY

    @property
    def battle_allowed(self) -> bool:
        return self.ready and self.user_confirmed


class PreparationPlanner:
    """Compile battle requirements and calculate a fail-closed, idempotent diff."""

    def __init__(self, catalog: AxleCatalog) -> None:
        self.catalog = catalog

    def compile(self, battle_plan: BattlePlan) -> PreparationPlan:
        required: dict[tuple[str, str, str, str], RequiredSkill] = {}
        required_passives: dict[tuple[str, int, str, str, str], RequiredPassiveSkill] = {}
        unresolved: list[tuple[str, str | None, str | None]] = []
        unresolved_passives: list[tuple[str, int, str, str]] = []

        for profile in battle_plan.parties:
            for member in profile.members:
                if member is None:
                    continue
                for skill_value in member.passive_skills:
                    if member.style is None:
                        unresolved_passives.append(
                            (profile.tab_id, member.slot, member.character_id, skill_value)
                        )
                        continue
                    definition = self.catalog.resolve_skill(
                        team=member.team,
                        character_id=member.character_id,
                        style=member.style,
                        skill_value=skill_value,
                    )
                    if definition is None or definition.category is not SkillCategory.PASSIVE:
                        unresolved_passives.append(
                            (profile.tab_id, member.slot, member.character_id, skill_value)
                        )
                        continue
                    key = (profile.tab_id, member.slot, member.character_id, member.style, skill_value)
                    required_passives[key] = RequiredPassiveSkill(
                        team_tab=profile.tab_id,
                        slot=member.slot,
                        character_id=member.character_id,
                        style=member.style,
                        skill_value=skill_value,
                        display_name=definition.display_name,
                    )

        for turn in battle_plan.turns:
            for action in turn.actions:
                if action is None:
                    continue
                if action.character_id is None or action.style is None or action.skill_value is None:
                    unresolved.append((action.team_tab, action.character_id, action.skill_value))
                    continue
                profile = battle_plan.party(action.team_tab)
                member = next(
                    (m for m in profile.members if m and m.character_id == action.character_id),
                    None,
                )
                definition = self.catalog.resolve_skill(
                    team=member.team if member else None,
                    character_id=action.character_id,
                    style=action.style,
                    skill_value=action.skill_value,
                )
                if definition is None:
                    unresolved.append((action.team_tab, action.character_id, action.skill_value))
                    continue
                required_key = (action.team_tab, action.character_id, action.style, action.skill_value)
                required[required_key] = RequiredSkill(
                    team_tab=action.team_tab,
                    character_id=action.character_id,
                    style=action.style,
                    skill_value=action.skill_value,
                    category=definition.category,
                    requires_equipment=definition.requires_equipment,
                    display_name=definition.display_name,
                )
        return PreparationPlan(
            battle_plan_name=battle_plan.name,
            battle_plan_fingerprint=battle_plan.fingerprint,
            profiles=battle_plan.parties,
            required_skills=tuple(required.values()),
            required_passive_skills=tuple(required_passives.values()),
            unresolved_skill_values=tuple(unresolved),
            unresolved_passive_values=tuple(unresolved_passives),
        )

    def compare(
        self,
        plan: PreparationPlan,
        current: PartyState | None,
        *,
        selected_tab: str | None = None,
    ) -> PreparationReport:
        blockers: list[PreparationBlocker] = []
        changes: list[PreparationChange] = []
        if len(plan.profiles) > 1:
            blockers.append(
                PreparationBlocker(
                    "multiple_profiles",
                    "The plan references multiple AxleTool team tabs. This release has no verified "
                    "in-game profile-switch executor, so this plan cannot reach READY.",
                )
            )
        if selected_tab is None and len(plan.profiles) == 1:
            selected_tab = plan.profiles[0].tab_id
        target_profile = None
        if selected_tab is not None:
            try:
                target_profile = plan.profile(selected_tab)
            except KeyError:
                blockers.append(PreparationBlocker("unknown_profile", f"Unknown profile {selected_tab!r}"))

        if plan.unresolved_skill_values:
            blockers.extend(
                PreparationBlocker(
                    "unresolved_skill",
                    f"Cannot resolve action skill {skill!r} for character {character!r} in tab {tab!r}.",
                )
                for tab, character, skill in plan.unresolved_skill_values
            )
        if plan.unresolved_passive_values:
            blockers.extend(
                PreparationBlocker(
                    "unresolved_passive_skill",
                    f"Cannot resolve passive skill {skill!r} for character {character!r}, "
                    f"slot {slot} in tab {tab!r}.",
                    slot=slot,
                )
                for tab, slot, character, skill in plan.unresolved_passive_values
            )

        if current is None:
            blockers.append(PreparationBlocker("current_party_unknown", "Current party state has not been observed"))
        elif target_profile is not None:
            self._compare_members(target_profile, current, changes, blockers)
            self._compare_skills(plan, current, changes, blockers)
            self._compare_passive_skills(plan, current, blockers)

        if blockers:
            status = PreparationStatus.NEEDS_USER_INPUT if any(not b.fatal for b in blockers) else PreparationStatus.BLOCKED
        elif changes:
            status = PreparationStatus.NEEDS_USER_INPUT
        else:
            status = PreparationStatus.READY
        return PreparationReport(status, plan, selected_tab, PreparationDiff(tuple(changes), tuple(blockers)))

    def _compare_members(
        self,
        target: PartyProfile,
        current: PartyState,
        changes: list[PreparationChange],
        blockers: list[PreparationBlocker],
    ) -> None:
        for index, expected in enumerate(target.members, start=1):
            observed = current.members[index - 1]
            if observed is None or not observed.known:
                blockers.append(
                    PreparationBlocker("slot_unknown", f"Current party slot {index} is not reliably identified", slot=index)
                )
                continue
            expected_character = expected.character_id if expected else None
            if observed.character_id != expected_character:
                changes.append(
                    PreparationChange(
                        ChangeKind.SET_PARTY_MEMBER,
                        index,
                        observed.character_id,
                        expected_character,
                        f"Set party slot {index} character",
                    )
                )
            if expected is not None and observed.character_id == expected.character_id:
                if observed.style != expected.style or observed.style_id != expected.style_id:
                    changes.append(
                        PreparationChange(
                            ChangeKind.SET_STYLE,
                            index,
                            observed.style,
                            expected.style,
                            f"Set slot {index} style for {expected.character_id}",
                        )
                    )
                if observed.passive_skills is None:
                    blockers.append(
                        PreparationBlocker(
                            "passive_state_unknown",
                            f"Passive skill slots for party slot {index} are unknown",
                            slot=index,
                        )
                    )
                elif expected.passive_skills or observed.passive_skills:
                    if not current.passive_slot_mapping_confirmed:
                        blockers.append(
                            PreparationBlocker(
                                "passive_slot_mapping",
                                f"Passive-skill values for slot {index} have no confirmed slot mapping",
                                slot=index,
                            )
                        )
                    elif tuple(observed.passive_skills) != tuple(expected.passive_skills):
                        changes.append(
                            PreparationChange(
                                ChangeKind.SET_PASSIVE_SKILLS,
                                index,
                                ",".join(observed.passive_skills),
                                ",".join(expected.passive_skills),
                                f"Set passive skills for party slot {index}",
                            )
                        )
                if observed.support is None or not current.support_state_verified:
                    blockers.append(
                        PreparationBlocker(
                            "support_state_unknown",
                            f"Resonance support for party slot {index} is not verified",
                            slot=index,
                        )
                    )
                elif expected.support != observed.support:
                    changes.append(
                        PreparationChange(
                            ChangeKind.SET_RESONANCE_SUPPORT,
                            index,
                            observed.support.character_id,
                            expected.support.character_id,
                            f"Set resonance support for party slot {index}",
                        )
                    )

    def _compare_skills(
        self,
        plan: PreparationPlan,
        current: PartyState,
        changes: list[PreparationChange],
        blockers: list[PreparationBlocker],
    ) -> None:
        for required in plan.required_skills:
            key = required.key
            if required.category not in (SkillCategory.ACTIVE, SkillCategory.EX):
                blockers.append(
                    PreparationBlocker(
                        "unsupported_skill_category",
                        f"Skill {required.skill_value!r} has unsupported category {required.category.value}",
                    )
                )
                continue
            if current.learned_skills is None:
                blockers.append(
                    PreparationBlocker("learned_skills_unknown", f"Learned state is unknown for {required.skill_value!r}")
                )
            elif key not in current.learned_skills:
                blockers.append(
                    PreparationBlocker("skill_not_learned", f"Required skill {required.skill_value!r} is not learned")
                )
            if required.category is SkillCategory.EX or required.requires_equipment:
                if current.equipped_ex_skills is None:
                    blockers.append(
                        PreparationBlocker("ex_equipment_unknown", f"EX equipment state is unknown for {required.skill_value!r}")
                    )
                elif key not in current.equipped_ex_skills:
                    changes.append(
                        PreparationChange(
                            ChangeKind.EQUIP_EX_SKILL,
                            0,
                            None,
                            required.skill_value,
                            f"Equip required EX skill {required.skill_value}",
                        )
                    )

    def _compare_passive_skills(
        self,
        plan: PreparationPlan,
        current: PartyState,
        blockers: list[PreparationBlocker],
    ) -> None:
        for required in plan.required_passive_skills:
            if current.learned_passive_skills is None:
                blockers.append(
                    PreparationBlocker(
                        "learned_passive_skills_unknown",
                        f"Learned state is unknown for passive skill {required.skill_value!r}",
                        slot=required.slot,
                    )
                )
            elif required.key not in current.learned_passive_skills:
                blockers.append(
                    PreparationBlocker(
                        "passive_skill_not_learned",
                        f"Required passive skill {required.skill_value!r} has not been learned",
                        slot=required.slot,
                    )
                )


class DryRunPreparationExecutor:
    """Preview-only implementation; it intentionally never sends device input."""

    def __init__(self, planner: PreparationPlanner) -> None:
        self.planner = planner

    def preview(
        self,
        plan: PreparationPlan,
        current: PartyState | None,
        *,
        selected_tab: str | None = None,
    ) -> PreparationReport:
        return self.planner.compare(plan, current, selected_tab=selected_tab)


def authorize_battle(report: PreparationReport, *, user_confirmed: bool) -> None:
    if report.status is not PreparationStatus.READY:
        raise PermissionError(
            f"Battle is locked: pre-battle preparation status is {report.status.value}, not READY"
        )
    if not user_confirmed:
        raise PermissionError("Battle is locked until the user confirms the verified preparation report")
