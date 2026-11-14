"""Real Tk layout regressions with synthetic names and mocked device checks."""
from pathlib import Path
from types import SimpleNamespace as NS
import tkinter as tk
from tkinter import font as tkfont, ttk
import unittest
from unittest.mock import patch

from src.launcher_calibration import Cancelled
from src.launcher_ui import CompactLabel, TkDialogs, choice_text, display_message, ellipsize


class LauncherFormattingTests(unittest.TestCase):
    def test_ellipsis_preserves_suffix_and_fits(self):
        text = 'perfil_' + 'área_amplia_' * 40 + '.json'
        for width in (0, 1, 2, 12, 80, len(text)):
            shown = ellipsize(text, len, width)
            self.assertLessEqual(len(shown), width)
        self.assertEqual(ellipsize('video.mp4', len, 30), 'video.mp4')
        self.assertTrue(ellipsize(text, len, 80).endswith('.json'))
        self.assertEqual(ellipsize('', len, 0), '')
        self.assertEqual(ellipsize('a\nb\tc', len, 20), 'a b c')

    def test_catalog_names_and_notices_keep_paths_out_of_primary_text(self):
        path = Path('C:/carpeta extensa/material/video de prueba.mp4')
        self.assertEqual(choice_text(str(path), f'{path.name} | {path.parent}'), path.name)
        profile = path.with_suffix('.json')
        self.assertEqual(choice_text(str(profile), f'Entrada principal | {profile}'),
                         'Entrada principal · video de prueba.json')
        self.assertEqual(choice_text('external', 'Buscar otro archivo…'), 'Buscar otro archivo…')
        self.assertEqual(display_message(f'Perfil creado: {profile}'), 'Perfil creado: video de prueba.json')
        self.assertEqual(display_message(f'{profile}\nIniciar ahora?'), 'video de prueba.json\nIniciar ahora?')


