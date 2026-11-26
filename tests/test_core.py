from __future__ import annotations

import logging
import time

import numpy as np
import pytest

from hbr_auto.core.device import CoordinateMapper, FakeDevice, ScreenshotCache, SerializedDevice
from hbr_auto.core.scenes import SceneDetector, SceneProbe, SceneManager, Navigator, Transition
from hbr_auto.core.tasks import (
    FunctionTask,
    TaskContext,
    TaskRegistry,
    TaskScheduler,
    TaskStatus,
)
from hbr_auto.core.vision import FakeVision, RecognitionResult


def test_coordinate_mapper_scales_and_clamps() -> None:
    mapper = CoordinateMapper(1920, 1080)
    assert mapper.map_point(960, 540, (1280, 720)) == (640, 360)
    assert mapper.map_point(5000, -2, (1280, 720)) == (1279, 0)


def test_screenshot_cache_returns_copy_and_expires() -> None:
    cache = ScreenshotCache(ttl_seconds=10)
    image = np.zeros((10, 20, 3), dtype=np.uint8)
    frame = cache.put(image)
    image[0, 0, 0] = 255
    cached = cache.get()
    assert cached is not None
    assert cached.image[0, 0, 0] == 0
    cache.invalidate()
    assert cache.get() is None
    assert frame.width == 20 and frame.height == 10


def test_serialized_device_calls_fake_device_in_order() -> None:
    underlying = FakeDevice()
    device = SerializedDevice(underlying)
    device.click(2, 3)
    image = device.screencap()
    assert image.shape == (1080, 1920, 3)
    assert underlying.actions[0] == ("click", 2, 3)
    assert underlying.actions[1] == ("screencap",)


def test_scene_detector_uses_unknown_for_ambiguous_recognition() -> None:
    device = FakeDevice()
    vision = FakeVision()
    vision.template_results["a"] = RecognitionResult("TemplateMatch", True, score=0.91)
    vision.template_results["b"] = RecognitionResult("TemplateMatch", True, score=0.90)
    detector = SceneDetector(
        vision,
        (
            SceneProbe("A", lambda image, adapter: adapter.match_template(image, "a")),
            SceneProbe("B", lambda image, adapter: adapter.match_template(image, "b")),
        ),
    )
    assert detector.detect(device.screencap()).name == SceneDetector.UNKNOWN


def test_navigator_verifies_scene_after_transition() -> None:
    device = FakeDevice()
    vision = FakeVision()
    current = {"scene": "HOME"}

    def home_match(image, adapter):
        return RecognitionResult("TemplateMatch", current["scene"] == "HOME", score=0.99)

    def battle_match(image, adapter):
        return RecognitionResult("TemplateMatch", current["scene"] == "BATTLE", score=0.99)

    detector = SceneDetector(
        vision,
        (SceneProbe("HOME", home_match), SceneProbe("BATTLE", battle_match)),
    )
    manager = SceneManager(detector, device)
    navigator = Navigator(
        manager,
        (Transition("HOME", "BATTLE", lambda _: current.update(scene="BATTLE")),),
    )
    observations = navigator.navigate("BATTLE")
    assert [item.name for item in observations] == ["HOME", "BATTLE"]


def test_task_registry_orders_dependencies_and_scheduler_runs_serially() -> None:
    events: list[str] = []
    registry = TaskRegistry()
    registry.register(FunctionTask("first", lambda ctx: events.append("first")))
    registry.register(FunctionTask("second", lambda ctx: events.append("second"), dependencies=("first",)))
    context = TaskContext(FakeDevice(), FakeVision(), logging.getLogger("tests"))
    report = TaskScheduler(registry).run("second", context)
    assert report.succeeded
    assert events == ["first", "second"]


def test_task_registry_detects_dependency_cycles() -> None:
    registry = TaskRegistry()
    registry.register(FunctionTask("a", lambda _: None, dependencies=("b",)))
    registry.register(FunctionTask("b", lambda _: None, dependencies=("a",)))
    with pytest.raises(ValueError, match="cycle"):
        registry.topological_order("a")


def test_task_timeout_is_cooperative_and_stops_following_tasks() -> None:
    events: list[str] = []
    registry = TaskRegistry()
    registry.register(FunctionTask("slow", lambda _: time.sleep(0.02), timeout_seconds=0.001))
    registry.register(FunctionTask("after", lambda _: events.append("after"), dependencies=("slow",)))
    context = TaskContext(FakeDevice(), FakeVision(), logging.getLogger("tests"))
    report = TaskScheduler(registry).run("after", context)
    assert report.records[0].status is TaskStatus.TIMED_OUT
    assert events == []


def test_navigator_rejects_ambiguous_equal_length_routes_before_input() -> None:
    device = FakeDevice()
    vision = FakeVision()
    current = {"scene": "HOME"}
    probes = tuple(
        SceneProbe(name, lambda image, adapter, expected=name: RecognitionResult(
            "TemplateMatch", current["scene"] == expected, score=0.99
        ))
        for name in ("HOME", "MENU", "SETTINGS", "STAGE")
    )
    manager = SceneManager(SceneDetector(vision, probes), device)
    navigator = Navigator(
        manager,
        (
            Transition("HOME", "MENU", lambda _: None),
            Transition("MENU", "STAGE", lambda _: None),
            Transition("HOME", "SETTINGS", lambda _: None),
            Transition("SETTINGS", "STAGE", lambda _: None),
        ),
    )
    from hbr_auto.core.scenes import AmbiguousSceneError
    with pytest.raises(AmbiguousSceneError, match="routes"):
        navigator.navigate("STAGE")
    assert device.actions == [("screencap",)]


def test_navigator_stops_immediately_when_transition_lands_on_wrong_scene() -> None:
    device = FakeDevice()
    vision = FakeVision()
    current = {"scene": "HOME"}
    probes = tuple(
        SceneProbe(name, lambda image, adapter, expected=name: RecognitionResult(
            "TemplateMatch", current["scene"] == expected, score=0.99
        ))
        for name in ("HOME", "MENU", "STAGE")
    )
    manager = SceneManager(SceneDetector(vision, probes), device)
    navigator = Navigator(
        manager,
        (
            Transition("HOME", "MENU", lambda _: current.update(scene="STAGE")),
            Transition("MENU", "STAGE", lambda _: None),
        ),
    )
    with pytest.raises(RuntimeError, match="expected 'MENU'"):
        navigator.navigate("STAGE")
    assert device.actions == [("screencap",), ("screencap",)]
