"""Isolated automation tests. Story, voice, renderer and publication are mocked; no real provider call."""
import json, pathlib, sys, tempfile, unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from hstudio import publication_automation as PA

class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.tmp.name); (self.root/'projects').mkdir()
        self.patches=[patch.object(PA.paths,'CONFIG',str(self.root)),patch.object(PA.paths,'PROJECTS',str(self.root/'projects')),
                      patch.object(PA.P,'load_settings',return_value={'gemini_api_key':'fixture','elevenlabs_api_key':'fixture'}),
                      patch.object(PA,'_launch'),patch.object(PA.OC,'plan',return_value={'stages':[]}),patch.object(PA,'voices',return_value={'voices':[{'voice_id':'fixture-voice-id','name':'Voix de test'}]})]
        self.started=[p.start() for p in self.patches]
        self.input={'premise':'Une porte inconnue','provider':'gemini','duration':60,'aspects':['9:16'],'language':'fr','voiceId':'fixture-voice-id'}
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()
    def test_requires_explicit_generation_consent(self):
        with self.assertRaises(ValueError): PA.start('request-12345678',self.input,{})
        self.started[3].assert_not_called()
    def test_duplicate_order_does_not_generate_twice(self):
        a=PA.start('request-12345678',self.input,{'generationConfirmed':True});b=PA.start('request-12345678',self.input,{'generationConfirmed':True})
        self.assertEqual(a['id'],b['id']);self.started[3].assert_called_once()
    def test_mock_story_is_not_accepted_for_a_real_order(self):
        with self.assertRaises(ValueError): PA.start('request-12345678',{**self.input,'provider':'mock'},{'generationConfirmed':True})
        self.started[3].assert_not_called()
    def test_cancel_before_a_late_start_remains_cancelled(self):
        PA.cancel('request-12345678');result=PA.start('request-12345678',self.input,{'generationConfirmed':True})
        self.assertEqual(result['status'],'cancelled');self.started[3].assert_not_called()
    def test_restart_holds_an_uncertain_voice_call(self):
        PA.start('request-12345678',self.input,{'generationConfirmed':True});PA._patch('request-12345678',status='running',phase='voice')
        PA._initialized.discard(str(self.root/'publication-orders.sqlite'))
        self.assertEqual(PA.view('request-12345678')['status'],'reconciliation_required')
        with self.assertRaises(ValueError): PA.resume('request-12345678')
    def project(self,quality=True):
        pr=Mock();pr.slug='film';pr.meta={'voice_mode':'local','story':{'generator':'gemini'}}
        pr.read_json.return_value={'encoded':{'ok':quality},'issues':[]}
        return pr
    def test_complete_native_pipeline_delivers_only_validated_assets(self):
        PA.start('request-12345678',self.input,{'generationConfirmed':True});pr=self.project()
        with patch.object(PA,'_project',return_value=pr),patch.object(PA.OC,'project_from_brief',return_value=(pr,Mock())) as writer,patch.object(PA.OC,'run',return_value={'complete':True,'renders':{'9:16':['film.mp4']}}) as render,patch.object(PA.PB,'prepare',return_value={'asset':{'id':'asset'}}) as deliver:
            PA._execute('request-12345678',Mock())
            self.assertEqual(writer.call_args.args[0]['provider'],'gemini');self.assertEqual(writer.call_args.args[0]['voice_mode'],'')
            self.assertNotIn('frames',render.call_args.args[2]);deliver.assert_called_once()
            result=PA.view('request-12345678');self.assertEqual(result['status'],'completed');self.assertEqual(result['assets'],['asset'])
    def test_failed_quality_prevents_delivery(self):
        PA.start('request-12345678',self.input,{'generationConfirmed':True});pr=self.project(False)
        with patch.object(PA,'_project',return_value=pr),patch.object(PA.OC,'project_from_brief',return_value=(pr,Mock())),patch.object(PA.OC,'run',return_value={'complete':True,'renders':{'9:16':['film.mp4']}}),patch.object(PA.PB,'prepare') as deliver:
            with self.assertRaises(ValueError): PA._execute('request-12345678',Mock())
            deliver.assert_not_called();self.assertEqual(PA.view('request-12345678')['status'],'blocked')
    def test_draft_voice_never_passes_the_delivery_gate(self):
        pr=self.project();pr.meta['voice_mode']='draft'
        with self.assertRaises(ValueError): PA._publishable(pr,['9:16'])
    def test_vertex_uses_the_configured_project_model_and_explicit_adc(self):
        from hstudio.director import providers
        from types import SimpleNamespace
        client=Mock();client.models.generate_content.return_value=SimpleNamespace(text='{"story":"ok"}',usage_metadata=None)
        credentials=Mock()
        with patch('google.genai.Client') as factory,patch('google.auth.default',return_value=(credentials,'ignored-project')):
            factory.return_value.__enter__.return_value=client
            text=providers.call_gemini_vertex({'vertex_project':'test-project','vertex_location':'global','vertex_model':'configured-model'},'system','prompt',log=lambda _:None)
            self.assertEqual(text,'{"story":"ok"}');self.assertEqual(factory.call_args.kwargs['credentials'],credentials)
            self.assertTrue(factory.call_args.kwargs['vertexai']);self.assertEqual(factory.call_args.kwargs['project'],'test-project')
            self.assertEqual(client.models.generate_content.call_args.kwargs['model'],'configured-model')
    def test_reconcile_existing_voice_does_not_repeat_a_provider_call(self):
        PA.start('request-12345678',self.input,{'generationConfirmed':True});PA._patch('request-12345678',project='film',status='reconciliation_required',phase='voice');pr=self.project();pr.exists.return_value=True
        with patch.object(PA,'_project',return_value=pr),patch.object(PA.jobs,'get',return_value=None),patch('hstudio.tts.ffprobe_duration',return_value=15):
            self.assertEqual(PA.reconcile('request-12345678')['status'],'interrupted');self.started[3].assert_called_once()

if __name__=='__main__':unittest.main()
