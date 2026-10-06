from .base import InputSource
from ..vision.webcam import WebcamCapture


class WebcamSource(InputSource):
    is_live = True
    input_type = "webcam"
    connection = "local"

    def __init__(self, device_index=0, width=None, height=None, capture_class=WebcamCapture):
        self.capture = capture_class(source=device_index, width=width, height=height)
        self.device_index = device_index
        self.source = str(device_index)

    def __enter__(self):
        if hasattr(self.capture, "open"):
            self.capture.open()
        elif hasattr(self.capture, "__enter__"):
            self.capture.__enter__()
        return self

    def read(self):
        return self.capture.read()

    def release(self):
        if hasattr(self.capture, "release"):
            self.capture.release()
        elif hasattr(self.capture, "__exit__"):
            self.capture.__exit__(None, None, None)

    @property
    def description(self):
        return f"webcam {self.device_index}"
