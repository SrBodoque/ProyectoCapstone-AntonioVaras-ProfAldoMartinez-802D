"""Navigation checkpoints and real Tk/OpenCV adapter lifecycle regression."""
import gc,threading,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch,MagicMock
import cv2,numpy as np
from tkinter import ttk
import test_launcher as existing
from h52_test_support import profile
from src import launcher,launcher_calibration as cal,launcher_autosave as autosave
from src.launcher_ui import TkDialogs
from src.zones import ZoneStore

class StopHere(Exception):pass

class NavigationTests(unittest.TestCase):
    setUp=existing.LauncherTests.setUp
    tearDown=existing.LauncherTests.tearDown
    args=existing.LauncherTests.args
    def nav(self,*flags):
        a=self.args(*flags);a.navigate=True;return a

    def test_editor_cancel_returns_base(self):
        self.ui.choose.side_effect=['new',cal.Cancelled()]
        with patch.object(launcher,'calibrate_video',side_effect=cal.Cancelled),self.assertRaises(cal.Cancelled):
            self.controller.calibrate(self.nav('--mp4'),self.video,None)
        self.assertEqual([c.args[0] for c in self.ui.choose.call_args_list],['Base de calibracion']*2)

    def test_existing_json_list_cancel_returns_base(self):
        self.ui.choose.side_effect=['edit',cal.Cancelled(),cal.Cancelled()]
        with self.assertRaises(cal.Cancelled):self.controller.calibrate(self.nav('--mp4'),self.video,None)
        self.assertEqual([c.args[0] for c in self.ui.choose.call_args_list],['Base de calibracion','Perfiles compatibles','Base de calibracion'])
        self.ui.open_json.assert_not_called()

    def test_base_back_returns_video_catalog(self):
        self.ui.choose.side_effect=[cal.Cancelled(),StopHere()]
        with self.assertRaises(StopHere):self.controller.prepare(self.nav('--calibrar','--mp4','--video',str(self.video)))
        self.assertEqual([c.args[0] for c in self.ui.choose.call_args_list],['Base de calibracion','Videos disponibles'])

    def test_base_back_returns_camera_selection_even_single_camera(self):
        self.ui.choose.side_effect=[0,cal.Cancelled(),StopHere()]
        with patch.object(launcher,'scan_cameras',return_value=[self.camera]),self.assertRaises(StopHere):self.controller.prepare(self.nav('--calibrar','--camara'))
        self.assertEqual([c.args[0] for c in self.ui.choose.call_args_list],['Seleccionar camara','Base de calibracion','Seleccionar camara'])

    def test_video_catalog_back_returns_source_then_main(self):
        self.ui.choose.side_effect=[cal.Cancelled(),cal.Cancelled()]
        with patch('src.launcher_ui.TkDialogs',return_value=self.ui):self.assertEqual(launcher.main(['--calibrar','--mp4']),0)
        self.assertEqual([c.args[0] for c in self.ui.choose.call_args_list],['Videos disponibles','Calibrar zonas'])
        self.ui.menu.assert_called_once();self.ui.close.assert_called_once()

    def test_camera_selection_back_returns_source_then_main(self):
        self.ui.choose.side_effect=[cal.Cancelled(),cal.Cancelled()]
        with patch('src.launcher_ui.TkDialogs',return_value=self.ui),patch.object(launcher,'scan_cameras',return_value=[self.camera]):self.assertEqual(launcher.main(['--calibrar','--camara']),0)
        self.assertEqual([c.args[0] for c in self.ui.choose.call_args_list],['Seleccionar camara','Calibrar zonas'])
        self.ui.menu.assert_called_once()

    def test_settings_back_returns_profiles_keeps_source(self):
        a=self.nav('--mp4','--video',str(self.video),'--zones',str(self.zones));a.review=True
        self.ui.settings.side_effect=cal.Cancelled;self.ui.choose.side_effect=StopHere
        with self.assertRaises(StopHere):self.controller.prepare(a)
        self.assertEqual(self.ui.choose.call_args.args[0],'Zonas de transicion');self.assertEqual(a.video,self.video)
        self.assertEqual((a.device,a.weights_dir),('cpu',self.weights))

    def test_settings_back_after_calibration_returns_confirmation_without_redraw(self):
        a=self.nav('--calibrar','--mp4','--video',str(self.video),'--output',str(self.root/'explicit.json'),'--reviewer','TEST')
        self.ui.settings.side_effect=[cal.Cancelled(),('bytetrack','cpu',self.weights)]
        def edit(*a,**kw):kw['on_save'](profile(),False);return profile()
        with patch.object(cal,'edit_profile',side_effect=edit) as editor:result=self.controller.prepare(a)
        self.assertEqual(result.zones,self.root/'explicit.json');self.assertEqual(editor.call_count,1)
        self.assertEqual(self.ui.confirm.call_count,2)

    def test_second_session_after_cancel_and_view_close_goes_main(self):
        self.ui.menu.side_effect=['video',cal.Cancelled()]
        options=NS()
        with patch('src.launcher_ui.TkDialogs',return_value=self.ui),patch.object(launcher.Launcher,'prepare',side_effect=[cal.Cancelled(),options]) as prepare:
            self.assertEqual(launcher.main(['--mp4','--tracker','bytetrack','--device','cpu','--weights-dir',str(self.weights)]),0)
        self.assertEqual(prepare.call_count,2);self.ui.run_view.assert_called_once_with(options)
        self.assertEqual(self.ui.menu.call_count,2)

    def test_native_file_cancel_returns_catalog(self):
        self.ui.choose.side_effect=['external',StopHere()]
        with self.assertRaises(StopHere):self.controller.prepare(self.nav('--mp4'))
        self.assertEqual([c.args[0] for c in self.ui.choose.call_args_list],['Videos disponibles']*2)

    def test_real_choice_escape_x_and_back_leave_no_timers(self):
        for action in ('escape','x','button'):
            ui=TkDialogs()
            try:
                def back():
                    top=ui.root.winfo_children()[0]
                    if action=='x':ui.root.tk.call(top.protocol('WM_DELETE_WINDOW'))
                    elif action=='escape':top.update_idletasks();top.focus_force();top.event_generate('<Escape>',when='tail')
                    else:
                        next(w for w in top.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='Volver').invoke()
                ui.root.after(10,back)
                with self.assertRaises(cal.Cancelled):ui.choose('Prueba','Volver',[('ok','Continuar')])
                self.assertFalse(ui.root.winfo_children());self.assertFalse(ui.root.tk.call('after','info'))
            finally:ui.close();gc.collect()

    def test_real_settings_escape_and_x_preserve_ui_preferences(self):
        for action in ('escape','x','button'):
            ui=TkDialogs();a=self.args('--mp4','--video',str(self.video))
            try:
                def back():
                    for top in ui.root.winfo_children():
                        if top.title()=='LimpIA - Preparar sesion':
                            form=next(w for w in top.winfo_children() if w.winfo_class()=='Frame')
                            combos=[w for w in form.winfo_children() if isinstance(w,ttk.Combobox)]
                            combos[0].set('botsort')
                            if action=='x':ui.root.tk.call(top.protocol('WM_DELETE_WINDOW'))
                            elif action=='escape':top.update_idletasks();top.focus_force();top.event_generate('<Escape>',when='tail')
                            else:next(w for w in top.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='Volver').invoke()
                            return
                    ui.root.after(10,back)
                ui.root.after(10,back)
                with patch('src.devices.load_torch'),patch('src.devices.discover_devices',return_value=NS(devices=[NS(device='cpu')])),self.assertRaises(cal.Cancelled):ui.settings(a,None)
                self.assertEqual(a.tracker,'botsort');self.assertEqual(a.device,'cpu')
                self.assertFalse(ui.root.winfo_children());self.assertFalse(ui.root.tk.call('after','info'))
            finally:ui.close();gc.collect()

    def test_editor_escape_q_and_x_cancel_without_export(self):
        for key in (27,ord('q'),-1):
            store=ZoneStore(self.root/f'editor{key}');store.save_and_activate(profile())
            save=MagicMock()
            with patch.object(cv2,'namedWindow'),patch.object(cv2,'setMouseCallback'),patch.object(cv2,'imshow'),patch.object(cv2,'destroyWindow'),patch.object(cv2,'waitKey',return_value=key),patch.object(cv2,'getWindowProperty',return_value=0),self.assertRaises(cal.Cancelled):
                cal.edit_camera_frame(cv2,np.zeros((160,160,3),np.uint8),store,0,on_save=save)
            save.assert_not_called()

    def test_dirty_editor_requires_confirmation_before_discard(self):
        store=ZoneStore(self.root/'dirty');store.save_and_activate(profile())
        from src.zone_calibrator import render_editor
        edits=[]
        def render(cv,frame,editor):
            if not edits:editor.polygons['A'][0]=(.11,.2);edits.append(editor)
            return render_editor(cv,frame,editor)
        with patch.object(cv2,'namedWindow'),patch.object(cv2,'setMouseCallback'),patch.object(cv2,'imshow'),patch.object(cv2,'destroyWindow'),patch.object(cv2,'waitKey',side_effect=[27,ord('y')]),patch.object(cv2,'getWindowProperty',return_value=1),patch('src.zone_calibrator.render_editor',side_effect=render),self.assertRaises(cal.Cancelled):
            cal.edit_camera_frame(cv2,np.zeros((160,160,3),np.uint8),store,0,on_save=lambda *a:self.fail('no export'))
        self.assertTrue(edits[0].exit_requested)

    def test_busy_escape_joins_worker(self):
        ui=TkDialogs()
        try:
            def back():
                top=ui.root.winfo_children()[0];top.update_idletasks();top.focus_force();top.event_generate('<Escape>',when='tail')
            ui.root.after(10,back)
            with self.assertRaises(cal.Cancelled):ui.busy(lambda cancel:cancel.wait(1),'TEST')
            self.assertFalse([t for t in threading.enumerate() if t.name=='LimpIA-launcher-check'])
            self.assertFalse(ui.root.tk.call('after','info'))
        finally:ui.close();gc.collect()

    def test_main_menu_escape_does_not_exit_only_salir_does(self):
        ui=TkDialogs();observed=[]
        try:
            def escape():
                top=ui.root.winfo_children()[0];top.update_idletasks();top.focus_force();top.event_generate('<Escape>',when='tail')
                def exit_menu():
                    observed.append(bool(top.winfo_exists()))
                    next(w for w in top.winfo_children() if isinstance(w,ttk.Button) and w.cget('text')=='Salir').invoke()
                ui.root.after_idle(exit_menu)
            ui.root.after(10,escape)
            with self.assertRaises(cal.Cancelled):ui.menu()
            self.assertEqual(observed,[True])
        finally:ui.close();gc.collect()

    def test_window_host_cancels_timers_and_can_open_twice(self):
        ui=TkDialogs();instances=[]
        def window(top,options):
            instance=MagicMock();instance.session.thread=None;instance.session.snapshot.return_value=NS(error='')
            top.after(10000,lambda:None)
            top.after(80,top.destroy)
            instances.append(instance);return instance
        try:
            with patch('src.view_presentation.PresentationWindow',side_effect=window):
                for _ in range(2):
                    self.assertFalse(ui.run_view(NS()))
                    self.assertFalse(ui.root.tk.call('after','info'));self.assertFalse(ui.root.winfo_children())
            for instance in instances:instance.start.assert_called_once();instance.session.stop.assert_called_once()
        finally:ui.close();gc.collect()

    def test_native_json_cancel_returns_profile_catalog(self):
        self.ui.choose.side_effect=['existing',StopHere()]
        with self.assertRaises(StopHere):self.controller.prepare(self.nav('--mp4','--video',str(self.video)))
        self.assertEqual([c.args[0] for c in self.ui.choose.call_args_list],['Zonas de transicion']*2)

    def test_calibration_back_from_profile_choice_returns_profile_choice(self):
        self.ui.choose.side_effect=['new',cal.Cancelled(),StopHere()]
        with self.assertRaises(StopHere):self.controller.prepare(self.nav('--mp4','--video',str(self.video)))
        self.assertEqual([c.args[0] for c in self.ui.choose.call_args_list],['Zonas de transicion','Base de calibracion','Zonas de transicion'])
