import cv2


CAMERA_FALLBACK_RESOLUTIONS = (
    (3840, 2160),
    (2560, 1440),
    (1920, 1080),
    (1600, 1200),
    (1600, 900),
    (1440, 1080),
    (1280, 960),
    (1024, 768),
    (960, 720),
    (960, 540),
    (800, 600),
    (800, 450),
    (640, 480),
    (640, 360),
    (320, 240),
)


class WebcamCapture:
    DEFAULT_FPS = 30

    def __init__(self, device_index=0, width=None, height=None, source=None):
        self.device_index = device_index
        self.source = device_index if source is None else source
        self.width = width
        self.height = height
        self._capture = None
        self._first_frame = None
        self.actual_resolution = None

    def open(self):
        if self._capture is not None:
            return

        try:
            capture = cv2.VideoCapture(self.source)
        except Exception as exc:
            raise RuntimeError(f"Unable to initialize video source {self.source!r}: {exc}") from exc
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Unable to open video source {self.source!r}.")

        if isinstance(self.source, int) and self.width is not None and self.height is not None:
            capture = self._select_camera_resolution(capture)
        else:
            if self.width is not None:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            if self.height is not None:
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        if isinstance(self.source, int):
            capture.set(cv2.CAP_PROP_FPS, self.DEFAULT_FPS)

        self._capture = capture

    def _select_camera_resolution(self, capture):
        initial_resolution = (
            int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        requested = (int(self.width), int(self.height))
        fallback_resolutions = set(CAMERA_FALLBACK_RESOLUTIONS)
        if all(initial_resolution):
            fallback_resolutions.add(initial_resolution)
        fallback_resolutions.discard(requested)
        candidates = [requested] + sorted(
            fallback_resolutions,
            key=lambda resolution: resolution[0] * resolution[1],
            reverse=True,
        )

        for width, height in candidates:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            reported_resolution = (
                int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            )
            if all(reported_resolution) and reported_resolution != (width, height):
                continue

            frame = self._read_stable_frame(capture, (width, height), attempts=30)
            if frame is not None:
                self.width, self.height = width, height
                self.actual_resolution = (width, height)
                self._first_frame = frame
                return capture

        capture.release()
        try:
            capture = cv2.VideoCapture(self.source)
        except Exception as exc:
            raise RuntimeError(f"Unable to reopen video source {self.source!r}: {exc}") from exc
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Unable to reopen video source {self.source!r} at its default resolution.")

        frame = self._read_stable_frame(capture)
        if frame is None:
            capture.release()
            raise RuntimeError(f"Video source {self.source!r} did not provide stable frames.")
        self.actual_resolution = (frame.shape[1], frame.shape[0])
        self.width, self.height = self.actual_resolution
        self._first_frame = frame
        return capture

    @staticmethod
    def _read_stable_frame(capture, expected_resolution=None, attempts=30):
        previous_resolution = None
        consecutive_frames = 0
        for _ in range(attempts):
            ok, frame = capture.read()
            if not ok or frame is None:
                previous_resolution = None
                consecutive_frames = 0
                continue

            resolution = (frame.shape[1], frame.shape[0])
            if expected_resolution is not None and resolution != expected_resolution:
                previous_resolution = None
                consecutive_frames = 0
                continue

            if resolution == previous_resolution:
                consecutive_frames += 1
            else:
                previous_resolution = resolution
                consecutive_frames = 1
            if consecutive_frames >= 2:
                return frame
        return None

    def read(self):
        if self._capture is None:
            raise RuntimeError("Webcam is not open")

        if self._first_frame is not None:
            frame = self._first_frame
            self._first_frame = None
            return True, frame

        ok, frame = self._capture.read()
        if ok and frame is not None:
            self.actual_resolution = (frame.shape[1], frame.shape[0])
        return ok, frame

    def release(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._first_frame = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()