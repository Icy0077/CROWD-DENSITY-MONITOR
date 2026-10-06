"""Aspect-ratio-safe display and coordinate transforms for every source."""
import cv2
import numpy as np


def letterbox(frame, size, color=(0, 0, 0)):
    target_width, target_height = size
    height, width = frame.shape[:2]
    scale = min(target_width / width, target_height / height)
    resized = cv2.resize(frame, (round(width * scale), round(height * scale)))
    canvas = np.full((target_height, target_width, frame.shape[2]), color, dtype=frame.dtype)
    left = (target_width - resized.shape[1]) // 2
    top = (target_height - resized.shape[0]) // 2
    canvas[top:top + resized.shape[0], left:left + resized.shape[1]] = resized
    return canvas, {"scale": scale, "offset": (left, top), "source_size": (width, height), "target_size": size}


def source_to_display(point, transform):
    scale = transform["scale"]
    left, top = transform["offset"]
    return point[0] * scale + left, point[1] * scale + top


def display_to_source(point, transform):
    scale = transform["scale"]
    left, top = transform["offset"]
    return (point[0] - left) / scale, (point[1] - top) / scale
