from urllib.parse import urlsplit, urlunsplit
import threading
import time

import cv2

from .base import InputSource


def redact_rtsp_url(url):
    parts = urlsplit(str(url))
    if not parts.username and not parts.password:
        return str(url)
    host = parts.hostname or "host"
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, f"***:***@{host}", parts.path, parts.query, parts.fragment))


class RtspSource(InputSource):
    is_live = True
    input_type = "rtsp"
    connection = "network"

    def __init__(self, url, width=None, height=None, reconnect_attempts=2, low_latency=False):
        self.url = str(url)
        self.source = self.url
        self.width = width
        self.height = height
        self.reconnect_attempts = reconnect_attempts
        self.low_latency = low_latency
        self.capture = None
        self._capture_lock = threading.RLock()
        self._frame_condition = threading.Condition()
        self._reader_thread = None
        self._reader_stop = threading.Event()
        self._latest_frame = None
        self._frame_sequence = 0
        self._last_read_sequence = 0

    @property
    def redacted_url(self):
        return redact_rtsp_url(self.url)

    def __enter__(self):
        self._open()
        return self

    def _open(self):
        self.release()
        try:
            self.capture = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        except Exception as exc:
            raise RuntimeError(f"Unable to initialize RTSP source {redact_rtsp_url(self.url)!r}: {exc}") from exc
        if not self.capture.isOpened():
            self.release()
            raise RuntimeError(f"Unable to open RTSP source {redact_rtsp_url(self.url)!r}.")
        if self.width is not None:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height is not None:
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if self.low_latency:
            self._start_latest_frame_reader()

    def _start_latest_frame_reader(self):
        self._reader_stop.clear()
        self._reader_thread = threading.Thread(target=self._read_latest_frames, name="wifi-camera-reader", daemon=True)
        self._reader_thread.start()

    def _read_latest_frames(self):
        while not self._reader_stop.is_set():
            with self._capture_lock:
                capture = self.capture
                try:
                    ok, frame = capture.read() if capture is not None else (False, None)
                except Exception:
                    ok, frame = False, None
            if ok and frame is not None:
                with self._frame_condition:
                    self._latest_frame = frame
                    self._frame_sequence += 1
                    self._frame_condition.notify_all()
            else:
                time.sleep(0.01)

    def read(self):
        if self.capture is None:
            raise RuntimeError("RTSP source is not open")
        if self.low_latency:
            with self._frame_condition:
                ready = self._frame_condition.wait_for(
                    lambda: self._frame_sequence > self._last_read_sequence or self._reader_stop.is_set(),
                    timeout=1.0,
                )
                if ready and self._frame_sequence > self._last_read_sequence and self._latest_frame is not None:
                    self._last_read_sequence = self._frame_sequence
                    return True, self._latest_frame
            return False, None
        ok, frame = self.capture.read()
        if ok and frame is not None:
            return True, frame
        for _ in range(self.reconnect_attempts):
            try:
                self._open()
            except RuntimeError:
                continue
            ok, frame = self.capture.read()
            if ok and frame is not None:
                return True, frame
        return False, None

    def release(self):
        self._reader_stop.set()
        with self._capture_lock:
            capture = self.capture
            self.capture = None
            if capture is not None:
                capture.release()
        with self._frame_condition:
            self._frame_condition.notify_all()
        if self._reader_thread is not None and self._reader_thread is not threading.current_thread():
            self._reader_thread.join(timeout=1.0)
        self._reader_thread = None
        self._latest_frame = None
        self._frame_sequence = 0
        self._last_read_sequence = 0

    @property
    def status(self):
        return {"type": self.input_type, "description": self.description, "source": self.redacted_url,
                "connection": self.connection, "connected": self.capture is not None,
                "video_available": self.capture is not None}

    @property
    def description(self):
        return f"RTSP source {self.redacted_url}"
