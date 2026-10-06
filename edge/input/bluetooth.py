from .base import InputSource


class BluetoothDeviceAdapter:
    """Discovery/control only. Bluetooth is not assumed to carry camera video."""
    def __init__(self, backend=None):
        self.backend = backend
        self.device = None
        self.connected = False

    def discover(self):
        return list(self.backend.discover()) if self.backend else []

    def connect(self, device):
        self.device = device
        if self.backend and hasattr(self.backend, "connect"):
            self.backend.connect(device)
        self.connected = True
        return self.status

    def disconnect(self):
        if self.backend and hasattr(self.backend, "disconnect"):
            self.backend.disconnect()
        self.connected = False
        self.device = None

    @property
    def status(self):
        return {"connected": self.connected, "device": self.device,
                "video_available": bool(self.device and self.device.get("video_url")),
                "message": "Bluetooth connected - no compatible video stream exposed" if self.connected and not (self.device and self.device.get("video_url")) else ""}


class BluetoothSource(InputSource):
    input_type = "bluetooth"
    connection = "bluetooth"

    def __init__(self, adapter=None):
        self.adapter = adapter or BluetoothDeviceAdapter()

    @property
    def description(self):
        return "Bluetooth device"

    @property
    def status(self):
        return {"type": self.input_type, **self.adapter.status}

    def read(self):
        raise RuntimeError("Bluetooth connected - no compatible video stream exposed")

    def release(self):
        self.adapter.disconnect()
