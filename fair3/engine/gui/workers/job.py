"""Utilities for running background jobs on a Qt thread pool."""

from __future__ import annotations

from typing import Any, Callable


class JobRunner:
    """Submit callables to a Qt thread pool and forward the results via signals."""

    def __init__(self, qt_core: Any, *, thread_pool: Any | None = None) -> None:
        self._qt_core = qt_core
        self._pool = thread_pool or qt_core.QThreadPool.globalInstance()

    def submit(
        self,
        fn: Callable[..., Any],
        *,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        """Schedule ``fn`` to run in the background."""

        qt_core = self._qt_core
        kwargs = kwargs or {}

        class _Signals(qt_core.QObject):
            finished = qt_core.Signal(object)
            failed = qt_core.Signal(object)

        class _Runnable(qt_core.QRunnable):
            def __init__(self) -> None:
                super().__init__()
                self.signals = _Signals()

            def run(self) -> None:  # pragma: no cover - executed on worker threads
                try:
                    result = fn(*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001 - propagate exact exception
                    self.signals.failed.emit(exc)
                else:
                    self.signals.finished.emit(result)

        runnable = _Runnable()

        if on_success is not None:
            runnable.signals.finished.connect(on_success)
        if on_error is not None:
            runnable.signals.failed.connect(on_error)

        self._pool.start(runnable)


__all__ = ["JobRunner"]
