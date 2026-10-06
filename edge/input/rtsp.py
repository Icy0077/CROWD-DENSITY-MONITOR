from urllib.parse import urlsplit, urlunsplit

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

    def __init__(self, url, width=None, height=None, reconnect_attempts=2):
        self.url = str(url)
        self.source = self.url
        self.width = width
        self.height = height
        self.reconnect_attempts = reconnect_attempts
        self.capture = None

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

    def read(self):
        if self.capture is None:
            raise RuntimeError("RTSP source is not open")
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
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    @property
    def description(self):
        return f"RTSP source {self.redacted_url}"
