"""Thread-safe synchronous dispatch for dialogs hosted by Tk's UI thread.

Workers may request a UI decision, but must never call Tk widgets directly.
A queued callback is cancelled if the UI does not start it before the timeout.
"""
from __future__ import annotations

import threading
from typing import Any, Callable


class TkThreadDispatcher:
    """Run callbacks on Tk's owning thread and return their result to a worker."""

    def __init__(self, root: Any, *, ui_thread_id: int | None = None, timeout: float = 30.0):
        if timeout <= 0:
            raise ValueError("Dispatch timeout must be positive.")
        self._root = root
        self._ui_thread_id = threading.get_ident() if ui_thread_id is None else ui_thread_id
        self._timeout = float(timeout)

    def call(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if not callable(callback):
            raise TypeError("A callable UI callback is required.")
        if threading.get_ident() == self._ui_thread_id:
            return callback(*args, **kwargs)

        completed = threading.Event()
        gate = threading.Lock()
        state = {"cancelled": False, "started": False}
        result: list[Any] = []
        failure: list[BaseException] = []

        def invoke() -> None:
            with gate:
                if state["cancelled"]:
                    completed.set()
                    return
                state["started"] = True
            try:
                result.append(callback(*args, **kwargs))
            except BaseException as exc:
                failure.append(exc)
            finally:
                completed.set()

        try:
            self._root.after(0, invoke)
        except Exception as exc:
            raise RuntimeError("Could not schedule a callback on the JARVIS UI thread.") from exc

        if not completed.wait(self._timeout):
            with gate:
                if not state["started"]:
                    state["cancelled"] = True
                    raise TimeoutError(
                        "The JARVIS UI did not respond in time; the pending dialog was cancelled."
                    )
            # The UI claimed the callback just before the timeout. Do not return
            # while a live approval dialog is still open or report a false timeout.
            completed.wait()
        if failure:
            raise failure[0]
        return result[0] if result else None
