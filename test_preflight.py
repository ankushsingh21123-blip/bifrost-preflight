import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from preflight import scan, safe_path

BASE = {'providers': {'openai': {'keys': [{'name':'local-reference','value':'env.OPENAI_API_KEY','models':['gpt-4o-mini'],'weight':1.0}]}}, 'client': {'disable_content_logging':True, 'enforce_auth_on_inference':True}, 'governance': {'auth_config': {'is_enabled':True, 'admin_username':'local-admin','admin_password':'env.BIFROST_ADMIN_PASSWORD'}}, 'config_store': {'enabled': False}}

def codes(c, hosted=False): return {x['code'] for x in scan(c,hosted)['findings']}
class Checks(unittest.TestCase):
    def test_reference_config_schema(self): self.assertEqual(codes(BASE),set())
    def test_hosted_explicit_auth(self): self.assertEqual(codes(BASE,True),set())
    def test_inline_provider(self):
        c=copy.deepcopy(BASE);c['providers']['openai']['keys'][0]['value']='fictional-api-value'
        self.assertIn('INLINE_PROVIDER_KEY',codes(c))
        self.assertNotIn('fictional-api-value',json.dumps(scan(c)))
    def test_unknown_provider_name_never_echoed(self):
        c={'providers':{'fictional-sensitive-label':{'keys':[{'value':'fictional-sensitive-value'}]}}}
        out=json.dumps(scan(c));self.assertNotIn('fictional-sensitive',out)
    def test_object_env_reference(self):
        # Reference helper supports typed references, but published schema may disallow them at a particular field.
        from preflight import is_reference
        self.assertTrue(is_reference({'type':'env','env_var':'TEST'}))
        self.assertFalse(is_reference({'type':'env','env_var':''}))
    def test_vault_ref(self):
        c=copy.deepcopy(BASE);c['providers']['openai']['keys'][0]['value']='vault.provider/key'
        self.assertNotIn('INLINE_PROVIDER_KEY',codes(c))
    def test_empty_env_not_reference(self):
        c=copy.deepcopy(BASE);c['providers']['openai']['keys'][0]['value']='env.'
        self.assertIn('INLINE_PROVIDER_KEY',codes(c))
    def test_content_logs(self):
        c={'client':{'enable_logging':True}}
        self.assertIn('CONTENT_LOGGING',codes(c))
    def test_content_disabled(self):
        self.assertNotIn('CONTENT_LOGGING',codes({'client':{'enable_logging':True,'disable_content_logging':True}}))
    def test_hidden_storage(self):
        self.assertIn('HIDDEN_CONTENT_RETENTION',codes({'client':{'disable_content_logging':True,'retain_content_in_object_storage':True}}))
    def test_override(self):
        self.assertIn('REQUEST_STORAGE_OVERRIDE',codes({'client':{'allow_per_request_content_storage_override':True}}))
    def test_header_case(self):
        self.assertIn('SENSITIVE_HEADER_LOGGING',codes({'client':{'logging_headers':['AUTHORIZATION']}}))
    def test_harmless_header(self):
        self.assertNotIn('SENSITIVE_HEADER_LOGGING',codes({'client':{'logging_headers':['x-request-id']}}))
    def test_direct_keys(self):
        self.assertIn('DIRECT_KEYS',codes({'client':{'allow_direct_keys':True}}))
    def test_missing_hosted_auth(self):
        self.assertIn('DASHBOARD_AUTH_UNCONFIRMED',codes({},True))
        self.assertIn('INFERENCE_AUTH_UNCONFIRMED',codes({},True))
    def test_local_not_hosted(self):
        self.assertNotIn('DASHBOARD_AUTH_UNCONFIRMED',codes({}))
    def test_legacy_auth_supported(self):
        c=copy.deepcopy(BASE);c['auth_config']=c.pop('governance')['auth_config']
        self.assertNotIn('DASHBOARD_AUTH_UNCONFIRMED',codes(c,True))
    def test_no_plain_admin(self):
        c=copy.deepcopy(BASE);c['governance']['auth_config']['admin_password']='fictional-password'
        self.assertIn('INLINE_ADMIN_PASSWORD',codes(c))
        self.assertNotIn('fictional-password',json.dumps(scan(c)))
    def test_route_bypass(self):
        self.assertIn('AUTH_BYPASS_ROUTES',codes({'client':{'whitelisted_routes':['/v1/chat/completions']}},True))
    def test_schema_error_redacted(self):
        c={'client':{'enforce_auth_on_inference':'fictional-secret-in-invalid-type'}}
        r=scan(c);self.assertIn('SCHEMA',codes(c));self.assertNotIn('fictional-secret',json.dumps(r))
    def test_governance_bypass_overrides_client_true(self):
        c=copy.deepcopy(BASE);c['governance']['auth_config']['disable_auth_on_inference']=True
        self.assertIn('INFERENCE_AUTH_BYPASS',codes(c,True))
    def test_governance_bypass_local_also_flagged(self):
        c=copy.deepcopy(BASE);c['governance']['auth_config']['disable_auth_on_inference']=True
        self.assertIn('INFERENCE_AUTH_BYPASS',codes(c))
    def test_legacy_bypass(self):
        c=copy.deepcopy(BASE);c['auth_config']={'disable_auth_on_inference':True}
        self.assertIn('LEGACY_INFERENCE_AUTH_BYPASS',codes(c,True))
    def test_legacy_only_bypass(self):
        c=copy.deepcopy(BASE);c['auth_config']=c.pop('governance')['auth_config'];c['auth_config']['disable_auth_on_inference']=True
        self.assertIn('LEGACY_INFERENCE_AUTH_BYPASS',codes(c,True))
        report=scan(c,True)
        self.assertNotIn('INFERENCE_AUTH_BYPASS',{x['code'] for x in report['findings']})
        bypass=[x for x in report['findings'] if x['code']=='LEGACY_INFERENCE_AUTH_BYPASS']
        self.assertEqual(len(bypass),1)
        self.assertEqual(bypass[0]['location'],'/auth_config/disable_auth_on_inference')
    def test_override_false_does_not_flag_bypass(self):
        c=copy.deepcopy(BASE);c['governance']['auth_config']['disable_auth_on_inference']=False
        self.assertNotIn('INFERENCE_AUTH_BYPASS',codes(c,True))
    def test_governance_and_legacy_bypasses_both_reported(self):
        c=copy.deepcopy(BASE);c['governance']['auth_config']['disable_auth_on_inference']=True;c['auth_config']={'disable_auth_on_inference':True}
        self.assertTrue({'INFERENCE_AUTH_BYPASS','LEGACY_INFERENCE_AUTH_BYPASS'} <= codes(c,True))
    def test_array_config(self):self.assertIn('SCHEMA',codes([]))
    def test_malformed_provider(self):self.assertIn('SCHEMA',codes({'providers':[]}))
    def test_malformed_client(self):self.assertIn('SCHEMA',codes({'client':[]}))
    def test_sanitize_path(self):self.assertEqual(safe_path(['providers','secret-label','keys',0,'value']),'/providers/*/keys/0/value')
    def test_no_mutation(self):
        c=copy.deepcopy(BASE);before=copy.deepcopy(c);scan(c);self.assertEqual(c,before)
    def test_cli_invalid_no_echo(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text('{"fictional-secret":')
            r=subprocess.run([sys.executable,'preflight.py',str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,2);self.assertNotIn('fictional-secret',r.stdout+r.stderr)
    def test_cli_duplicate_no_echo(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text('{"key":"fictional-secret","key":2}')
            r=subprocess.run([sys.executable,'preflight.py',str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,2);self.assertNotIn('fictional-secret',r.stdout+r.stderr)
    def test_cli_status(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'safe.json';p.write_text(json.dumps(BASE))
            r=subprocess.run([sys.executable,'preflight.py',str(p),'--hosted'],capture_output=True,text=True)
            self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['status'],'no_findings_in_checked_rules')

if __name__=='__main__':unittest.main(verbosity=2)
