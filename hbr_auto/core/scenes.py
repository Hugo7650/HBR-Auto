from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .device import DeviceInterface
from .vision import RecognitionResult, VisionInterface


@dataclass(frozen=True, slots=True)
class SceneObservation:
    name: str
    confidence: float
    evidence: tuple[RecognitionResult, ...] = ()


@dataclass(frozen=True, slots=True)
class SceneProbe:
    name: str
    match: Callable[[np.ndarray, VisionInterface], RecognitionResult]
    threshold: float = 0.85

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Scene name cannot be empty")
        if not 0 <= self.threshold <= 1:
            raise ValueError("Scene threshold must be between 0 and 1")


class AmbiguousSceneError(RuntimeError):
    pass


class SceneDetector:
    UNKNOWN = "UNKNOWN"

    def __init__(self, vision: VisionInterface, probes: tuple[SceneProbe, ...] = ()) -> None:
        self.vision = vision
        self.probes = probes
        names = [probe.name for probe in probes]
        if len(names) != len(set(names)):
            raise ValueError("Scene probe names must be unique")

    def detect(self, image: np.ndarray) -> SceneObservation:
        observations: list[SceneObservation] = []
        for probe in self.probes:
            result = probe.match(image, self.vision)
            if result.found and result.score is not None and result.score >= probe.threshold:
                observations.append(SceneObservation(probe.name, result.score, (result,)))
        observations.sort(key=lambda item: item.confidence, reverse=True)
        if not observations:
            return SceneObservation(self.UNKNOWN, 0.0)
        if len(observations) > 1 and observations[0].confidence - observations[1].confidence < 0.03:
            return SceneObservation(self.UNKNOWN, observations[0].confidence, tuple(
                evidence for item in observations[:2] for evidence in item.evidence
            ))
        return observations[0]


class SceneManager:
    def __init__(self, detector: SceneDetector, device: DeviceInterface) -> None:
        self.detector = detector
        self.device = device
        self.current: SceneObservation = SceneObservation(SceneDetector.UNKNOWN, 0.0)

    def refresh(self) -> SceneObservation:
        self.current = self.detector.detect(self.device.screencap())
        return self.current

    def require(self, scene_name: str) -> SceneObservation:
        observation = self.refresh()
        if observation.name != scene_name:
            raise RuntimeError(
                f"Expected scene {scene_name!r}, observed {observation.name!r}; no input was sent"
            )
        return observation


@dataclass(frozen=True, slots=True)
class Transition:
    source: str
    target: str
    apply: Callable[[DeviceInterface], None]


class Navigator:
    """Find one unambiguous route and verify every resulting scene before continuing."""

    def __init__(self, scene_manager: SceneManager, transitions: tuple[Transition, ...] = ()) -> None:
        self.scene_manager = scene_manager
        self.transitions = transitions

    def _unique_route(self, source: str, target: str, max_steps: int) -> tuple[Transition, ...]:
        if source == target:
            return ()
        routes: list[tuple[Transition, ...]] = []
        frontier: list[tuple[str, tuple[Transition, ...], frozenset[str]]] = [
            (source, (), frozenset({source}))
        ]
        for depth in range(1, max_steps + 1):
            next_frontier: list[tuple[str, tuple[Transition, ...], frozenset[str]]] = []
            for scene, route, visited in frontier:
                for transition in self.transitions:
                    if transition.source != scene or transition.target in visited:
                        continue
                    next_route = (*route, transition)
                    if transition.target == target:
                        routes.append(next_route)
                    else:
                        next_frontier.append(
                            (transition.target, next_route, visited | {transition.target})
                        )
            if routes:
                break
            frontier = next_frontier
            if not frontier:
                break
        if not routes:
            raise RuntimeError(f"No verified navigation route from {source!r} to {target!r}")
        if len(routes) != 1:
            raise AmbiguousSceneError(
                f"Found {len(routes)} equally short navigation routes from {source!r} to {target!r}"
            )
        return routes[0]

    def navigate(self, target: str, *, max_steps: int = 5) -> tuple[SceneObservation, ...]:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        initial = self.scene_manager.refresh()
        visited: list[SceneObservation] = [initial]
        if initial.name == target:
            return tuple(visited)
        route = self._unique_route(initial.name, target, max_steps)
        for transition in route:
            current = self.scene_manager.current
            if current.name != transition.source:
                raise RuntimeError(
                    f"Navigation state drifted: expected {transition.source!r}, observed {current.name!r}"
                )
            transition.apply(self.scene_manager.device)
            observed = self.scene_manager.refresh()
            visited.append(observed)
            if observed.name != transition.target:
                raise RuntimeError(
                    f"Navigation transition expected {transition.target!r}, observed {observed.name!r}; "
                    "stopping before the next input"
                )
        if self.scene_manager.current.name != target:
            raise TimeoutError(f"Could not reach scene {target!r} within {max_steps} transitions")
        return tuple(visited)


@dataclass(frozen=True, slots=True)
class PopupRule:
    name: str
    detect: Callable[[np.ndarray, VisionInterface], RecognitionResult]
    dismiss: Callable[[DeviceInterface, RecognitionResult], None]
    threshold: float = 0.9

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Popup rule name cannot be empty")
        if not 0 <= self.threshold <= 1:
            raise ValueError("Popup threshold must be between 0 and 1")


class PopupHandler:
    def __init__(self, device: DeviceInterface, vision: VisionInterface) -> None:
        self.device = device
        self.vision = vision
        self.rules: list[PopupRule] = []

    def register(self, rule: PopupRule) -> None:
        if any(existing.name == rule.name for existing in self.rules):
            raise ValueError(f"Popup rule already registered: {rule.name}")
        self.rules.append(rule)

    def handle_one(self) -> str | None:
        frame = self.device.screencap()
        matched: list[tuple[PopupRule, RecognitionResult]] = []
        for rule in self.rules:
            result = rule.detect(frame, self.vision)
            if result.found and result.score is not None and result.score >= rule.threshold:
                matched.append((rule, result))
        if not matched:
            return None
        if len(matched) != 1:
            raise AmbiguousSceneError("Multiple popup rules matched; refusing to guess which one to dismiss")
        rule, result = matched[0]
        rule.dismiss(self.device, result)
        after = rule.detect(self.device.screencap(), self.vision)
        if after.found and after.score is not None and after.score >= rule.threshold:
            raise RuntimeError(f"Popup {rule.name!r} is still visible after its dismiss action")
        return rule.name
