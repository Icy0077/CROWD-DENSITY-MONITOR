from abc import ABC, abstractmethod


class InputSource(ABC):
    """Frame source contract shared by webcam, file, and RTSP inputs."""

    is_live = False
    input_type = "unknown"
    connection = "local"
    source = None

    @abstractmethod
    def read(self):
        """Return ``(ok, frame)`` using the OpenCV capture convention."""

    @abstractmethod
    def release(self):
        """Release the underlying source."""

    def __enter__(self):
        return self

    def open(self):
        return self.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

    def close(self):
        self.release()

    def read_frame(self):
        return self.read()

    def is_open(self):
        return bool(self.status.get("connected"))

    def get_status(self):
        return self.status

    @property
    def description(self):
        return self.__class__.__name__

    @property
    def status(self):
        return {"type": self.input_type, "description": self.description, "source": self.source,
                "connection": self.connection, "connected": False,
                "video_available": True}
