from __future__ import annotations

import json
from pathlib import Path

import pytest

from hbr_auto.battle.axle_import import AxlePlanImporter
from hbr_auto.battle.catalog import SkillCategory, SkillDefinition, StaticAxleCatalog
from hbr_auto.battle.preparation import (
    ChangeKind,
    PartySlotState,
    PartyState,
    PreparationPlanner,
    PreparationStatus,
    SkillKey,
    authorize_battle,
)
from hbr_auto.battle.models import ResonanceSupportSpec

FIXTURE = Path(__file__).parent / "fixtures" / "sample_axle_payload.json"


def battle_plan():
    return AxlePlanImporter().normalize(json.loads(FIXTURE.read_text(encoding="utf-8")))


def planner():
    catalog = StaticAxleCatalog()
    catalog.register(
        "char-001",
        "style-001",
        SkillDefinition("skill-001", SkillCategory.ACTIVE, display_name="Test skill"),
    )
    catalog.register(
        "char-001",
        "style-001",
        SkillDefinition("passive-001", SkillCategory.PASSIVE, display_name="Test passive"),
    )
    return PreparationPlanner(catalog)


def exact_current_state() -> PartyState:
    members = [
        PartySlotState(
            slot=1,
            character_id="char-001",
            style="style-001",
            style_id="style-id-001",
            passive_skills=("passive-001",),
            support=ResonanceSupportSpec(),
        )
    ]
    members.extend(
        PartySlotState(
            slot=slot,
            character_id=None,
            style=None,
            style_id=None,
            passive_skills=(),
            support=ResonanceSupportSpec(),
        )
        for slot in range(2, 7)
    )
    skill_key = SkillKey("char-001", "style-001", "skill-001")
    return PartyState(
        members=tuple(members),
        learned_skills=frozenset({skill_key}),
        equipped_ex_skills=frozenset(),
        passive_slot_mapping_confirmed=True,
        support_state_verified=True,
        screenshot_evidence="party-state.png",
        learned_passive_skills=frozenset({SkillKey("char-001", "style-001", "passive-001")}),
    )


def test_preparation_compiler_deduplicates_repeated_action_skills() -> None:
    compiled = planner().compile(battle_plan())
    assert len(compiled.required_skills) == 1
    assert compiled.required_skills[0].skill_value == "skill-001"


def test_preparation_diff_is_ready_when_observed_state_matches() -> None:
    prepared = planner()
    compiled = prepared.compile(battle_plan())
    report = prepared.compare(compiled, exact_current_state())
    assert report.status is PreparationStatus.READY
    assert report.ready
    assert report.diff.changes == ()
    authorize_battle(report, user_confirmed=True)


def test_preparation_diff_reports_changes_without_auto_applying() -> None:
    prepared = planner()
    compiled = prepared.compile(battle_plan())
    current = exact_current_state()
    changed = list(current.members)
    changed[0] = PartySlotState(
        slot=1,
        character_id="char-001",
        style="old-style",
        style_id="old-style-id",
        passive_skills=("passive-001",),
        support=ResonanceSupportSpec(),
    )
    current = PartyState(
        members=tuple(changed),
        learned_skills=current.learned_skills,
        equipped_ex_skills=current.equipped_ex_skills,
        passive_slot_mapping_confirmed=True,
        support_state_verified=True,
        learned_passive_skills=current.learned_passive_skills,
    )
    report = prepared.compare(compiled, current)
    assert report.status is PreparationStatus.NEEDS_USER_INPUT
    assert report.diff.changes[0].kind is ChangeKind.SET_STYLE


def test_preparation_requires_passive_slot_mapping_confirmation() -> None:
    prepared = planner()
    compiled = prepared.compile(battle_plan())
    current = exact_current_state()
    current = PartyState(
        members=current.members,
        learned_skills=current.learned_skills,
        equipped_ex_skills=current.equipped_ex_skills,
        passive_slot_mapping_confirmed=False,
        support_state_verified=True,
        learned_passive_skills=current.learned_passive_skills,
    )
    report = prepared.compare(compiled, current)
    assert report.status is PreparationStatus.BLOCKED
    assert any(b.code == "passive_slot_mapping" for b in report.diff.blockers)


def test_preparation_does_not_allow_unknown_skill_catalog() -> None:
    empty = PreparationPlanner(StaticAxleCatalog())
    compiled = empty.compile(battle_plan())
    report = empty.compare(compiled, exact_current_state())
    assert report.status is PreparationStatus.BLOCKED
    assert any(b.code == "unresolved_skill" for b in report.diff.blockers)


def test_multiple_axle_profiles_require_explicit_switch_semantics() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["char"]["2"] = data["char"]["1"]
    data["skills"][2][0]["selectedTab"] = 2
    compiled = planner().compile(AxlePlanImporter().normalize(data))
    report = planner().compare(compiled, exact_current_state())
    assert report.status is PreparationStatus.BLOCKED
    assert any(b.code == "multiple_profiles" for b in report.diff.blockers)


def test_battle_gate_requires_ready_and_user_confirmation() -> None:
    compiled = planner().compile(battle_plan())
    report = planner().compare(compiled, exact_current_state())
    with pytest.raises(PermissionError, match="user confirms"):
        authorize_battle(report, user_confirmed=False)
    blocked = planner().compare(compiled, None)
    with pytest.raises(PermissionError, match="pre-battle preparation"):
        authorize_battle(blocked, user_confirmed=True)


def test_multiple_profiles_remain_blocked_even_when_one_is_selected() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["char"]["2"] = data["char"]["1"]
    data["skills"][2][0]["selectedTab"] = 2
    compiled = planner().compile(AxlePlanImporter().normalize(data))
    report = planner().compare(compiled, exact_current_state(), selected_tab="1")
    assert report.status is PreparationStatus.BLOCKED
    assert any(b.code == "multiple_profiles" for b in report.diff.blockers)


def test_passive_skill_must_be_known_to_be_learned() -> None:
    prepared = planner()
    compiled = prepared.compile(battle_plan())
    current = exact_current_state()
    current = PartyState(
        members=current.members,
        learned_skills=current.learned_skills,
        equipped_ex_skills=current.equipped_ex_skills,
        passive_slot_mapping_confirmed=True,
        support_state_verified=True,
        learned_passive_skills=frozenset(),
    )
    report = prepared.compare(compiled, current)
    assert report.status is PreparationStatus.BLOCKED
    assert any(b.code == "passive_skill_not_learned" for b in report.diff.blockers)


def test_passive_skill_catalog_entry_must_be_classified_as_passive() -> None:
    catalog = StaticAxleCatalog()
    catalog.register(
        "char-001",
        "style-001",
        SkillDefinition("skill-001", SkillCategory.ACTIVE),
    )
    catalog.register(
        "char-001",
        "style-001",
        SkillDefinition("passive-001", SkillCategory.ACTIVE),
    )
    compiled = PreparationPlanner(catalog).compile(battle_plan())
    assert compiled.required_passive_skills == ()
    assert compiled.unresolved_passive_values == (("1", 1, "char-001", "passive-001"),)
