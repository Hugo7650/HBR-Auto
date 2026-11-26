from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    algorithm: str
    found: bool
    box: tuple[int, int, int, int] | None = None
    score: float | None = None
    text: str | None = None
    raw: Any = None

    @property
    def center(self) -> tuple[int, int] | None:
        if self.box is None:
            return None
        x, y, width, height = self.box
        return x + width // 2, y + height // 2


@runtime_checkable
class VisionInterface(Protocol):
    def match_template(
        self,
        image: np.ndarray,
        template: str,
        *,
        threshold: float = 0.8,
        roi: tuple[int, int, int, int] | None = None,
    ) -> RecognitionResult: ...

    def ocr(
        self,
        image: np.ndarray,
        *,
        expected: tuple[str, ...] = (),
        model: str = "",
        threshold: float = 0.3,
        roi: tuple[int, int, int, int] | None = None,
    ) -> tuple[RecognitionResult, ...]: ...


class MaaVision:
    """Maa Native Vision adapter using independent Tasker.post_recognition calls."""

    def __init__(self, tasker: Any) -> None:
        self._tasker = tasker

    @staticmethod
    def _box(value: Any) -> tuple[int, int, int, int] | None:
        if value is None:
            return None
        if all(hasattr(value, attr) for attr in ("x", "y", "w", "h")):
            return int(value.x), int(value.y), int(value.w), int(value.h)
        if isinstance(value, (tuple, list)) and len(value) == 4:
            return tuple(int(v) for v in value)  # type: ignore[return-value]
        return None

    def _recognize(self, kind: Any, params: Any, image: np.ndarray) -> Any:
        if not isinstance(image, np.ndarray) or image.size == 0:
            raise ValueError("Vision input must be a non-empty numpy image")
        job = self._tasker.post_recognition(kind, params, image)
        job.wait()
        if not job.succeeded:
            raise RuntimeError(f"Maa Native Vision recognition failed: {kind}")
        detail = job.get()
        if detail is None:
            raise RuntimeError("Maa Native Vision returned no task detail")
        recognition_nodes = [node.recognition for node in detail.nodes if node.recognition is not None]
        if not recognition_nodes:
            raise RuntimeError("Maa Native Vision returned no recognition detail")
        return recognition_nodes[-1]

    def match_template(
        self,
        image: np.ndarray,
        template: str,
        *,
        threshold: float = 0.8,
        roi: tuple[int, int, int, int] | None = None,
    ) -> RecognitionResult:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Template threshold must be between 0 and 1")
        from maa.pipeline import JRecognitionType, JTemplateMatch

        params = JTemplateMatch(
            template=[template],
            threshold=[threshold],
            roi=roi if roi is not None else (0, 0, 0, 0),
        )
        detail = self._recognize(JRecognitionType.TemplateMatch, params, image)
        result = detail.best_result
        box = self._box(getattr(result, "box", None)) if result is not None else self._box(detail.box)
        score = getattr(result, "score", None) if result is not None else None
        return RecognitionResult("TemplateMatch", bool(detail.hit), box, score, raw=detail.raw_detail)

    def ocr(
        self,
        image: np.ndarray,
        *,
        expected: tuple[str, ...] = (),
        model: str = "",
        threshold: float = 0.3,
        roi: tuple[int, int, int, int] | None = None,
    ) -> tuple[RecognitionResult, ...]:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("OCR threshold must be between 0 and 1")
        from maa.pipeline import JRecognitionType, JOCR

        params = JOCR(
            expected=list(expected),
            model=model,
            threshold=threshold,
            roi=roi if roi is not None else (0, 0, 0, 0),
        )
        detail = self._recognize(JRecognitionType.OCR, params, image)
        results: list[RecognitionResult] = []
        for item in detail.filtered_results:
            results.append(
                RecognitionResult(
                    algorithm="OCR",
                    found=True,
                    box=self._box(getattr(item, "box", None)),
                    score=getattr(item, "score", None),
                    text=getattr(item, "text", None),
                    raw=item,
                )
            )
        return tuple(results)


class FakeVision:
    def __init__(self) -> None:
        self.template_results: dict[str, RecognitionResult] = {}
        self.ocr_results: tuple[RecognitionResult, ...] = ()

    def match_template(
        self,
        image: np.ndarray,
        template: str,
        *,
        threshold: float = 0.8,
        roi: tuple[int, int, int, int] | None = None,
    ) -> RecognitionResult:
        return self.template_results.get(
            template,
            RecognitionResult("TemplateMatch", False),
        )

    def ocr(
        self,
        image: np.ndarray,
        *,
        expected: tuple[str, ...] = (),
        model: str = "",
        threshold: float = 0.3,
        roi: tuple[int, int, int, int] | None = None,
    ) -> tuple[RecognitionResult, ...]:
        if expected:
            return tuple(item for item in self.ocr_results if item.text in expected)
        return self.ocr_results
