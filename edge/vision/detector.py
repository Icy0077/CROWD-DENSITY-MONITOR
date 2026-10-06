from ultralytics import YOLO

from ..privacy.privacy_drop import PrivacyDrop


PERSON_CLASS_ID = 0


class PersonDetector:
	def __init__(
		self,
		model_path="yolov8n.pt",
		confidence=0.25,
		tracker="bytetrack.yaml",
		line=None,
		in_side="positive",
	):
		try:
			self.model = YOLO(model_path)
		except Exception as exc:
			raise RuntimeError(f"Unable to load YOLO model '{model_path}': {exc}") from exc
		self.confidence = confidence
		self.tracker = tracker
		self.line = line
		if in_side not in ("positive", "negative"):
			raise ValueError("in_side must be 'positive' or 'negative'")
		self.in_side = 1 if in_side == "positive" else -1
		self._track_sides = {}
		self.occupancy = 0
		self.privacy_drop = PrivacyDrop()

	def detect(self, frame):
		if frame is None:
			raise ValueError("detect() requires a non-empty frame")
		try:
			results = self.model.track(
				source=frame,
				classes=[PERSON_CLASS_ID],
				conf=self.confidence,
				persist=True,
				tracker=self.tracker,
				verbose=False,
			)
		except Exception as exc:
			raise RuntimeError(f"YOLO tracking failed: {exc}") from exc

		detections = []
		in_count = 0
		out_count = 0
		result = None
		box = None
		for result in results:
			for box in result.boxes:
				class_id = int(box.cls[0])
				if class_id != PERSON_CLASS_ID:
					continue

				track_id = None if box.id is None else int(box.id[0])
				bbox = box.xyxy[0].tolist()
				crossing = self._get_crossing(track_id, bbox)
				if crossing == "IN":
					in_count += 1
				elif crossing == "OUT":
					out_count += 1

				detections.append(
					{
						"bbox": bbox,
						"confidence": float(box.conf[0]),
						"class_id": class_id,
						"track_id": track_id,
						"crossing": crossing,
					}
				)

		self.occupancy = max(0, self.occupancy + in_count - out_count)
		results = None
		result = None
		box = None
		frame = self.privacy_drop.drop(frame)
		return detections

	def _get_crossing(self, track_id, bbox):
		if self.line is None or track_id is None:
			return None

		x1, y1 = self.line[0]
		x2, y2 = self.line[1]
		center_x = (bbox[0] + bbox[2]) / 2
		center_y = (bbox[1] + bbox[3]) / 2
		side_value = (x2 - x1) * (center_y - y1) - (y2 - y1) * (center_x - x1)
		current_side = 1 if side_value > 0 else -1 if side_value < 0 else 0
		previous_side = self._track_sides.get(track_id)
		if current_side == 0:
			return None

		self._track_sides[track_id] = current_side
		if previous_side is None or previous_side == current_side:
			return None

		return "IN" if current_side == self.in_side else "OUT"
