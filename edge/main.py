import argparse
import ctypes
import json
import math
import os
import time

import cv2
import numpy as np

from .mqtt.publisher import MqttPublisher, build_telemetry
from .input import InputDeviceManager
from .vision.detector import PersonDetector
from .vision.webcam import WebcamCapture


class _TelemetryIntervalPublisher:
	def __init__(self, publisher, detector, facility_id, reporting_interval_seconds):
		self.publisher = publisher
		self.detector = detector
		self.facility_id = facility_id
		self.reporting_interval_seconds = reporting_interval_seconds
		self.interval_start = time.monotonic()
		self.pending_in = 0
		self.pending_out = 0
		self.has_frames = False

	def observe(self, detections):
		self.pending_in += sum(detection["crossing"] == "IN" for detection in detections)
		self.pending_out += sum(detection["crossing"] == "OUT" for detection in detections)
		self.has_frames = True
		now = time.monotonic()
		elapsed = now - self.interval_start
		if elapsed >= self.reporting_interval_seconds:
			self._publish_pending(elapsed)
			self.interval_start = now

	def flush(self):
		if self.has_frames:
			self._publish_pending(time.monotonic() - self.interval_start)

	def _publish_pending(self, elapsed_seconds):
		interval_metadata = (
			{"reporting_interval_seconds": elapsed_seconds}
			if elapsed_seconds > 0
			else {}
		)
		telemetry = build_telemetry(
			self.facility_id,
			self.detector.occupancy,
			self.pending_in,
			self.pending_out,
			**interval_metadata,
		)
		try:
			self.publisher.publish(telemetry)
		except Exception:
			self.pending_in = 0
			self.pending_out = 0
			self.has_frames = False
			raise
		print(f"Published telemetry: {json.dumps(telemetry)}")
		self.pending_in = 0
		self.pending_out = 0
		self.has_frames = False


class EdgePipeline:
	def __init__(self, camera=None, detector=None, publisher=None, facility_id=None, line=None, reporting_interval_seconds=None, source=None, input_type=None, width=None, height=None):
		self.camera = camera or create_input_source(source=source, input_type=input_type, width=width, height=height)
		self.detector = detector if detector is not None else PersonDetector(line=line)
		self._custom_line = line is not None or getattr(self.detector, "line", None) is not None
		self.publisher = publisher if publisher is not None else MqttPublisher()
		self.facility_id = facility_id or os.getenv("FACILITY_ID", "facility-1")
		interval = reporting_interval_seconds
		if interval is None:
			interval = os.getenv("REPORTING_INTERVAL_SECONDS", "60")
		self.reporting_interval_seconds = float(interval)
		if not math.isfinite(self.reporting_interval_seconds) or self.reporting_interval_seconds <= 0:
			raise ValueError("reporting_interval_seconds must be greater than zero")

	def run(self):
		reporter = _TelemetryIntervalPublisher(
			self.publisher,
			self.detector,
			self.facility_id,
			self.reporting_interval_seconds,
		)
		last_source = None
		last_source_size = None
		try:
			with self.camera as camera:
				while True:
					ok, frame = camera.read()
					if not ok:
						break
					source_size = (frame.shape[1], frame.shape[0])
					active_source = getattr(camera, "source", camera)
					if not self._custom_line and (
						active_source is not last_source or source_size != last_source_size
					):
						self.detector.line = _line_for_frame(*source_size)
					last_source = active_source
					last_source_size = source_size

					detections = self.detector.detect(frame)
					reporter.observe(detections)
					frame = None
					yield {
						"detections": detections,
						"occupancy": self.detector.occupancy,
					}
		except RuntimeError as exc:
			raise RuntimeError(f"Edge pipeline failed: {exc}") from exc
		finally:
			try:
				reporter.flush()
			finally:
				self.publisher.close()


def _parse_source(value):
	try:
		return int(value)
	except ValueError:
		return value


def _parse_line(value):
	try:
		coordinates = tuple(float(coordinate) for coordinate in value.split(","))
		if len(coordinates) != 4:
			raise ValueError
	except ValueError as exc:
		raise argparse.ArgumentTypeError("line must be x1,y1,x2,y2") from exc
	return ((coordinates[0], coordinates[1]), (coordinates[2], coordinates[3]))


def _line_for_frame(width, height, line=None):
	if line is not None:
		return line
	line_x = width // 2
	return ((line_x, 0), (line_x, height - 1))


