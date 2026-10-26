"""Regresiones existentes ejecutables sin PyYAML/PyTorch ni temporales restrictivos.

No reemplaza la suite completa, que debe ejecutarse en un entorno completo.
"""

import unittest


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name in (
        "test_hito1.ResourceTests",
        "test_camera_selector.ScanTests",
        "test_camera_selector.SelectionTests",
        "test_hito2.DetectionResourceTests",
        "test_device_selector.DeviceTests",
    ):
        suite.addTests(loader.loadTestsFromName(name))
    from test_hito2 import DetectorTests
    for method in loader.getTestCaseNames(DetectorTests):
        # Ese caso usa TemporaryDirectory(mode=0o700) y falla por ACL del sandbox.
        # Su exclusión se documenta; no se presenta como omitido aprobado.
        if method != "test_model_path_independent_of_cwd":
            suite.addTest(DetectorTests(method))
    return suite
