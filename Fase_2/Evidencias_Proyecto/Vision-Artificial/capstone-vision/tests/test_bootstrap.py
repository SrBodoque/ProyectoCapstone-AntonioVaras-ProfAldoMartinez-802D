import os,subprocess,sys,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import instalar_limpia as boot
from video_test_support import temporary_directory

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=temporary_directory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.p=patch.object(boot,'ROOT',self.root);self.p.start();self.addCleanup(self.p.stop)
        env=patch.dict(os.environ,{'LOCALAPPDATA':str(self.root/'userdata')});env.start();self.addCleanup(env.stop)
    def test_batch_spaces_and_other_working_directory(self):
        folder=self.root/'folder with spaces';folder.mkdir()
        actual=Path(boot.__file__).with_name('Iniciar_LimpIA.bat')
        (folder/actual.name).write_bytes(actual.read_bytes())
        (folder/'instalar_limpia.py').write_text('import os;print(os.getcwd())')
        r=subprocess.run(['cmd','/d','/c','call',str(folder/actual.name),'--check'],cwd=self.root,capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn(str(folder),r.stdout)
    def test_candidates_priority_and_no_git_dependency(self):
        boot.save_state({'python':str(self.root/'external.exe')})
        result=boot.candidates(self.root/'configured.exe')
        self.assertEqual(result[:3],[self.root/'.venv/Scripts/python.exe',self.root/'configured.exe',self.root/'external.exe'])
    def test_broken_preferences_are_safe(self):
        self.assertEqual(boot.read(self.root/'absent'),{})
    def test_reject_existing_install_target(self):
        with self.assertRaises(ValueError),patch.object(boot,'run') as run:boot.install(sys.executable,'cpu',self.root)
        run.assert_not_called()
    def test_new_install_requires_consent(self):
        with patch.object(boot,'ask',return_value=False),patch.object(boot,'run') as run,self.assertRaises(boot.Cancelled):boot.install(sys.executable,'cpu',self.root/'new')
        run.assert_not_called()
    def test_cpu_gpu_commands_constrain_exact_variant(self):
        for variant,suffix in [('cpu','cpu'),('gpu','cu132')]:
            target=self.root/variant
            def run(argv,**kw):
                if 'venv' in argv:target.mkdir()
                return MagicMock(returncode=0)
            with patch.object(boot,'ask',return_value=True),patch.object(boot,'gpu_ready',return_value=True),patch.object(boot,'run',side_effect=run) as mocked:boot.install(sys.executable,variant,target)
            commands=mocked.call_args_list
            self.assertIn('https://download.pytorch.org/whl/'+suffix,commands[1].args[0])
            self.assertIn('-c',commands[2].args[0]);self.assertIn('torch==2.14.0+'+suffix,(target/'limpia-torch-constraints.txt').read_text())
    def test_gpu_detection_success_and_failure(self):
        with patch.object(boot,'run',return_value=MagicMock(stdout='RTX, 610.88')):self.assertIn('RTX',boot.hardware())
        for error in [FileNotFoundError(),subprocess.TimeoutExpired('x',1)]:
            with patch.object(boot,'run',side_effect=error):self.assertEqual(boot.hardware(),'')
    def test_probe_checks_imports_versions_device_and_nms(self):
        with patch.object(boot,'run',return_value=MagicMock(stdout='ok')) as run:boot.probe('python','cuda:0',full=True,weights='yolo26n.pt')
        code=run.call_args_list[0].args[0][3]
        for check in ['torch.cuda.is_available','torchvision.ops.nms','struct.calcsize','YOLO','predict']:self.assertIn(check,code)
        self.assertEqual(run.call_args_list[1].args[0],['python','-m','pip','check'])
    def test_existing_model_matching_and_mismatching_hash(self):
        model=self.root/'yolo26n.pt';model.write_bytes(b'fixture')
        with patch.object(boot,'MODEL_HASH',boot.digest(model)):self.assertEqual(boot.weights('python'),model)
        with patch.object(boot,'ask',return_value=True):self.assertEqual(boot.weights('python'),model)
        with patch.object(boot,'ask',return_value=False),patch('builtins.input',return_value=''),self.assertRaises(boot.Cancelled):boot.weights('python')
    def test_missing_weights_download_declined(self):
        with patch('builtins.input',side_effect=['d','n']),patch.object(boot,'urlopen') as download,self.assertRaises(boot.Cancelled):boot.weights('python')
        download.assert_not_called()
    def test_download_verified_and_network_failure(self):
        import io
        data=b'fixture'
        with patch.object(boot,'MODEL_HASH',__import__('hashlib').sha256(data).hexdigest()),patch('builtins.input',side_effect=['d','s']),patch.object(boot,'urlopen',return_value=io.BytesIO(data)):
            self.assertEqual(boot.weights('python').read_bytes(),data)
        for error in [OSError('network'),ValueError('bad file')]:
            with patch.object(boot,'urlopen',side_effect=error),patch('builtins.input',side_effect=['d','s']),self.assertRaises((OSError,ValueError)):boot.weights('python')
    def test_clean_clone_cancel_leaves_no_success_state(self):
        with patch('builtins.input',return_value=''),patch.object(boot,'candidates',return_value=[]):self.assertEqual(boot.main(['--device','cpu']),0)
        self.assertFalse(boot.state_path().exists())
    def test_reuse_and_second_start_never_install(self):
        exe=self.root/'python.exe';exe.write_bytes(b'fixture');model=self.root/'yolo26n.pt';model.write_bytes(b'fixture')
        with patch.object(boot,'candidates',return_value=[exe]),patch.object(boot,'probe') as probe,patch.object(boot,'weights',return_value=model),patch.object(boot,'ask',return_value=True),patch.object(boot,'install') as install,patch.object(boot,'run',return_value=MagicMock(returncode=0)):
            self.assertEqual(boot.main(['--device','cpu']),0);self.assertEqual(boot.main(['--device','cpu']),0)
            install.assert_not_called();self.assertEqual(sum('weights' in c.kwargs for c in probe.call_args_list),1)
    def test_incompatible_environment_does_not_install_or_record_success(self):
        exe=self.root/'bad.exe';exe.write_bytes(b'bad')
        with patch.object(boot,'candidates',return_value=[exe]),patch.object(boot,'probe',side_effect=subprocess.CalledProcessError(1,'probe')),patch('builtins.input',return_value=''):
            self.assertEqual(boot.main(['--device','cuda:0']),0)
        self.assertFalse(boot.state_path().exists())

    def test_driver_compatibility_gate(self):
        for version,expected in [('13.2',True),('13.3',True),('12.6',False),('unknown',False)]:
            with patch.object(boot,'run',return_value=MagicMock(stdout='CUDA Version: '+version)):self.assertEqual(boot.gpu_ready(),expected)
        with patch.object(boot,'gpu_ready',return_value=False),self.assertRaises(ValueError):boot.install(sys.executable,'gpu',self.root/'new')
