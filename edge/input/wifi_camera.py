from .rtsp import RtspSource


class WifiCameraSource(RtspSource):
    """Network camera source; OpenCV supports RTSP and many MJPEG URLs."""
    input_type = "wifi"
    connection = "wi-fi"

    def __init__(self, url, width=None, height=None, reconnect_attempts=2):
        super().__init__(url, width=width, height=height, reconnect_attempts=reconnect_attempts, low_latency=True)

    @property
    def description(self):
        return f"Wi-Fi camera {self.redacted_url}"
