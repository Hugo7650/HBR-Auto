from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import BattleAction, BattlePlan, BattleTurn, TurnKind
from .preparation import PreparationReport, authorize_battle


class BattleExecutionPaused(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AvailableSkill:
    character_id: str
    style: str
    skill_value: str


@dataclass(frozen=True, slots=True)
class BattleState:
    scene: str
    turn_label: str
    available_skills: tuple[AvailableSkill, ...]
    available_targets: tuple[str, ...]
    overdrive_level: int
    overdrive_bonus: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedAction:
    action: BattleAction
    target_value: str | None


class BattleRuntimeAdapter(Protocol):
    def analyze(self) -> BattleState: ...

    def execute_action(self, action: ResolvedAction) -> None: ...

    def verify_action(self, action: ResolvedAction, state: BattleState) -> bool: ...

    def execute_overdrive(self, level: int, bonus: int | None) -> None: ...

    def verify_overdrive(self, level: int, bonus: int | None, state: BattleState) -> bool: ...

    def handle_special_turn(self, turn: BattleTurn) -> None: ...

    def verify_turn_complete(self, turn: BattleTurn, state: BattleState) -> bool: ...


class TurnTracker:
    def validate(self, planned: BattleTurn, observed: BattleState) -> None:
        if observed.scene != "BATTLE":
            raise BattleExecutionPaused(f"Expected BATTLE scene, observed {observed.scene!r}")
        if observed.turn_label != planned.label:
            raise BattleExecutionPaused(
                f"Turn mismatch: plan expects {planned.label!r}, game shows {observed.turn_label!r}"
            )


class ActionResolver:
    def resolve(self, action: BattleAction, state: BattleState) -> ResolvedAction:
        if action.character_id is None or action.style is None or action.skill_value is None:
            raise BattleExecutionPaused("Action has unresolved character, style or skill metadata")
        candidates = [
            skill
            for skill in state.available_skills
            if skill.character_id == action.character_id
            and skill.style == action.style
            and skill.skill_value == action.skill_value
        ]
        if len(candidates) != 1:
            raise BattleExecutionPaused(
                f"Expected exactly one available instance of skill {action.skill_value!r}; found {len(candidates)}"
            )
        if action.target_value is not None and action.target_value not in state.available_targets:
            raise BattleExecutionPaused(f"Target {action.target_value!r} is not currently selectable")
        return ResolvedAction(action, action.target_value)


class BattlePlanRunner:
    """Strict per-turn/per-action orchestration over an explicitly supplied runtime adapter."""

    def __init__(
        self,
        runtime: BattleRuntimeAdapter,
        *,
        tracker: TurnTracker | None = None,
        resolver: ActionResolver | None = None,
    ) -> None:
        self.runtime = runtime
        self.tracker = tracker or TurnTracker()
        self.resolver = resolver or ActionResolver()

    def run(
        self,
        plan: BattlePlan,
        preparation: PreparationReport,
        *,
        user_confirmed: bool,
    ) -> int:
        authorize_battle(preparation, user_confirmed=user_confirmed)
        if preparation.plan.battle_plan_fingerprint != plan.fingerprint:
            raise PermissionError(
                "Battle is locked: READY preparation report belongs to a different BattlePlan"
            )
        completed_turns = 0
        for turn in plan.turns:
            before = self.runtime.analyze()
            self.tracker.validate(turn, before)
            if turn.kind in (TurnKind.SWITCH, TurnKind.EXTRA, TurnKind.UNKNOWN):
                if turn.kind is TurnKind.UNKNOWN:
                    raise BattleExecutionPaused(f"Unsupported special turn label: {turn.label!r}")
                self.runtime.handle_special_turn(turn)
            else:
                for action in turn.actions:
                    if action is None:
                        continue
                    before_action = self.runtime.analyze()
                    self.tracker.validate(turn, before_action)
                    resolved = self.resolver.resolve(action, before_action)
                    self.runtime.execute_action(resolved)
                    after_action = self.runtime.analyze()
                    if not self.runtime.verify_action(resolved, after_action):
                        raise BattleExecutionPaused(
                            f"Action verification failed for turn {turn.label!r}, slot {action.slot}"
                        )
            if turn.overdrive is not None:
                od = turn.overdrive
                if not od.supported:
                    raise BattleExecutionPaused(f"Unsupported OD instruction {od.raw!r}")
                self.runtime.execute_overdrive(od.level or 0, od.bonus)
                after_od = self.runtime.analyze()
                if not self.runtime.verify_overdrive(od.level or 0, od.bonus, after_od):
                    raise BattleExecutionPaused(f"OD verification failed for turn {turn.label!r}")
            after_turn = self.runtime.analyze()
            if not self.runtime.verify_turn_complete(turn, after_turn):
                raise BattleExecutionPaused(f"Turn completion could not be verified: {turn.label!r}")
            completed_turns += 1
        return completed_turns


class FakeBattleRuntime:
    """Simulation adapter. It records intent and can inject verification failures."""

    def __init__(self, initial_state: BattleState) -> None:
        self.state = initial_state
        self.executed_actions: list[ResolvedAction] = []
        self.executed_od: list[tuple[int, int | None]] = []
        self.special_turns: list[str] = []
        self.fail_action_verification = False

    def analyze(self) -> BattleState:
        return self.state

    def execute_action(self, action: ResolvedAction) -> None:
        self.executed_actions.append(action)

    def verify_action(self, action: ResolvedAction, state: BattleState) -> bool:
        return not self.fail_action_verification

    def execute_overdrive(self, level: int, bonus: int | None) -> None:
        self.executed_od.append((level, bonus))

    def verify_overdrive(self, level: int, bonus: int | None, state: BattleState) -> bool:
        return True

    def handle_special_turn(self, turn: BattleTurn) -> None:
        self.special_turns.append(turn.label)

    def verify_turn_complete(self, turn: BattleTurn, state: BattleState) -> bool:
        return True
