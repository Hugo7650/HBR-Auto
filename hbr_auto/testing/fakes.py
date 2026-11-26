"""Convenience imports for tests and local simulation."""

from hbr_auto.battle.runner import FakeBattleRuntime
from hbr_auto.core.device import FakeDevice
from hbr_auto.core.vision import FakeVision

__all__ = ["FakeBattleRuntime", "FakeDevice", "FakeVision"]
