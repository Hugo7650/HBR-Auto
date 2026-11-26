from __future__ import annotations

import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np


class DeviceError(RuntimeError):
    """Base exception for device operations."""


class DeviceDisconnectedError(DeviceError):
    """Raised when an operation is requested without a connected device."""


class ControllerOperationError(DeviceError):
    """Raised when a MaaFramework controller job fails."""


@runtime_checkable
class DeviceInterface(Protocol):
    @property
    def connected(self) -> bool: ...

    @property
    def resolution(self) -> tuple[int, int]: ...

    def screencap(self) -> np.ndarray: ...

    def click(self, x: int, y: int) -> None: ...

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None: ...

    def press_key(self, keycode: int) -> None: ...


@dataclass(frozen=True, slots=True)
class AdbDeviceInfo:
    serial: str
    state: str
    details: str = ""


class AdbDiscovery:
    """Read connected ADB devices without creating or controlling a game session."""

    def __init__(self, adb_path: str | Path | None = None, timeout_seconds: float = 10.0) -> None:
        self.adb_path = str(adb_path) if adb_path else (shutil.which("adb") or "adb")
        self.timeout_seconds = timeout_seconds

    def discover(self) -> tuple[AdbDeviceInfo, ...]:
        try:
            result = subprocess.run(
                [self.adb_path, "devices", "-l"],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise DeviceError(f"Unable to query ADB devices using {self.adb_path!r}: {exc}") from exc

        devices: list[AdbDeviceInfo] = []
        for line in result.stdout.splitlines()[1:]:
            fields = line.strip().split(maxsplit=1)
            if len(fields) < 2:
                continue
            serial, remainder = fields
            state, _, details = remainder.partition(" ")
            devices.append(AdbDeviceInfo(serial=serial, state=state, details=details))
        return tuple(devices)

    def connect_wireless(self, address: str) -> str:
        if not address.strip() or any(ch.isspace() for ch in address):
            raise ValueError("ADB address must be a non-empty host:port value without whitespace")
        try:
            result = subprocess.run(
                [self.adb_path, "connect", address],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise DeviceError(f"ADB connect failed for {address!r}: {exc}") from exc
        output = (result.stdout + result.stderr).strip()
        if "unable to connect" in output.lower() or "failed" in output.lower():
            raise DeviceError(f"ADB did not connect to {address!r}: {output}")
        return output


@dataclass(frozen=True, slots=True)
class CoordinateMapper:
    """Map coordinates drawn against a logical canvas to the current screenshot size."""

    logical_width: int
    logical_height: int

    def __post_init__(self) -> None:
        if self.logical_width <= 0 or self.logical_height <= 0:
            raise ValueError("Logical coordinate dimensions must be positive")

    def map_point(self, x: float, y: float, actual_size: tuple[int, int]) -> tuple[int, int]:
        actual_width, actual_height = actual_size
        if actual_width <= 0 or actual_height <= 0:
            raise ValueError("Actual screenshot dimensions must be positive")
        mapped_x = round(x * actual_width / self.logical_width)
        mapped_y = round(y * actual_height / self.logical_height)
        return (
            min(max(mapped_x, 0), actual_width - 1),
            min(max(mapped_y, 0), actual_height - 1),
        )


@dataclass(frozen=True, slots=True)
class ScreenFrame:
    image: np.ndarray
    captured_at: float
    width: int
    height: int


class ScreenshotCache:
    def __init__(self, ttl_seconds: float = 0.25) -> None:
        if ttl_seconds < 0:
            raise ValueError("Screenshot cache TTL cannot be negative")
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._frame: ScreenFrame | None = None

    def get(self) -> ScreenFrame | None:
        with self._lock:
            frame = self._frame
            if frame is None or time.monotonic() - frame.captured_at > self.ttl_seconds:
                return None
            return frame

    def put(self, image: np.ndarray) -> ScreenFrame:
        if image.ndim < 2:
            raise ValueError("Screenshot must have at least two dimensions")
        height, width = image.shape[:2]
        frame = ScreenFrame(np.array(image, copy=True), time.monotonic(), width, height)
        with self._lock:
            self._frame = frame
        return frame

    def invalidate(self) -> None:
        with self._lock:
            self._frame = None


class MaaDevice:
    """Thin synchronous adapter over MaaFramework's asynchronous Controller API."""

    def __init__(self, controller: Any) -> None:
        self._controller = controller
        self._lock = threading.RLock()
        self._cache = ScreenshotCache()

    @staticmethod
    def _wait(job: Any, operation: str) -> Any:
        job.wait()
        if not job.succeeded:
            raise ControllerOperationError(f"MaaFramework controller operation failed: {operation}")
        return job

    @property
    def connected(self) -> bool:
        return bool(self._controller.connected)

    @property
    def resolution(self) -> tuple[int, int]:
        value = self._controller.resolution
        if hasattr(value, "width") and hasattr(value, "height"):
            return int(value.width), int(value.height)
        if hasattr(value, "x") and hasattr(value, "y"):
            return int(value.x), int(value.y)
        if isinstance(value, (tuple, list)) and len(value) == 2:
            return int(value[0]), int(value[1])
        raise DeviceError(f"Unsupported MaaFramework resolution value: {value!r}")

    def screencap(self, *, fresh: bool = True) -> np.ndarray:
        with self._lock:
            if not self.connected:
                raise DeviceDisconnectedError("Cannot take a screenshot: ADB controller is disconnected")
            cached = None if fresh else self._cache.get()
            if cached is not None:
                return np.array(cached.image, copy=True)
            job = self._wait(self._controller.post_screencap(), "screencap")
            image = job.get()
            if image is None or not isinstance(image, np.ndarray) or image.size == 0:
                raise DeviceError("MaaFramework returned an empty or invalid screenshot")
            self._cache.put(image)
            return np.array(image, copy=True)

    def click(self, x: int, y: int) -> None:
        with self._lock:
            self._require_connected()
            self._wait(self._controller.post_click(int(x), int(y)), "click")
            self._cache.invalidate()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        if duration_ms <= 0:
            raise ValueError("Swipe duration must be positive")
        with self._lock:
            self._require_connected()
            self._wait(
                self._controller.post_swipe(
                    int(x1), int(y1), int(x2), int(y2), int(duration_ms)
                ),
                "swipe",
            )
            self._cache.invalidate()

    def press_key(self, keycode: int) -> None:
        with self._lock:
            self._require_connected()
            self._wait(self._controller.post_click_key(int(keycode)), "press_key")
            self._cache.invalidate()

    def _require_connected(self) -> None:
        if not self.connected:
            raise DeviceDisconnectedError("ADB controller is disconnected")


class SerializedDevice:
    """Serialize all device access so screenshots cannot race with input operations."""

    def __init__(self, device: DeviceInterface) -> None:
        self._device = device
        self._lock = threading.RLock()

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._device.connected

    @property
    def resolution(self) -> tuple[int, int]:
        with self._lock:
            return self._device.resolution

    def screencap(self) -> np.ndarray:
        with self._lock:
            return self._device.screencap()

    def click(self, x: int, y: int) -> None:
        with self._lock:
            self._device.click(x, y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        with self._lock:
            self._device.swipe(x1, y1, x2, y2, duration_ms)

    def press_key(self, keycode: int) -> None:
        with self._lock:
            self._device.press_key(keycode)


class FakeDevice:
    """Deterministic test device; no ADB or MaaFramework process is started."""

    def __init__(self, image: np.ndarray | None = None) -> None:
        self.image = image if image is not None else np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.connected = True
        self.actions: list[tuple[Any, ...]] = []

    @property
    def resolution(self) -> tuple[int, int]:
        height, width = self.image.shape[:2]
        return width, height

    def screencap(self) -> np.ndarray:
        self.actions.append(("screencap",))
        return np.array(self.image, copy=True)

    def click(self, x: int, y: int) -> None:
        if not self.connected:
            raise DeviceDisconnectedError("Fake device is disconnected")
        self.actions.append(("click", x, y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        if not self.connected:
            raise DeviceDisconnectedError("Fake device is disconnected")
        self.actions.append(("swipe", x1, y1, x2, y2, duration_ms))

    def press_key(self, keycode: int) -> None:
        if not self.connected:
            raise DeviceDisconnectedError("Fake device is disconnected")
        self.actions.append(("press_key", keycode))


class SerialCallQueue:
    """A single-worker queue for callers that need ordered, synchronous operations."""

    def __init__(self, name: str = "hbr-device-io") -> None:
        import concurrent.futures

        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix=name)
        self._closed = False
        self._lock = threading.Lock()

    def submit(self, operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            if self._closed:
                raise DeviceError("Device call queue is closed")
            future = self._executor.submit(operation, *args, **kwargs)
        return future.result()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)
