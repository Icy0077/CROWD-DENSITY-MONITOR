import threading

from .factory import create_input_source


class InputDeviceManager:
    """Thread-safe source owner shared by the control API and frame loop."""

    def __init__(self, source=None, input_type=None, **kwargs):
        self._kwargs = kwargs
        self._lock = threading.RLock()
        self.source = create_input_source(source=source, input_type=input_type, **kwargs)
        self._prefetched = None
        self._last_error = None
        self._active = False
        self._frames = 0

    @property
    def status(self):
        with self._lock:
            value = dict(self.source.get_status())
            value.update({"active": self._active, "frames": self._frames})
            if self._last_error:
                value.update({"state": "ERROR", "message": self._last_error})
            elif self._active:
                value.update({"state": "ACTIVE", "message": "Receiving frames"})
            elif value.get("connected"):
                value.update({"state": "CONNECTED", "message": "Source connected"})
            else:
                value.update({"state": "AVAILABLE", "message": "Source configured"})
            return value

    @property
    def input_type(self):
        return self.source.input_type

    @property
    def connection(self):
        return self.source.connection

    @property
    def description(self):
        return self.source.description

    def _open_and_probe(self, candidate):
        candidate.open()
        ok, frame = candidate.read_frame()
        if not ok or frame is None:
            candidate.close()
            raise RuntimeError(f"Unable to receive a frame from {candidate.description}.")
        return frame

    def select(self, source=None, input_type=None, **kwargs):
        with self._lock:
            candidate = create_input_source(source=source, input_type=input_type, **{**self._kwargs, **kwargs})
            try:
                first_frame = self._open_and_probe(candidate)
            except Exception as exc:
                candidate.close()
                self._last_error = str(exc)
                raise RuntimeError(str(exc)) from exc
            old = self.source
            self.source = candidate
            self._prefetched = first_frame
            self._last_error = None
            self._active = False
            self._frames = 0
            old.close()
            return self.status

    def connect(self):
        with self._lock:
            if not self.source.is_open():
                self._prefetched = self._open_and_probe(self.source)
            self._last_error = None
            return self.status

    def read(self):
        with self._lock:
            if self._prefetched is not None:
                frame = self._prefetched
                self._prefetched = None
                ok = True
            else:
                try:
                    ok, frame = self.source.read_frame()
                except Exception as exc:
                    self._last_error = str(exc)
                    self._active = False
                    return False, None
            if ok and frame is not None:
                self._active = True
                self._last_error = None
                self._frames += 1
            else:
                self._active = False
                self._last_error = "Source stopped returning frames."
            return ok, frame

    def disconnect(self):
        with self._lock:
            self.source.close()
            self._prefetched = None
            self._active = False
            return self.status

    open = connect
    close = disconnect

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
