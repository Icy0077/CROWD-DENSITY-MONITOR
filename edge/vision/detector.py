import math
from pathlib import Path

import torch
from ultralytics import YOLO

from ..privacy.privacy_drop import PrivacyDrop


PERSON_CLASS_ID = 0
BYTE_TRACKER_CONFIG = str(Path(__file__).with_name("crowd_bytetrack.yaml"))


class PersonDetector:
	def __init__(
		self,
		model_path="yolov8n.pt",
		confidence=0.4,
		image_size=640,
		tracker=BYTE_TRACKER_CONFIG,
		line=None,
		in_side="positive",
		line_tolerance=8.0,
		max_track_age=45,
	):
		try:
			self.model = YOLO(model_path)
		except Exception as exc:
			raise RuntimeError(f"Unable to load YOLO model '{model_path}': {exc}") from exc
		self.confidence = float(confidence)
		if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
			raise ValueError("confidence must be between 0 and 1")
		self.image_size = int(image_size)
		if self.image_size <= 0:
			raise ValueError("image_size must be greater than 0")
		self.device = 0 if torch.cuda.is_available() else "cpu"
		# Ultralytics maps quantize=16 to FP16 in AutoBackend. Keep CPU on
		# the default precision and retain the previous CUDA FP16 behavior.
		self.quantize = 16 if self.device != "cpu" else None
		self.tracker = tracker
		if line is not None:
			if len(line) != 2 or any(len(point) != 2 for point in line):
				raise ValueError("line must contain two (x, y) points")
			line = tuple(tuple(float(value) for value in point) for point in line)
			if not all(math.isfinite(value) for point in line for value in point):
				raise ValueError("line coordinates must be finite")
			if line[0] == line[1]:
				raise ValueError("line endpoints must be different")
		self.line = line
		if in_side not in ("positive", "negative"):
			raise ValueError("in_side must be 'positive' or 'negative'")
		self.in_side = 1 if in_side == "positive" else -1
		self.line_tolerance = float(line_tolerance)
		if not math.isfinite(self.line_tolerance) or self.line_tolerance < 0:
			raise ValueError("line_tolerance must be a finite non-negative number")
		self.max_track_age = int(max_track_age)
		if self.max_track_age < 1:
			raise ValueError("max_track_age must be at least 1")
		self._track_sides = {}
		self._track_centers = {}
		self._track_missed = {}
		self.occupancy = 0
		self.privacy_drop = PrivacyDrop()
		self.processed_frame = None

	def detect(self, frame):
		if frame is None:
			raise ValueError("detect() requires a non-empty frame")
		try:
			results = self.model.track(
				source=frame,
				classes=[PERSON_CLASS_ID],
				conf=0.1,
				imgsz=self.image_size,
				device=self.device,
				quantize=self.quantize,
				persist=True,
				tracker=self.tracker,
				verbose=False,
			)
		except Exception as exc:
			raise RuntimeError(f"YOLO tracking failed: {exc}") from exc

		detections = []
		in_count = 0
		out_count = 0
		observed_track_ids = set()
		result = None
		box = None
		for result in results:
			for box in result.boxes:
				class_id = int(box.cls[0])
				confidence = float(box.conf[0])
				if class_id != PERSON_CLASS_ID:
					continue

				track_id = None if box.id is None else int(box.id[0])
				if confidence < self.confidence:
					if track_id is not None:
						observed_track_ids.add(track_id)
					continue
				bbox = box.xyxy[0].tolist()
				crossing = None
				if track_id is not None and track_id not in observed_track_ids:
					observed_track_ids.add(track_id)
					crossing = self._get_crossing(track_id, bbox)
				if crossing == "IN":
					in_count += 1
				elif crossing == "OUT":
					out_count += 1

				detections.append(
					{
						"bbox": bbox,
						"confidence": confidence,
						"class_id": class_id,
						"track_id": track_id,
						"crossing": crossing,
					}
				)

		self._age_lost_tracks(observed_track_ids)
		self.occupancy = max(0, self.occupancy + in_count - out_count)
		results = None
		result = None
		box = None
		self.processed_frame = self.privacy_drop.drop(frame)
		return detections

	def _get_crossing(self, track_id, bbox):
		if self.line is None or track_id is None:
			return None

		x1, y1 = self.line[0]
		x2, y2 = self.line[1]
		center_x = (bbox[0] + bbox[2]) / 2
		center_y = (bbox[1] + bbox[3]) / 2
		side_value = (x2 - x1) * (center_y - y1) - (y2 - y1) * (center_x - x1)
		line_length = math.hypot(x2 - x1, y2 - y1)
		signed_distance = side_value / line_length
		current_side = (
			1 if signed_distance > self.line_tolerance
			else -1 if signed_distance < -self.line_tolerance
			else 0
		)
		previous_side = self._track_sides.get(track_id)
		previous_center = self._track_centers.get(track_id)
		self._track_missed[track_id] = 0
		if current_side == 0:
			return None

		self._track_sides[track_id] = current_side
		self._track_centers[track_id] = (center_x, center_y)
		if previous_side is None or previous_side == current_side:
			return None
		if not self._crosses_line_segment(previous_center, (center_x, center_y)):
			return None

		return "IN" if current_side == self.in_side else "OUT"

	def _crosses_line_segment(self, start, end):
		line_start, line_end = self.line
		movement_x = end[0] - start[0]
		movement_y = end[1] - start[1]
		line_x = line_end[0] - line_start[0]
		line_y = line_end[1] - line_start[1]
		denominator = movement_x * line_y - movement_y * line_x
		if denominator == 0:
			return False

		offset_x = line_start[0] - start[0]
		offset_y = line_start[1] - start[1]
		movement_position = (offset_x * line_y - offset_y * line_x) / denominator
		line_position = (offset_x * movement_y - offset_y * movement_x) / denominator
		return 0 <= movement_position <= 1 and 0 <= line_position <= 1

	def _age_lost_tracks(self, observed_track_ids):
		for track_id in list(self._track_sides):
			if track_id in observed_track_ids:
				self._track_missed[track_id] = 0
				continue

			missed_frames = self._track_missed.get(track_id, 0) + 1
			if missed_frames > self.max_track_age:
				self._track_sides.pop(track_id, None)
				self._track_centers.pop(track_id, None)
				self._track_missed.pop(track_id, None)
			else:
				self._track_missed[track_id] = missed_frames
