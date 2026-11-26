from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .device import DeviceInterface
from .vision import VisionInterface


class TaskError(RuntimeError):
    pass


class TaskCancelled(TaskError):
    pass


class TaskTimedOut(TaskError):
    pass


class TaskStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    BLOCKED = "BLOCKED"


@dataclass(slots=True)
class TaskContext:
    device: DeviceInterface
    vision: VisionInterface
    logger: Any
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    cancellation: threading.Event = field(default_factory=threading.Event)
    deadline: float | None = None
    state: dict[str, Any] = field(default_factory=dict)

    def checkpoint(self) -> None:
        if self.cancellation.is_set():
            raise TaskCancelled("Task cancellation was requested")
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise TaskTimedOut("Task exceeded its cooperative execution timeout")

    def cancelled(self) -> bool:
        return self.cancellation.is_set()


class BaseTask(ABC):
    name: str
    dependencies: tuple[str, ...] = ()
    timeout_seconds: float | None = None

    @abstractmethod
    def run(self, context: TaskContext) -> Any:
        raise NotImplementedError


class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, BaseTask] = {}

    def register(self, task: BaseTask) -> None:
        name = getattr(task, "name", "")
        if not name or not isinstance(name, str):
            raise ValueError("Task must define a non-empty string name")
        if name in self._tasks:
            raise ValueError(f"Task already registered: {name}")
        if task.timeout_seconds is not None and task.timeout_seconds <= 0:
            raise ValueError(f"Task timeout must be positive: {name}")
        self._tasks[name] = task

    def get(self, name: str) -> BaseTask:
        try:
            return self._tasks[name]
        except KeyError as exc:
            raise KeyError(f"Unknown task: {name}") from exc

    def topological_order(self, target: str) -> tuple[BaseTask, ...]:
        order: list[BaseTask] = []
        visiting: list[str] = []
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                cycle = " -> ".join((*visiting, name))
                raise ValueError(f"Task dependency cycle detected: {cycle}")
            if name in visited:
                return
            task = self.get(name)
            visiting.append(name)
            for dependency in task.dependencies:
                visit(dependency)
            visiting.pop()
            visited.add(name)
            order.append(task)

        visit(target)
        return tuple(order)


@dataclass(frozen=True, slots=True)
class TaskExecutionRecord:
    task_name: str
    status: TaskStatus
    started_at: float
    finished_at: float
    result: Any = None
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        return self.finished_at - self.started_at


@dataclass(frozen=True, slots=True)
class TaskRunReport:
    run_id: str
    records: tuple[TaskExecutionRecord, ...]

    @property
    def succeeded(self) -> bool:
        return bool(self.records) and all(r.status is TaskStatus.SUCCEEDED for r in self.records)


class TaskScheduler:
    """Run task dependency graphs in deterministic serial order.

    Timeout is cooperative: tasks must call TaskContext.checkpoint() at safe points.
    Python cannot safely terminate a running task thread or interrupt an arbitrary Maa job.
    """

    def __init__(self, registry: TaskRegistry) -> None:
        self.registry = registry

    def run(self, target: str, context: TaskContext) -> TaskRunReport:
        records: list[TaskExecutionRecord] = []
        for task in self.registry.topological_order(target):
            if context.cancelled():
                now = time.monotonic()
                records.append(
                    TaskExecutionRecord(task.name, TaskStatus.BLOCKED, now, now, error="run cancelled")
                )
                break

            started = time.monotonic()
            context.deadline = (
                started + task.timeout_seconds if task.timeout_seconds is not None else None
            )
            try:
                context.checkpoint()
                result = task.run(context)
                context.checkpoint()
            except TaskCancelled as exc:
                finished = time.monotonic()
                records.append(
                    TaskExecutionRecord(task.name, TaskStatus.CANCELLED, started, finished, error=str(exc))
                )
                break
            except TaskTimedOut as exc:
                finished = time.monotonic()
                records.append(
                    TaskExecutionRecord(task.name, TaskStatus.TIMED_OUT, started, finished, error=str(exc))
                )
                break
            except Exception as exc:
                finished = time.monotonic()
                records.append(
                    TaskExecutionRecord(
                        task.name,
                        TaskStatus.FAILED,
                        started,
                        finished,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
                if context.logger is not None:
                    context.logger.exception("Task %s failed", task.name, extra={"task_name": task.name})
                break
            else:
                finished = time.monotonic()
                records.append(
                    TaskExecutionRecord(task.name, TaskStatus.SUCCEEDED, started, finished, result=result)
                )
        context.deadline = None
        return TaskRunReport(context.run_id, tuple(records))


class FunctionTask(BaseTask):
    def __init__(
        self,
        name: str,
        function: Callable[[TaskContext], Any],
        *,
        dependencies: tuple[str, ...] = (),
        timeout_seconds: float | None = None,
    ) -> None:
        self.name = name
        self.function = function
        self.dependencies = dependencies
        self.timeout_seconds = timeout_seconds

    def run(self, context: TaskContext) -> Any:
        return self.function(context)
