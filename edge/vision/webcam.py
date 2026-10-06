import cv2


class WebcamCapture:
    def __init__(self, device_index=0, width=None, height=None):
        self.device_index = device_index
        self.width = width
        self.height = height
        self._capture = None

    def open(self):
        if self._capture is not None:
            return

        try:
            capture = cv2.VideoCapture(self.device_index)
        except Exception as exc:
            raise RuntimeError(f"Unable to initialize webcam device {self.device_index}: {exc}") from exc
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Unable to open webcam {self.device_index}. Ensure the camera is connected and available.")

        if self.width is not None:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height is not None:
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        self._capture = capture

    def read(self):
        if self._capture is None:
            raise RuntimeError("Webcam is not open")

        return self._capture.read()

    def release(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
