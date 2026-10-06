from .rtsp import RtspSource


class WifiCameraSource(RtspSource):
    """Network camera source; OpenCV supports RTSP and many MJPEG URLs."""
    input_type = "wifi"
    connection = "wi-fi"

    @property
    def description(self):
        return f"Wi-Fi camera {self.redacted_url}"
