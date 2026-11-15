import threading
import unittest

from tk_thread_dispatch import TkThreadDispatcher


class FakeTkRoot:
    def __init__(self):
        self.callbacks = []
        self.fail = False

    def after(self, delay, callback):
        if self.fail:
            raise RuntimeError("Tk is shutting down")
        self.callbacks.append(callback)


class TkThreadDispatcherTests(unittest.TestCase):
    def test_calls_directly_when_already_on_ui_thread(self):
        root = FakeTkRoot()
        dispatcher = TkThreadDispatcher(root)
        self.assertEqual(dispatcher.call(lambda value: value + 1, 4), 5)
        self.assertEqual(root.callbacks, [])

    def test_worker_waits_for_ui_callback_and_receives_result(self):
        root = FakeTkRoot()
        ui_thread = threading.get_ident()
        dispatcher = TkThreadDispatcher(root, ui_thread_id=ui_thread, timeout=1)
        result = []
        worker = threading.Thread(target=lambda: result.append(
            dispatcher.call(lambda left, right: left + right, 10, 7)
        ))
        worker.start()
        for _ in range(100):
            if root.callbacks:
                break
            threading.Event().wait(0.005)
        self.assertEqual(len(root.callbacks), 1)
        root.callbacks.pop(0)()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [17])

    def test_worker_receives_callback_exception(self):
        root = FakeTkRoot()
        dispatcher = TkThreadDispatcher(root, ui_thread_id=threading.get_ident(), timeout=1)
        errors = []

        def worker_call():
            try:
                dispatcher.call(lambda: (_ for _ in ()).throw(ValueError("dialog failed")))
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=worker_call)
        worker.start()
        for _ in range(100):
            if root.callbacks:
                break
            threading.Event().wait(0.005)
        root.callbacks.pop(0)()
        worker.join(1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValueError)
        self.assertEqual(str(errors[0]), "dialog failed")

    def test_timeout_cancels_queued_callback_before_it_can_run(self):
        root = FakeTkRoot()
        dispatcher = TkThreadDispatcher(root, ui_thread_id=threading.get_ident(), timeout=0.02)
        errors = []
        calls = []

        def worker_call():
            try:
                dispatcher.call(lambda: calls.append("dialog"))
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=worker_call)
        worker.start()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(errors[0], TimeoutError)
        root.callbacks.pop(0)()
        self.assertEqual(calls, [])

    def test_tk_shutdown_is_reported_without_waiting(self):
        root = FakeTkRoot()
        root.fail = True
        dispatcher = TkThreadDispatcher(root, ui_thread_id=threading.get_ident(), timeout=1)
        errors = []

        worker = threading.Thread(target=lambda: self._capture_error(
            errors, lambda: dispatcher.call(lambda: "never")
        ))
        worker.start()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(errors[0], RuntimeError)

    @staticmethod
    def _capture_error(errors, callback):
        try:
            callback()
        except Exception as exc:
            errors.append(exc)


if __name__ == "__main__":
    unittest.main()
