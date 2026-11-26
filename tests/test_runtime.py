from __future__ import annotations

from pathlib import Path

import numpy as np

from hbr_auto.core.runtime import MaaRuntime, MaaRuntimeConfig, RuntimeState


class FakeJob:
    def __init__(self, result=None, succeeded=True):
        self._result = result
        self.done = True
        self.succeeded = succeeded

    def wait(self):
        return self

    def get(self):
        return self._result


class FakeResource:
    def post_image(self, path):
        return FakeJob()

    def post_ocr_model(self, path):
        return FakeJob()


class FakeController:
    connected = True
    resolution = (1920, 1080)

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def post_connection(self):
        return FakeJob()

    def post_screencap(self):
        return FakeJob(np.zeros((1080, 1920, 3), dtype=np.uint8))

    def post_click(self, x, y):
        return FakeJob()

    def post_swipe(self, *args):
        return FakeJob()

    def post_click_key(self, keycode):
        return FakeJob()


class FakeTasker:
    inited = True

    def bind(self, resource, controller):
        self.bound = (resource, controller)
        return True

    def post_stop(self):
        return FakeJob()


def test_runtime_lifecycle_with_injected_fake_maafw_factories(tmp_path: Path) -> None:
    runtime = MaaRuntime(
        MaaRuntimeConfig(
            adb_path=Path("adb"),
            address="emulator-5554",
            log_dir=tmp_path / "logs",
        ),
        factories={
            "Resource": FakeResource,
            "AdbController": FakeController,
            "Tasker": FakeTasker,
        },
    )
    device = runtime.start()
    assert runtime.state is RuntimeState.READY
    assert device.connected
    assert device.screencap().shape == (1080, 1920, 3)
    runtime.close()
    assert runtime.state is RuntimeState.STOPPED


def test_maa_device_accepts_native_point_resolution_shape() -> None:
    from hbr_auto.core.device import MaaDevice

    class Point:
        x = 2560
        y = 1440

    class Controller(FakeController):
        resolution = Point()

    device = MaaDevice(Controller())
    assert device.resolution == (2560, 1440)
