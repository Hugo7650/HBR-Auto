from __future__ import annotations

import json
from pathlib import Path

import pytest

from hbr_auto.battle.axle_import import AxlePlanImporter
from hbr_auto.battle.catalog import SkillCategory, SkillDefinition, StaticAxleCatalog
from hbr_auto.battle.preparation import PartySlotState, PartyState, PreparationPlanner, SkillKey
from hbr_auto.battle.models import ResonanceSupportSpec
from hbr_auto.battle.runner import (
    AvailableSkill,
    BattleExecutionPaused,
    BattlePlanRunner,
    BattleState,
    FakeBattleRuntime,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_axle_payload.json"


def ready_report_and_plan():
    plan = AxlePlanImporter().normalize(json.loads(FIXTURE.read_text(encoding="utf-8")))
    catalog = StaticAxleCatalog()
    catalog.register("char-001", "style-001", SkillDefinition("skill-001", SkillCategory.ACTIVE))
    catalog.register("char-001", "style-001", SkillDefinition("passive-001", SkillCategory.PASSIVE))
    planner = PreparationPlanner(catalog)
    compiled = planner.compile(plan)
    members = [
        PartySlotState(1, "char-001", "style-001", "style-id-001", ("passive-001",), ResonanceSupportSpec())
    ]
    members.extend(
        PartySlotState(slot, None, None, None, (), ResonanceSupportSpec())
        for slot in range(2, 7)
    )
    key = SkillKey("char-001", "style-001", "skill-001")
    current = PartyState(
        tuple(members),
        frozenset({key}),
        frozenset(),
        True,
        True,
        learned_passive_skills=frozenset({SkillKey("char-001", "style-001", "passive-001")}),
    )
    return plan, planner.compare(compiled, current)


def test_runner_requires_preparation_and_user_confirmation() -> None:
    plan, report = ready_report_and_plan()
    state = BattleState(
        "BATTLE",
        "T1",
        (AvailableSkill("char-001", "style-001", "skill-001"),),
        ("char-001",),
        overdrive_level=0,
    )
    runtime = FakeBattleRuntime(state)
    with pytest.raises(PermissionError):
        BattlePlanRunner(runtime).run(plan, report, user_confirmed=False)


def test_runner_validates_each_action_and_turn() -> None:
    plan, report = ready_report_and_plan()
    state = BattleState(
        "BATTLE",
        "T1",
        (AvailableSkill("char-001", "style-001", "skill-001"),),
        ("char-001",),
        overdrive_level=0,
    )
    runtime = FakeBattleRuntime(state)
    # Only the first T1 row is part of the plan being exercised here.
    from dataclasses import replace
    plan = replace(plan, turns=(plan.turns[0],))
    report = replace(report, plan=replace(report.plan, battle_plan_fingerprint=plan.fingerprint))
    assert BattlePlanRunner(runtime).run(plan, report, user_confirmed=True) == 1
    assert len(runtime.executed_actions) == 1
    assert runtime.executed_od == [(1, 1)]


def test_runner_pauses_when_action_cannot_be_verified() -> None:
    plan, report = ready_report_and_plan()
    from dataclasses import replace
    plan = replace(plan, turns=(plan.turns[0],))
    report = replace(report, plan=replace(report.plan, battle_plan_fingerprint=plan.fingerprint))
    state = BattleState(
        "BATTLE",
        "T1",
        (AvailableSkill("char-001", "style-001", "skill-001"),),
        ("char-001",),
        overdrive_level=0,
    )
    runtime = FakeBattleRuntime(state)
    runtime.fail_action_verification = True
    with pytest.raises(BattleExecutionPaused, match="verification"):
        BattlePlanRunner(runtime).run(plan, report, user_confirmed=True)


def test_runner_rejects_ready_report_for_a_different_battle_plan() -> None:
    from dataclasses import replace

    plan, report = ready_report_and_plan()
    altered = replace(plan, name="different plan")
    state = BattleState(
        "BATTLE",
        "T1",
        (AvailableSkill("char-001", "style-001", "skill-001"),),
        ("char-001",),
        overdrive_level=0,
    )
    with pytest.raises(PermissionError, match="different BattlePlan"):
        BattlePlanRunner(FakeBattleRuntime(state)).run(altered, report, user_confirmed=True)
