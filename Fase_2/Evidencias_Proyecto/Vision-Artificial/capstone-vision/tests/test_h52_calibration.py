"""Editor H4 reutilizado con frame fijo y GUI simulada; no es aceptación humana."""

import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from src import calibrate_mp4_zones as app
from src.video_zones import load_video_zones
from src.zone_calibrator import CalibrationEditor
from src.zones import ZoneStore
from h52_test_support import fixture,profile
from video_test_support import temporary_directory
from zone_test_support import make_ui


class CalibrationTests(unittest.TestCase):
    def test_close_without_save_does_not_invent_or_export_zones(self):
        with temporary_directory() as temp:
            ui,_,_=make_ui()
            ui.waitKey.return_value=ord("q")
            with self.assertRaisesRegex(ValueError,"No se guardó un perfil MP4"):
                app.edit_frame(ui,np.zeros((160,160,3),dtype=np.uint8),ZoneStore(Path(temp)/"profiles"))
            ui.destroyAllWindows.assert_called_once()
            self.assertFalse((Path(temp)/"profiles/active.json").exists())

    def test_reads_requested_frame_with_real_decoder_and_releases(self):
        with temporary_directory() as temp:
            video,_,_=fixture(temp,real_video=True)
            frame=app.reference_frame(video,2)
            self.assertEqual(frame.shape,(160,160,3))
            with self.assertRaises(ValueError):app.reference_frame(video,10)
            with self.assertRaises(ValueError):app.reference_frame(video,-1)

    def test_existing_editor_saves_in_private_store_without_camera(self):
        with temporary_directory() as temp:
            store=ZoneStore(Path(temp)/"private_profiles")
            editor=CalibrationEditor(store,0,160,160)
            p=profile()
            editor.polygons={"A":list(p.a),"B":list(p.b)}
            editor.closed={"A":True,"B":True}
            editor.name=p.name
            ui,_,_=make_ui()
            ui.waitKey.side_effect=[ord("s"),13,ord("q")]
            with patch.object(app,"CalibrationEditor",return_value=editor):
                result=app.edit_frame(ui,np.zeros((160,160,3),dtype=np.uint8),store)
            self.assertEqual(result,p)
            ui.VideoCapture.assert_not_called()
            ui.destroyAllWindows.assert_called_once()

    def test_ui_error_releases_window(self):
        with temporary_directory() as temp:
            ui,_,_=make_ui()
            ui.imshow.side_effect=ui.error("GUI unavailable")
            with self.assertRaises(ui.error):
                app.edit_frame(ui,np.zeros((160,160,3),dtype=np.uint8),ZoneStore(Path(temp)/"profiles"))
            ui.destroyAllWindows.assert_called_once()

    def test_cli_exports_only_after_save_and_never_overwrites(self):
        with temporary_directory() as temp:
            root=Path(temp)
            video,_,existing=fixture(root)
            output=root/"new_zones.json"
            with patch.object(app,"PROJECT_ROOT",root), \
                 patch.object(app,"reference_frame",return_value=np.zeros((160,160,3),dtype=np.uint8)), \
                 patch.object(app,"edit_frame",return_value=profile()):
                self.assertEqual(app.main(["--video",str(video),"--output",str(output),"--reviewer","synthetic"]),0)
                self.assertEqual(load_video_zones(output,video).profile,profile())
                before=output.read_bytes()
                with self.assertLogs(app.LOGGER,level="ERROR"):
                    self.assertEqual(app.main(["--video",str(video),"--output",str(output),"--reviewer","synthetic"]),1)
                self.assertEqual(output.read_bytes(),before)


if __name__ == "__main__":unittest.main()
