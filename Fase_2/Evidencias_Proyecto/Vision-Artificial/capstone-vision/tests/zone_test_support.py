"""Datos geométricos sintéticos y GUI/cámara simuladas solo para pruebas H4."""

import importlib
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import src
from src.zones import ZoneProfile

A = ((.55, .1), (.95, .1), (.95, .9), (.55, .9))
B = ((.05, .1), (.45, .1), (.45, .9), (.05, .9))


def profile(name="prueba", camera=1, width=640, height=480):
    return ZoneProfile.create(name, camera, width, height, A, B)


def make_ui():
    class CvError(Exception): pass
    ui = MagicMock(error=CvError)
    constants = ("CAP_DSHOW", "CAP_MSMF", "CAP_V4L2", "CAP_AVFOUNDATION", "CAP_ANY",
                 "CAP_PROP_FRAME_WIDTH", "CAP_PROP_FRAME_HEIGHT", "CAP_PROP_FPS",
                 "WINDOW_NORMAL", "WINDOW_AUTOSIZE", "WND_PROP_VISIBLE", "FONT_HERSHEY_SIMPLEX", "LINE_AA",
                 "EVENT_LBUTTONDOWN", "EVENT_LBUTTONUP", "EVENT_MOUSEMOVE", "EVENT_RBUTTONDOWN")
    for i, name in enumerate(constants): setattr(ui, name, i + 1)
    frame = np.full((480, 640, 3), 70, dtype=np.uint8)
    capture = ui.VideoCapture.return_value
    capture.read.side_effect = lambda: (True, frame.copy())
    capture.getBackendName.return_value = "SIMULATED"
    capture.get.return_value = 0
    ui.getWindowProperty.return_value = 1
    ui.waitKey.return_value = ord("q")
    ui.resize.side_effect = lambda image, size: np.zeros((size[1], size[0], 3), dtype=np.uint8)
    return ui, capture, frame


@contextmanager
def camera_module(ui):
    previous = sys.modules.get("src.camera")
    attribute = getattr(src, "camera", None)
    try:
        with patch.dict(sys.modules, {"cv2": ui}):
            camera = importlib.import_module("src.camera")
            with patch.object(camera, "cv2", ui): yield camera
    finally:
        if previous is None: sys.modules.pop("src.camera", None)
        else: sys.modules["src.camera"] = previous
        if attribute is None:
            if hasattr(src, "camera"): delattr(src, "camera")
        else: src.camera = attribute
