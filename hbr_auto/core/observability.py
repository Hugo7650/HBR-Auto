from __future__ import annotations

import json
import logging
import struct
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("run_id", "task_name", "scene", "turn", "action_slot", "device"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("hbr_auto")
    logger.setLevel(level)
    logger.propagate = False
    if not any(getattr(handler, "_hbr_auto_handler", False) for handler in logger.handlers):
        handler = logging.FileHandler(log_dir / "hbr-auto.jsonl", encoding="utf-8")
        handler.setFormatter(JsonLineFormatter())
        setattr(handler, "_hbr_auto_handler", True)
        logger.addHandler(handler)
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        setattr(console, "_hbr_auto_handler", True)
        logger.addHandler(console)
    return logger


def save_failure_screenshot(image: np.ndarray, directory: Path, *, prefix: str = "failure") -> Path:
    """Save an RGB/RGBA/grayscale numpy image as PNG without a heavyweight imaging stack."""
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Cannot save an empty screenshot")
    if image.dtype != np.uint8:
        raise ValueError(f"PNG screenshot must use uint8 pixels, got {image.dtype}")
    if image.ndim == 2:
        color_type, rows = 0, image
    elif image.ndim == 3 and image.shape[2] == 3:
        color_type, rows = 2, image
    elif image.ndim == 3 and image.shape[2] == 4:
        color_type, rows = 6, image
    else:
        raise ValueError(f"Unsupported screenshot dimensions: {image.shape}")

    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    path = directory / f"{prefix}_{stamp}.png"
    height, width = rows.shape[:2]
    scanlines = b"".join(b"\x00" + rows[y].tobytes() for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(scanlines, level=6))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path
