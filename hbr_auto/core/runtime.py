from __future__ import annotations

import importlib
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .device import MaaDevice, SerializedDevice


class RuntimeState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    READY = "READY"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class RuntimeErrorBase(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MaaRuntimeConfig:
    adb_path: Path
    address: str
    image_dirs: tuple[Path, ...] = ()
    ocr_model_dirs: tuple[Path, ...] = ()
    log_dir: Path = Path("logs/maa")
    operation_timeout_seconds: float = 30.0
    load_native_images: bool = True

    def __post_init__(self) -> None:
        if not self.address.strip():
            raise ValueError("ADB address is required")
        if self.operation_timeout_seconds <= 0:
            raise ValueError("operation_timeout_seconds must be positive")


@dataclass(slots=True)
class RuntimeComponents:
    resource: Any
    controller: Any
    tasker: Any


class MaaRuntime:
    """Own Resource, Controller and Tasker lifetime; never posts JSON Pipeline tasks."""

    def __init__(
        self,
        config: MaaRuntimeConfig,
        *,
        factories: dict[str, Callable[..., Any]] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self._factories = factories
        self.logger = logger or logging.getLogger("hbr_auto.runtime")
        self.state = RuntimeState.STOPPED
        self.components: RuntimeComponents | None = None
        self.device: SerializedDevice | None = None

    def _load_factories(self) -> dict[str, Callable[..., Any]]:
        if self._factories is not None:
            return self._factories
        try:
            controller_module = importlib.import_module("maa.controller")
            resource_module = importlib.import_module("maa.resource")
            tasker_module = importlib.import_module("maa.tasker")
        except ImportError as exc:
            raise RuntimeErrorBase(
                "MaaFw is not importable in this interpreter; install the pinned MaaFw version "
                "before starting a device runtime"
            ) from exc
        return {
            "Resource": resource_module.Resource,
            "AdbController": controller_module.AdbController,
            "Tasker": tasker_module.Tasker,
        }

    def _wait_job(self, job: Any, label: str) -> None:
        deadline = time.monotonic() + self.config.operation_timeout_seconds
        while not job.done:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"MaaFramework job timed out while {label}")
            time.sleep(0.05)
        if not job.succeeded:
            raise RuntimeErrorBase(f"MaaFramework job failed while {label}")

    def start(self) -> SerializedDevice:
        if self.state is RuntimeState.READY and self.device is not None:
            return self.device
        if self.state is not RuntimeState.STOPPED:
            raise RuntimeErrorBase(f"Cannot start runtime while state is {self.state.value}")

        self.state = RuntimeState.STARTING
        resource = controller = tasker = None
        try:
            factories = self._load_factories()
            self.config.log_dir.mkdir(parents=True, exist_ok=True)
            resource = factories["Resource"]()

            if self.config.load_native_images:
                for image_dir in self.config.image_dirs:
                    if not image_dir.exists():
                        raise FileNotFoundError(f"MAA image resource directory does not exist: {image_dir}")
                    self._wait_job(resource.post_image(image_dir), f"loading image resources from {image_dir}")
                for model_dir in self.config.ocr_model_dirs:
                    if not model_dir.exists():
                        raise FileNotFoundError(f"MAA OCR model directory does not exist: {model_dir}")
                    self._wait_job(resource.post_ocr_model(model_dir), f"loading OCR model from {model_dir}")

            controller = factories["AdbController"](
                adb_path=self.config.adb_path,
                address=self.config.address,
            )
            self._wait_job(controller.post_connection(), f"connecting to ADB device {self.config.address}")
            if not bool(controller.connected):
                raise RuntimeErrorBase(f"MaaFramework reports ADB device {self.config.address} disconnected")

            tasker = factories["Tasker"]()
            if not tasker.bind(resource, controller):
                raise RuntimeErrorBase("Failed to bind Maa Resource and Controller to Tasker")
            if not tasker.inited:
                raise RuntimeErrorBase("Maa Tasker did not initialize after binding")

            # Confirm screenshot transport before exposing this Runtime to game features.
            screenshot_job = controller.post_screencap()
            self._wait_job(screenshot_job, "taking the initial screenshot")
            image = screenshot_job.get()
            if image is None or getattr(image, "size", 0) == 0:
                raise RuntimeErrorBase("Initial ADB screenshot is empty")

            self.components = RuntimeComponents(resource, controller, tasker)
            self.device = SerializedDevice(MaaDevice(controller))
            self.state = RuntimeState.READY
            self.logger.info("MaaRuntime ready for device %s", self.config.address)
            return self.device
        except Exception:
            self.state = RuntimeState.FAILED
            # Let Maa wrapper destructors release partially created native handles.
            tasker = controller = resource = None
            raise

    def require_ready(self) -> RuntimeComponents:
        if self.state is not RuntimeState.READY or self.components is None:
            raise RuntimeErrorBase("MaaRuntime is not ready")
        return self.components

    def close(self) -> None:
        if self.state in (RuntimeState.STOPPED, RuntimeState.STOPPING):
            return
        self.state = RuntimeState.STOPPING
        components = self.components
        if components is not None:
            try:
                stop_job = components.tasker.post_stop()
                self._wait_job(stop_job, "stopping Tasker")
            except Exception:
                self.logger.exception("Failed to stop Maa Tasker cleanly")
        self.device = None
        self.components = None
        self.state = RuntimeState.STOPPED

    def __enter__(self) -> "MaaRuntime":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
