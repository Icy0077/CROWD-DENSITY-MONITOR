import numpy as np

from edge.input.bluetooth import BluetoothDeviceAdapter, BluetoothSource
from edge.input.factory import create_input_source
from edge.input.geometry import display_to_source, letterbox, source_to_display
from edge.input.phone import PhoneCameraSource
from edge.input.usb_camera import UsbCameraSource
from edge.input.wifi_camera import WifiCameraSource


class FakeBluetooth:
    def discover(self):
        return [{"id": "mock-1", "name": "Mock camera"}]

    def connect(self, _device):
        pass

    def disconnect(self):
        pass


def test_factory_supports_usb_wifi_phone_and_bluetooth():
    assert isinstance(create_input_source("1", input_type="usb"), UsbCameraSource)
    assert isinstance(create_input_source("http://camera/mjpeg", input_type="wifi"), WifiCameraSource)
    assert isinstance(create_input_source(None, input_type="phone"), PhoneCameraSource)
    assert isinstance(create_input_source(None, input_type="bluetooth"), BluetoothSource)


def test_bluetooth_mock_discovery_and_unsupported_video_state():
    adapter = BluetoothDeviceAdapter(FakeBluetooth())
    device = adapter.discover()[0]
    status = adapter.connect(device)
    assert status["connected"] is True
    assert status["video_available"] is False
    assert "no compatible video stream" in status["message"]
    adapter.disconnect()


def test_phone_webrtc_is_explicitly_future_ready():
    source = PhoneCameraSource(transport="webrtc")
    assert source.status["video_available"] is False
    assert "signaling" in source.status["message"]


def test_letterbox_preserves_aspect_ratio_and_round_trips_coordinates():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    boxed, transform = letterbox(frame, (200, 200))
    assert boxed.shape == (200, 200, 3)
    point = (80, 25)
    assert np.allclose(display_to_source(source_to_display(point, transform), transform), point)