def _line_side_labels(line, in_side, offset=48):
	if line is None:
		raise ValueError("line is required for side labels")
	(x1, y1), (x2, y2) = line
	dx = x2 - x1
	dy = y2 - y1
	length = math.hypot(dx, dy)
	if length == 0:
		raise ValueError("line endpoints must be different")

	midpoint = ((x1 + x2) / 2, (y1 + y2) / 2)
	normal = (-dy / length, dx / length)
	positive = (
		midpoint[0] + normal[0] * offset,
		midpoint[1] + normal[1] * offset,
	)
	negative = (
		midpoint[0] - normal[0] * offset,
		midpoint[1] - normal[1] * offset,
	)
	positive_label = ("IN ->", positive) if in_side in (1, "positive") else ("OUT <-", positive)
	negative_label = ("OUT <-", negative) if in_side in (1, "positive") else ("IN ->", negative)
	return {"positive": positive_label, "negative": negative_label}


def _draw_side_label(frame, text, position, color):
	font = cv2.FONT_HERSHEY_SIMPLEX
	font_scale = 0.55
	thickness = 2
	(text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
	frame_height, frame_width = frame.shape[:2]
	padding = 8
	x = max(padding, min(frame_width - text_width - padding, int(position[0] - text_width / 2)))
	y = max(text_height + baseline + padding, min(frame_height - padding, int(position[1] + text_height / 2)))
	cv2.rectangle(
		frame,
		(x - padding, y - text_height - baseline - padding),
		(x + text_width + padding, y + padding),
		(18, 24, 32),
		-1,
	)
	cv2.putText(frame, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)


def _draw_counting_line_and_labels(frame, line, in_side):
	line_start, line_end = line
	cv2.line(
		frame,
		tuple(map(int, line_start)),
		tuple(map(int, line_end)),
		(0, 220, 255),
		3,
		cv2.LINE_AA,
	)
	labels = _line_side_labels(line, in_side)
	_draw_side_label(frame, *labels["positive"], (0, 220, 0) if labels["positive"][0].startswith("IN") else (0, 0, 220))
	_draw_side_label(frame, *labels["negative"], (0, 220, 0) if labels["negative"][0].startswith("IN") else (0, 0, 220))


def _draw_hud(frame, fps, total_in, total_out, occupancy, capacity, privacy_enabled):
	if capacity and capacity > 0:
		percentage = round(occupancy / capacity * 100)
		status = "GREEN" if percentage < 50 else "YELLOW" if percentage <= 80 else "RED"
		occupancy_text = f"{occupancy}/{capacity} ({percentage}%)"
	else:
		status = "UNKNOWN"
		occupancy_text = f"{occupancy}/-- (--%)"

	metrics_text = (
		f"FPS {fps:4.1f}   IN {total_in}   OUT {total_out}   "
		f"OCCUPANCY {occupancy_text}   {status}"
	)
	privacy_text = f"PRIVACY: {'ON' if privacy_enabled else 'OFF'} (LOCAL)   [1] ON   [2] OFF"
	font = cv2.FONT_HERSHEY_SIMPLEX
	font_scale = 0.56
	thickness = 2
	(metrics_width, metrics_height), metrics_baseline = cv2.getTextSize(metrics_text, font, font_scale, thickness)
	(privacy_width, privacy_height), privacy_baseline = cv2.getTextSize(privacy_text, font, font_scale, thickness)
	padding_x = 14
	padding_y = 10
	frame_height, frame_width = frame.shape[:2]
	box_width = min(frame_width - 20, max(metrics_width, privacy_width) + padding_x * 2)
	box_height = metrics_height + metrics_baseline + privacy_height + privacy_baseline + padding_y * 2 + 5
	cv2.rectangle(frame, (10, 10), (10 + box_width, 10 + box_height), (18, 24, 32), -1)
	cv2.putText(frame, metrics_text, (10 + padding_x, 10 + padding_y + metrics_height), font, font_scale, (235, 240, 245), thickness, cv2.LINE_AA)
	cv2.putText(frame, privacy_text, (10 + padding_x, 10 + padding_y + metrics_height + metrics_baseline + 5 + privacy_height), font, font_scale, (184, 211, 199), thickness, cv2.LINE_AA)


def _draw_source_label(frame, source):
	"""Keep the selected source visible without making resolution a headline."""
	name = getattr(source, "input_type", None) or getattr(source, "description", "unknown")
	connection = getattr(source, "connection", "local")
	text = f"CAMERA: {str(name).upper()}   CONNECTION: {str(connection).upper()}"
	cv2.putText(frame, text, (18, frame.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (235, 240, 245), 2, cv2.LINE_AA)


def _privacy_state_for_key(privacy_enabled, key):
	if key == ord("1"):
		return True
	if key == ord("2"):
		return False
	return privacy_enabled


def _screen_dimensions():
	try:
		user32 = ctypes.windll.user32
		return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
	except (AttributeError, OSError):
		try:
			import tkinter

			root = tkinter.Tk()
			root.withdraw()
			dimensions = (root.winfo_screenwidth(), root.winfo_screenheight())
			root.destroy()
			return dimensions
		except Exception:
			return 1280, 800


def _fit_frame_to_screen(frame, screen_dimensions):
	geometry = _display_geometry(frame.shape[:2], screen_dimensions)
	display_width = geometry["display_size"][0]
	display_height = geometry["display_size"][1]
	canvas_width = geometry["canvas_size"][0]
	canvas_height = geometry["canvas_size"][1]
	resized = frame if geometry["scale"] == 1 else cv2.resize(
		frame,
		(display_width, display_height),
		interpolation=cv2.INTER_AREA,
	)
	canvas = np.zeros((canvas_height, canvas_width, frame.shape[2]), dtype=frame.dtype)
	offset_x, offset_y = geometry["offset"]
	canvas[offset_y:offset_y + display_height, offset_x:offset_x + display_width] = resized
	return canvas


def _display_geometry(frame_shape, screen_dimensions):
	frame_height, frame_width = frame_shape
	canvas_width = max(1, screen_dimensions[0] - 80)
	canvas_height = max(1, screen_dimensions[1] - 140)
	scale = min(1.0, canvas_width / frame_width, canvas_height / frame_height)
	display_width = max(1, round(frame_width * scale))
	display_height = max(1, round(frame_height * scale))
	offset = ((canvas_width - display_width) // 2, (canvas_height - display_height) // 2)
	return {
		"source_size": (frame_width, frame_height),
		"display_size": (display_width, display_height),
		"canvas_size": (canvas_width, canvas_height),
		"scale": scale,
		"offset": offset,
		"source_center_x": frame_width // 2,
		"display_center_x": offset[0] + int((frame_width // 2) * scale),
	}


def _debug_display_geometry(frame_shape, screen_dimensions):
	if os.getenv("EDGE_DEBUG_DISPLAY", "0").lower() not in {"1", "true", "yes"}:
		return
	geometry = _display_geometry(frame_shape, screen_dimensions)
	print(
		"SOURCE: "
		f"{geometry['source_size'][0]}x{geometry['source_size'][1]} "
		"DISPLAY: "
		f"{geometry['display_size'][0]}x{geometry['display_size'][1]} "
		"CANVAS: "
		f"{geometry['canvas_size'][0]}x{geometry['canvas_size'][1]} "
		"SCALE: "
		f"{geometry['scale']:.3f} "
		"OFFSET: "
		f"{geometry['offset'][0]},{geometry['offset'][1]} "
		"CENTER LINE SOURCE X: "
		f"{geometry['source_center_x']} "
		"CENTER LINE DISPLAY X: "
		f"{geometry['display_center_x']}"
	)


def run_visual_demo(
	source=None,
	model_path="yolov8n.pt",
	line=None,
	in_side="positive",
	confidence=0.35,
	image_size=640,
	width=None,
	height=None,
	input_type=None,
):
	if (
		isinstance(source, int)
		or str(source).lower() == "webcam"
		or (source is None and (input_type or os.getenv("INPUT_TYPE", "webcam")).lower() in {"webcam", "camera"})
	):
		if (width is None) != (height is None):
			raise ValueError("width and height must be provided together")
		if width is None:
			width, height = 1280, 720
	camera = InputDeviceManager(
		source=source,
		input_type=input_type,
		width=width,
		height=height,
		webcam_capture_cls=WebcamCapture,
	)
	if os.getenv("EDGE_CONTROL_ENABLED", "1").lower() not in {"0", "false", "no"}:
		try:
			from cloud.api.local_server import start_server_in_thread
			start_server_in_thread(camera, host=os.getenv("EDGE_CONTROL_HOST", "127.0.0.1"), port=int(os.getenv("EDGE_CONTROL_PORT", "8000")))
		except (OSError, ValueError) as exc:
			print(f"Input control API unavailable: {exc}")
	screen_dimensions = _screen_dimensions()
	detector = None
	last_source_size = None
	last_source = None
	privacy_enabled = True
	total_in = 0
	total_out = 0
	facility_id = os.getenv("FACILITY_ID", "facility-1")
	try:
		interval = float(os.getenv("REPORTING_INTERVAL_SECONDS", "60"))
	except ValueError as exc:
		raise ValueError("REPORTING_INTERVAL_SECONDS must be a positive number") from exc
	if not math.isfinite(interval) or interval <= 0:
		raise ValueError("REPORTING_INTERVAL_SECONDS must be a positive number")
	try:
		capacity = int(os.getenv("FACILITY_CAPACITY", ""))
	except ValueError:
		capacity = None
	window_name = "Crowd monitor"
	window_created = False
	fps_window_start = time.perf_counter()
	fps_frame_count = 0
	fps = 0.0
	publisher = MqttPublisher()
	reporter = None
	try:
		reporter = _TelemetryIntervalPublisher(
			publisher,
			detector,
			facility_id,
			interval,
		)
		with camera as capture:
			failed_reads = 0
			while True:
				ok, frame = capture.read()
				if not ok:
					failed_reads += 1
					if getattr(capture.source, "is_live", False) and failed_reads < 4:
						time.sleep(0.05)
						continue
					break
				failed_reads = 0

				source_size = (frame.shape[1], frame.shape[0])
				active_source = getattr(capture, "source", capture)
				source_changed = active_source is not last_source
				size_changed = source_size != last_source_size
				if detector is None:
					height, width = frame.shape[:2]
					counting_line = _line_for_frame(width, height, line)
					detector = PersonDetector(
						model_path=model_path,
						confidence=confidence,
						image_size=image_size,
						line=counting_line,
						in_side=in_side,
					)
				elif line is None and (source_changed or size_changed):
					# The input can be switched at runtime. Keep the default line
					# centered in the new source frame; explicit custom lines are kept.
					detector.line = _line_for_frame(frame.shape[1], frame.shape[0])
				if source_changed or size_changed:
					last_source = active_source
					last_source_size = source_size
					_debug_display_geometry(frame.shape[:2], screen_dimensions)

				detections = detector.detect(frame)
				display_frame = detector.processed_frame if privacy_enabled else frame.copy()
				reporter.detector = detector
				frame_in = sum(item["crossing"] == "IN" for item in detections)
				frame_out = sum(item["crossing"] == "OUT" for item in detections)
				total_in += frame_in
				total_out += frame_out
				reporter.observe(detections)
				_draw_counting_line_and_labels(display_frame, detector.line, getattr(detector, "in_side", 1))
				for item in detections:
					x1, y1, x2, y2 = (int(value) for value in item["bbox"])
					track_id = "?" if item["track_id"] is None else str(item["track_id"])
					label = f"ID {track_id} {item['confidence']:.2f}"
					if item["crossing"]:
						label += f" {item['crossing']}"
					color = {
						"IN": (0, 220, 0),
						"OUT": (0, 0, 220),
						None: (255, 160, 0),
					}[item["crossing"]]
					cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
					cv2.putText(display_frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

				fps_frame_count += 1
				fps_now = time.perf_counter()
				fps_elapsed = fps_now - fps_window_start
				if fps_elapsed >= 0.5:
					fps = fps_frame_count / fps_elapsed
					fps_window_start = fps_now
					fps_frame_count = 0
				_draw_hud(display_frame, fps, total_in, total_out, detector.occupancy, capacity, privacy_enabled)
				_draw_source_label(display_frame, capture)
				display_frame = _fit_frame_to_screen(display_frame, screen_dimensions)
				if not window_created:
					cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
					cv2.resizeWindow(window_name, display_frame.shape[1], display_frame.shape[0])
					window_created = True
				cv2.imshow(window_name, display_frame)
				key = cv2.waitKey(1) & 0xFF
				privacy_enabled = _privacy_state_for_key(privacy_enabled, key)
				if key in (ord("q"), 27):
					break
	finally:
		try:
			if reporter is not None:
				reporter.flush()
		finally:
			try:
				publisher.close()
			finally:
				cv2.destroyAllWindows()


def main(argv=None):
	parser = argparse.ArgumentParser(description="Run the local crowd-monitoring visual demo.")
	parser.add_argument(
		"--source",
		type=_parse_source,
		default=None,
		help="webcam, numeric camera index, local video path, or rtsp:// URL; defaults to webcam 0",
	)
	parser.add_argument(
		"--input-type",
		choices=("webcam", "usb", "file", "rtsp", "cctv", "wifi", "phone", "bluetooth"),
		help="explicit input type; otherwise inferred from --source or INPUT_TYPE",
	)
	parser.add_argument("--model", default="yolov8n.pt", help="YOLOv8 model file")
	parser.add_argument("--line", type=_parse_line, help="counting line as x1,y1,x2,y2; defaults to frame center")
	parser.add_argument("--in-side", choices=("positive", "negative"), default="positive")
	parser.add_argument("--confidence", type=float, default=0.4, help="minimum person confidence (0-1)")
	parser.add_argument("--image-size", type=int, default=640, help="YOLO inference size; larger can improve small-person detection")
	parser.add_argument("--width", type=int, help="optional requested camera width; ignored if unsupported")
	parser.add_argument("--height", type=int, help="optional requested camera height; ignored if unsupported")
	args = parser.parse_args(argv)
	call_args = (
		args.source,
		args.model,
		args.line,
		args.in_side,
		args.confidence,
		args.image_size,
		args.width,
		args.height,
	)
	if args.input_type is None:
		run_visual_demo(*call_args)
	else:
		run_visual_demo(*call_args, input_type=args.input_type)


if __name__ == "__main__":
	main()
