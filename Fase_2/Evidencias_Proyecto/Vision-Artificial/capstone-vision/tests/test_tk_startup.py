"""Regression for the actual settings-button callback, not only Launcher.prepare."""
import gc,threading,unittest,sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import tkinter as tk
from tkinter import ttk
from src.launcher_ui import TkDialogs
from src.launcher_calibration import Cancelled
from video_test_support import temporary_directory


class TkStartupTests(unittest.TestCase):
    def test_settings_button_reads_tk_only_on_main_thread_twice(self):
        gc.collect();ui=TkDialogs();errors=[];reads=[];workers=[]
        self.addCleanup(gc.collect)
        unraisable=[]
        hook=patch.object(sys,"unraisablehook",side_effect=lambda exc:unraisable.append(str(exc.exc_value)))
        hook.start();self.addCleanup(hook.stop)
        ui.root.report_callback_exception=lambda *exc:(errors.append(str(exc[1])),[w.destroy() for w in list(ui.root.winfo_children())])
        owner=threading.get_ident();original=tk.StringVar.get
        def get(variable):
            reads.append(threading.get_ident())
            if threading.get_ident()!=owner:raise AssertionError('Tk Variable read from worker')
            return original(variable)
        def validate(device):
            workers.append(threading.get_ident());gc.collect()
            self.assertEqual(device,'cpu')
        def click():
            for top in ui.root.winfo_children():
                if top.title()=='LimpIA - Preparar sesion':
                    for child in top.winfo_children():
                        if isinstance(child,ttk.Button) and child.cget('text')=='Iniciar visualizador':child.invoke();return
            ui.root.after(10,click)
        with temporary_directory() as folder:
            weights=Path(folder);(weights/'yolo26n.pt').write_bytes(b'fixture, never loaded')
            args=NS(tracker='bytetrack',device='cpu',weights_dir=weights,mp4=True,video=Path('fixture.mp4'),camera_index=None)
            try:
                with patch('src.devices.load_torch'),patch('src.devices.discover_devices',return_value=NS(devices=[NS(device='cpu')])),patch('src.devices.validate_device',side_effect=validate),patch.object(tk.StringVar,'get',get):
                    for _ in range(2):
                        ui.root.after(10,click)
                        result=ui.settings(args,None)
                        self.assertEqual(result,('bytetrack','cpu',weights))
                        gc.collect()
                self.assertFalse(errors);self.assertFalse(unraisable)
                self.assertTrue(reads);self.assertEqual(set(reads),{owner})
                self.assertTrue(workers);self.assertNotIn(owner,workers)
                self.assertFalse(any(t.name=='LimpIA-launcher-check' and t.is_alive() for t in threading.enumerate()))
            finally:ui.close();gc.collect()


    def test_settings_recovers_after_cancel_and_device_error(self):
        gc.collect();ui=TkDialogs();errors=[];attempts=[]
        ui.root.report_callback_exception=lambda *exc:errors.append(str(exc[1]))
        real_busy=ui.busy
        def busy(function,title):
            if title=='Validando dispositivo':
                attempts.append(title)
                if len(attempts)==1:raise Cancelled()
                if len(attempts)==2:raise RuntimeError('CUDA unavailable; select CPU')
            return real_busy(function,title)
        def click():
            for top in ui.root.winfo_children():
                if top.title()=='LimpIA - Preparar sesion':
                    for child in top.winfo_children():
                        if isinstance(child,ttk.Button) and child.cget('text')=='Iniciar visualizador':
                            child.invoke()
                            if len(attempts)<3:ui.root.after(10,click)
                            return
            ui.root.after(10,click)
        try:
            with temporary_directory() as folder:
                weights=Path(folder);(weights/'yolo26n.pt').write_bytes(b'fixture')
                args=NS(tracker='bytetrack',device='cpu',weights_dir=weights,mp4=True,video=Path('fixture.mp4'),camera_index=None)
                with patch.object(ui,'busy',side_effect=busy),patch('src.devices.load_torch'),patch('src.devices.discover_devices',return_value=NS(devices=[NS(device='cpu')])),patch('src.devices.validate_device'):
                    ui.root.after(10,click)
                    self.assertEqual(ui.settings(args,None),('bytetrack','cpu',weights))
                self.assertEqual(len(attempts),3);self.assertFalse(errors)
        finally:ui.close();gc.collect()
