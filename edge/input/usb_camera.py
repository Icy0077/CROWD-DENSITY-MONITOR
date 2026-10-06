from .webcam import WebcamSource


class UsbCameraSource(WebcamSource):
    """USB cameras use the same OpenCV capture contract as a webcam."""
    input_type = "usb"
    connection = "usb"

    @property
    def description(self):
        return f"USB camera {self.device_index}"