class LauncherLayoutTests(unittest.TestCase):
    def setUp(self):
        self.ui = TkDialogs()
        self.addCleanup(self.ui.close)
        self.errors = []
        self.ui.root.report_callback_exception = lambda *exc: self.errors.append(exc[1])
        self.path = Path('C:/') / ('carpeta_larga_' * 12) / ('archivo_' * 30 + '.mp4')

    def schedule(self, inspect, close=True):
        def callback():
            top = self.ui.root.winfo_children()[0]
            try:
                top.update()
                inspect(top)
            except Exception as exc:
                self.errors.append(exc)
            finally:
                if close and top.winfo_exists():
                    top.destroy()
        self.ui.root.after(50, callback)

    def assert_clean(self):
        self.assertEqual(self.errors, [])
        self.assertFalse(self.ui.root.winfo_children())
        self.assertFalse(self.ui.root.tk.call('after', 'info'))
        self.assertEqual(self.ui.status.trace_info(), [])

    def assert_inside(self, widget):
        parent = widget.master
        self.assertGreaterEqual(widget.winfo_x(), 0)
        self.assertGreaterEqual(widget.winfo_y(), 0)
        self.assertLessEqual(widget.winfo_x() + widget.winfo_width(), parent.winfo_width())
        self.assertLessEqual(widget.winfo_y() + widget.winfo_height(), parent.winfo_height())

    def test_catalog_resize_keeps_selection_and_original_value(self):
        choices = [(str(self.path.parent / f'{i}_{self.path.name}'), f'Perfil {i} | {self.path}')
                   for i in range(24)]
        def inspect(top):
            frame = next(w for w in top.winfo_children() if isinstance(w, tk.Frame))
            box = next(w for w in frame.winfo_children() if isinstance(w, tk.Listbox))
            box.selection_clear(0, 'end')
            box.selection_set(17)
            box.see(17)
            box.event_generate('<<ListboxSelect>>')
            for size in ('580x480', '960x700', '720x560'):
                top.geometry(size)
                top.update()
                self.ui.notice(f'Perfil creado: {self.path.with_suffix(".json")}')
                top.update()
                self.assertEqual(box.curselection(), (17,))
                self.assertEqual(box.size(), 24)
                measure = tkfont.Font(font=box.cget('font')).measure
                self.assertLessEqual(measure(box.get(17)), box.winfo_width())
                for child in top.winfo_children():
                    self.assert_inside(child)
            button = next(w for w in top.winfo_children()
                          if isinstance(w, ttk.Button) and w.cget('text') == 'Seleccionar')
            button.invoke()
        self.schedule(inspect)
        try:
            self.assertEqual(self.ui.choose('Perfiles', 'Seleccione un perfil', choices), choices[17][0])
        finally:
            self.assertEqual(self.errors, [])
        self.assert_clean()

    def test_small_catalog_uses_same_list_and_external_action(self):
        for choices, expected in (([(str(self.path), f'{self.path.name} | {self.path.parent}'),
                                    ('external', 'Buscar otro archivo…')], 'external'),
                                  ([('external', 'Buscar otro archivo…')], 'external')):
            def inspect(top):
                frame = next(w for w in top.winfo_children() if isinstance(w, tk.Frame))
                lists = [w for w in frame.winfo_children() if isinstance(w, tk.Listbox)]
                if lists:
                    lists[0].selection_clear(0, 'end')
                    lists[0].selection_set(1)
                    next(w for w in top.winfo_children() if isinstance(w, ttk.Button)
                         and w.cget('text') == 'Seleccionar').invoke()
                else:
                    next(w for w in frame.winfo_children() if isinstance(w, ttk.Button)).invoke()
            self.schedule(inspect)
            self.assertEqual(self.ui.choose('Videos', 'Seleccione', choices), expected)
            self.assert_clean()

    def test_settings_long_text_keeps_summary_and_actions_in_bounds(self):
        args = NS(mp4=True, video=self.path, zones=self.path.with_suffix('.json'),
                  camera_index=None, tracker='bytetrack', device='cpu', weights_dir=self.path.parent)
        def inspect(top):
            form = next(w for w in top.winfo_children() if isinstance(w, tk.Frame))
            for size in ('580x480', '960x700'):
                top.geometry(size)
                self.ui.notice('Perfil creado: ' + str(args.zones))
                top.update()
                for child in top.winfo_children():
                    self.assert_inside(child)
                for child in form.winfo_children():
                    self.assert_inside(child)
                actions = [w for w in top.winfo_children() if isinstance(w, ttk.Button)]
                self.assertLessEqual(abs(actions[0].winfo_width() - actions[1].winfo_width()), 1)
                self.assertEqual(actions[0].winfo_height(), actions[1].winfo_height())
                status = next(w for w in top.winfo_children()
                              if isinstance(w, CompactLabel) and w.variable is self.ui.status)
                self.assertLessEqual(form.winfo_y() + form.winfo_height(), status.winfo_y())
            entry = next(w for w in form.winfo_children() if isinstance(w, ttk.Entry)
                         and not isinstance(w, ttk.Combobox))
            self.assertEqual(entry.get(), str(args.weights_dir))
            next(w for w in top.winfo_children() if isinstance(w, ttk.Button)
                 and w.cget('text') == 'Iniciar visualizador').invoke()
        self.schedule(inspect)
        with patch.object(self.ui, 'busy', return_value=NS(devices=[NS(device='cpu')])), \
                patch('src.launcher_resources.valid_weights', return_value=True):
            try:
                self.assertEqual(self.ui.settings(args, NS(name='Perfil_' * 100)),
                                 ('bytetrack', 'cpu', args.weights_dir.resolve()))
            finally:
                self.assertEqual(self.errors, [])
        self.assert_clean()

    def test_tooltip_and_status_trace_are_disposed_with_window(self):
        def inspect(top):
            status = next(w for w in top.winfo_children()
                          if isinstance(w, CompactLabel) and w.variable is self.ui.status)
            self.ui.notice('Perfil creado: ' + str(self.path.with_suffix('.json')))
            status._show_detail(None)
            self.assertIsNotNone(status.tooltip)
            text = status.tooltip.winfo_children()[0].cget('text')
            self.assertIn(str(self.path.parent), text)
        self.schedule(inspect)
        with self.assertRaises(Cancelled):
            self.ui.menu()
        self.assert_clean()

