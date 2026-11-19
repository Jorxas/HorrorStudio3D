"""Publication bridge checks, isolated files and mocked transport. No provider or video generation."""
import os, sys, json, tempfile, pathlib, importlib, unittest
from unittest.mock import patch, Mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from hstudio import publication_bridge as bridge

class PublicationTests(unittest.TestCase):
    def test_saving_preferences_keeps_credentials_out_of_the_tracked_template(self):
        from hstudio import pipeline as P
        with tempfile.TemporaryDirectory() as tmp:
            template=pathlib.Path(tmp)/'settings.json';template.write_text('{"quality":"standard"}')
            with patch.object(P.paths,'CONFIG',tmp),patch.object(P.paths,'SETTINGS_FILE',str(template)),patch.object(P,'load_env_file'),patch.dict(os.environ,{'ELEVENLABS_API_KEY':'fixture-private-key'}):
                P.save_settings({'quality':'max'})
                self.assertEqual(template.read_text(),'{"quality":"standard"}')
                private=pathlib.Path(tmp)/'settings.local.json';self.assertTrue(private.exists())
                self.assertEqual(json.loads(private.read_text())['elevenlabs_api_key'],'fixture-private-key')

    def test_default_ports_do_not_use_pps(self):
        from hstudio.__main__ import main
        for argv, expected in [(['hstudio'], 8767), (['hstudio', 'web', '--no-browser'], 8767), (['hstudio', 'web', '--no-browser', '--port', '9876'], 9876)]:
            with patch.object(sys, 'argv', argv), patch('uvicorn.run') as run, patch('threading.Timer'):
                main()
                self.assertEqual(run.call_args.kwargs['port'], expected)

    def test_missing_configuration_is_honest(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bridge.paths, 'CONFIG', tmp):
            self.assertEqual(bridge.status(), {'enabled': False, 'publicUrl': None})

    def test_prepare_preserves_caption_and_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bridge.paths, 'CONFIG', tmp):
            root = pathlib.Path(tmp); (root/'renders').mkdir(); (root/'renders'/'film.mp4').write_bytes(b'video')
            (root/'publication.json').write_text(json.dumps({'enabled': True, 'apiKey': 'test-private-key', 'apiUrl': 'http://127.0.0.1:1', 'publicUrl': 'https://example.test/publication/'}))
            project = Mock(); project.slug = 'film'; project.meta = {'name': 'Mon film'}; project.p.side_effect = lambda *parts: str(root.joinpath(*parts)); project.read_json.return_value = {'platforms': {'tiktok': {'caption': 'La légende fidèle'}}}
            response = Mock(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False); response.read.return_value = b'{"asset":{"id":"prepared"}}'
            with patch.object(bridge.urllib.request, 'urlopen', return_value=response) as urlopen:
                result = bridge.prepare(project, 'film.mp4', 'fr')
                req = urlopen.call_args.args[0]; payload = json.loads(req.data)
                self.assertTrue(req.full_url.endswith('/api/assets')); self.assertEqual(payload['caption'], 'La légende fidèle'); self.assertFalse(result['published']); self.assertNotIn('test-private-key', json.dumps(result))

    def test_outside_project_render_is_refused_before_transport(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bridge.paths, 'CONFIG', tmp):
            root = pathlib.Path(tmp); (root/'renders').mkdir(); (root/'outside.mp4').write_bytes(b'video'); (root/'publication.json').write_text(json.dumps({'enabled': True, 'apiKey': 'key', 'apiUrl': 'http://127.0.0.1:1', 'publicUrl': 'https://example.test'}))
            project = Mock(); project.p.side_effect=lambda *parts: str(root.joinpath(*parts))
            with patch.object(bridge.urllib.request, 'urlopen') as transport:
                with self.assertRaises(ValueError): bridge.prepare(project, '../outside.mp4')
                transport.assert_not_called()

if __name__ == '__main__': unittest.main()
