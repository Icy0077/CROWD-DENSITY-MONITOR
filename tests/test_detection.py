import numpy as np

from edge.vision import detector as detector_module


class FakeCoordinates(list):
	def tolist(self):
		return list(self)


class FakeBox:
	def __init__(self, center_x, track_id, center_y=20, confidence=0.9):
		self.cls = [0]
		self.conf = [confidence]
		self.id = None if track_id is None else [track_id]
		self.xyxy = [
			FakeCoordinates([center_x - 5, center_y - 10, center_x + 5, center_y + 10])
		]


class FakeResult:
	def __init__(self, boxes):
		self.boxes = boxes


class FakeModel:
	def __init__(self, outputs):
		self.outputs = iter(outputs)
		self.calls = []

	def track(self, **kwargs):
		self.calls.append(kwargs)
		return next(self.outputs)


def make_detector(monkeypatch, frame_boxes, **kwargs):
	model = FakeModel([ [FakeResult(boxes)] for boxes in frame_boxes ])
	monkeypatch.setattr(detector_module, "YOLO", lambda model_path: model)
	detector = detector_module.PersonDetector(line=((50, 0), (50, 100)), **kwargs)
	return detector, model


def test_line_crossings_update_in_out_counts_and_occupancy(monkeypatch):
	detector, model = make_detector(
		monkeypatch,
		[
			[FakeBox(70, 17)],
			[FakeBox(50, 17)],
			[FakeBox(30, 17)],
			[FakeBox(30, 17)],
			[FakeBox(70, 17)],
		],
	)

	crossings = [
		detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))[0]["crossing"]
		for _ in range(5)
	]

	assert crossings == [None, None, "IN", None, "OUT"]
	assert detector.occupancy == 0
	assert all(call["persist"] is True for call in model.calls)
	assert all(call["tracker"].endswith("crowd_bytetrack.yaml") for call in model.calls)
	assert all(call["classes"] == [0] for call in model.calls)
	assert all(call["imgsz"] == 640 for call in model.calls)
	assert all(call["conf"] == 0.1 for call in model.calls)


def test_detector_uses_supported_quantize_setting_for_cpu(monkeypatch):
	detector, model = make_detector(monkeypatch, [[FakeBox(70, 17)]])
	detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

	assert detector.quantize is None
	assert model.calls[0]["quantize"] is None
	assert "half" not in model.calls[0]


def test_detector_uses_fp16_quantize_setting_on_cuda(monkeypatch):
	monkeypatch.setattr(detector_module.torch.cuda, "is_available", lambda: True)
	detector, model = make_detector(monkeypatch, [[FakeBox(70, 17)]])
	detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

	assert detector.device == 0
	assert detector.quantize == 16
	assert model.calls[0]["quantize"] == 16
	assert "half" not in model.calls[0]


def test_duplicate_track_detections_count_once_per_frame(monkeypatch):
	detector, _ = make_detector(
		monkeypatch,
		[
			[FakeBox(70, 4)],
			[FakeBox(30, 4), FakeBox(30, 4)],
			[FakeBox(30, 4)],
		],
	)

	first = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))
	second = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))
	third = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

	assert [item["crossing"] for item in first] == [None]
	assert [item["crossing"] for item in second] == ["IN", None]
	assert [item["crossing"] for item in third] == [None]
	assert detector.occupancy == 1


def test_low_confidence_person_does_not_trigger_crossing(monkeypatch):
	detector, _ = make_detector(
		monkeypatch,
		[
			[FakeBox(70, 18)],
			[FakeBox(30, 18, confidence=0.2)],
			[FakeBox(30, 18)],
		],
	)

	first = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))
	low_confidence = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))
	confirmed = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

	assert first[0]["crossing"] is None
	assert low_confidence == []
	assert confirmed[0]["crossing"] == "IN"
	assert detector.occupancy == 1


def test_line_deadband_prevents_flicker_double_count(monkeypatch):
	detector, _ = make_detector(
		monkeypatch,
		[
			[FakeBox(70, 33)],
			[FakeBox(56, 33)],
			[FakeBox(44, 33)],
			[FakeBox(30, 33)],
			[FakeBox(70, 33)],
		],
	)

	frames = [detector.detect(np.zeros((100, 100, 3), dtype=np.uint8)) for _ in range(5)]

	assert [frame[0]["crossing"] for frame in frames] == [None, None, None, "IN", "OUT"]
	assert detector.occupancy == 0


def test_out_crossing_never_reduces_occupancy_below_zero(monkeypatch):
	detector, _ = make_detector(
		monkeypatch,
		[
			[FakeBox(30, 29)],
			[FakeBox(70, 29)],
		],
	)

	detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))
	out_detection = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))[0]

	assert out_detection["crossing"] == "OUT"
	assert detector.occupancy == 0


def test_lost_track_state_expires_before_track_id_reuse(monkeypatch):
	detector, _ = make_detector(
		monkeypatch,
		[
			[FakeBox(30, 8)],
			[],
			[],
			[],
			[FakeBox(70, 8)],
		],
		max_track_age=2,
	)

	for _ in range(4):
		detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))
	assert 8 not in detector._track_sides

	last_frame = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

	assert last_frame[0]["crossing"] is None
	assert detector.occupancy == 0


def test_crossing_beyond_line_endpoints_is_not_counted(monkeypatch):
	detector, _ = make_detector(
		monkeypatch,
		[
			[FakeBox(70, 21, center_y=120)],
			[FakeBox(30, 21, center_y=120)],
			[FakeBox(30, 21, center_y=50)],
			[FakeBox(70, 21, center_y=50)],
		],
	)

	frames = [detector.detect(np.zeros((150, 100, 3), dtype=np.uint8)) for _ in range(4)]

	assert [frame[0]["crossing"] for frame in frames] == [None, None, None, "OUT"]


def test_detector_requires_valid_configured_line(monkeypatch):
	model = FakeModel([])
	monkeypatch.setattr(detector_module, "YOLO", lambda model_path: model)

	try:
		detector_module.PersonDetector(line=((10, 10), (10, 10)))
	except ValueError as error:
		assert "different" in str(error)
	else:
		assert False, "a zero-length counting line must be rejected"
