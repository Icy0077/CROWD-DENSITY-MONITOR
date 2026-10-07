import numpy as np

from edge.main import _display_geometry, _fit_frame_to_screen, _line_for_frame
from edge.vision import webcam as webcam_module


class FakeCapture:
	def __init__(self, source, supported_resolutions, initial_resolution=(640, 480)):
		self.source = source
		self.supported_resolutions = set(supported_resolutions)
		self.resolution = initial_resolution
		self.requested_width = initial_resolution[0]
		self.requested_height = initial_resolution[1]

	def isOpened(self):
		return True

	def set(self, prop_id, value):
		if prop_id == webcam_module.cv2.CAP_PROP_FRAME_WIDTH:
			self.requested_width = int(value)
		else:
			self.requested_height = int(value)
		requested = (self.requested_width, self.requested_height)
		if requested in self.supported_resolutions:
			self.resolution = requested
			return True
		return False

	def get(self, prop_id):
		if prop_id == webcam_module.cv2.CAP_PROP_FRAME_WIDTH:
			return self.resolution[0]
		return self.resolution[1]

	def read(self):
		width, height = self.resolution
		return True, np.zeros((height, width, 3), dtype=np.uint8)

	def release(self):
		return None


class DelayedFakeCapture(FakeCapture):
	def __init__(self, source, supported_resolutions, initial_resolution=(640, 480)):
		super().__init__(source, supported_resolutions, initial_resolution)
		self.pending_resolution = None
		self.frames_until_switch = 0

	def set(self, prop_id, value):
		if prop_id == webcam_module.cv2.CAP_PROP_FRAME_WIDTH:
			self.requested_width = int(value)
		else:
			self.requested_height = int(value)
		requested = (self.requested_width, self.requested_height)
		if requested in self.supported_resolutions:
			self.pending_resolution = requested
			self.frames_until_switch = 7
			return True
		return False

	def get(self, prop_id):
		if prop_id == webcam_module.cv2.CAP_PROP_FRAME_WIDTH:
			return self.requested_width
		return self.requested_height

	def read(self):
		if self.pending_resolution is not None:
			self.frames_until_switch -= 1
			if self.frames_until_switch <= 0:
				self.resolution = self.pending_resolution
				self.pending_resolution = None
		return super().read()


def test_webcam_falls_back_to_highest_stable_supported_resolution(monkeypatch):
	capture = FakeCapture(0, {(1024, 768), (640, 480)})
	monkeypatch.setattr(webcam_module.cv2, "VideoCapture", lambda source: capture)
	camera = webcam_module.WebcamCapture(source=0, width=1280, height=720)

	with camera as opened_camera:
		ok, frame = opened_camera.read()

	assert ok
	assert frame.shape[:2] == (768, 1024)
	assert camera.actual_resolution == (1024, 768)


def test_webcam_waits_for_camera_mode_to_stabilize(monkeypatch):
	capture = DelayedFakeCapture(0, {(1280, 720)})
	monkeypatch.setattr(webcam_module.cv2, "VideoCapture", lambda source: capture)
	camera = webcam_module.WebcamCapture(source=0, width=1280, height=720)

	with camera as opened_camera:
		ok, frame = opened_camera.read()

	assert ok
	assert frame.shape[:2] == (720, 1280)
	assert camera.actual_resolution == (1280, 720)


def test_display_fit_preserves_aspect_ratio_without_upscaling():
	frame = np.zeros((720, 1280, 3), dtype=np.uint8)

	display_frame = _fit_frame_to_screen(frame, (1280, 800))
	geometry = _display_geometry(frame.shape[:2], (1280, 800))

	assert display_frame.shape[1:] == (1200, 3)
	assert display_frame.shape[0] == 660
	assert geometry["display_size"] == (1173, 660)
	assert geometry["offset"] == (13, 0)
	assert abs(geometry["display_size"][0] / geometry["display_size"][1] - 1280 / 720) < 0.002
	assert geometry["display_center_x"] == 599
	assert abs(geometry["display_center_x"] - (geometry["offset"][0] + geometry["display_size"][0] / 2)) <= 1


def test_display_fit_preserves_source_ratio_and_video_center_for_common_resolutions():
	for width, height in ((640, 480), (1280, 720), (1920, 1080), (1080, 1920)):
		frame = np.full((height, width, 3), 127, dtype=np.uint8)
		geometry = _display_geometry((height, width), (1280, 800))
		canvas = _fit_frame_to_screen(frame, (1280, 800))
		display_width, display_height = geometry["display_size"]
		offset_x, offset_y = geometry["offset"]
		displayed_frame = canvas[offset_y:offset_y + display_height, offset_x:offset_x + display_width]
		source_center = width // 2

		assert displayed_frame.shape[:2] == (display_height, display_width)
		assert np.all(displayed_frame == 127)
		assert geometry["source_center_x"] == source_center
		assert geometry["display_center_x"] == geometry["offset"][0] + int(source_center * geometry["scale"])
		assert abs(display_width / display_height - width / height) < 0.002
		assert _line_for_frame(width, height) == ((source_center, 0), (source_center, height - 1))
		assert geometry["display_center_x"] == offset_x + int(source_center * geometry["scale"])


def test_counting_line_spans_actual_frame_height():
	assert _line_for_frame(1280, 720) == ((640, 0), (640, 719))
	assert _line_for_frame(640, 480, ((320, 0), (320, 479))) == ((320, 0), (320, 479))
	assert _line_for_frame(1280, 720, ((320, 0), (320, 479))) == ((320, 0), (320, 479))
