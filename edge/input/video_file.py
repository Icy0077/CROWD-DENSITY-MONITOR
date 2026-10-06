import cv2

from .base import InputSource


class VideoFileSource(InputSource):
    is_live = False
    input_type = "file"
    connection = "local"

    def __init__(self, path):
        self.path = str(path)
        self.source = self.path
        self.capture = None

    def __enter__(self):
        self.capture = cv2.VideoCapture(self.path)
        if not self.capture.isOpened():
            self.release()
            raise RuntimeError(f"Unable to open video file {self.path!r}.")
        return self

    def read(self):
        if self.capture is None:
            raise RuntimeError("Video file is not open")
        return self.capture.read()

    def release(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    @property
    def description(self):
        return f"video file {self.path}"
