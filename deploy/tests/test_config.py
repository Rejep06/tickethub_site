from pathlib import Path
import os, shutil, subprocess, sys, tempfile, unittest
try:
    import yaml
except ImportError:
    yaml = None
ROOT=Path(__file__).resolve().parents[2]
class EnvGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); (self.root/'deploy').mkdir()
        shutil.copy(ROOT/'deploy/create_production_env.py',self.root/'deploy')
        shutil.copy(ROOT/'.env.production.example',self.root)
    def run_generator(self, domain):
        return subprocess.run([sys.executable,str(self.root/'deploy/create_production_env.py'),domain],capture_output=True,text=True)
    def test_valid_domain_random_secrets_private_permissions(self):
        r=self.run_generator('tickets.example.com'); self.assertEqual(r.returncode,0,r.stderr)
        p=self.root/'.env.production'; values=dict(line.split('=',1) for line in p.read_text().splitlines() if '=' in line and not line.startswith('#'))
        self.assertEqual(values['PUBLIC_HOST'],'tickets.example.com')
        self.assertNotIn('GENERATE_WITH_SCRIPT',p.read_text())
        self.assertEqual(len(values['DJANGO_SECRET_KEY']),96)
        self.assertNotEqual(values['POSTGRES_PASSWORD'],values['POSTGRES_ADMIN_PASSWORD'])
        self.assertEqual(p.stat().st_mode&0o777,0o600)
    def test_unicode_hostname_converts_to_punycode(self):
        r=self.run_generator('билеты.рф'); self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('PUBLIC_HOST=xn--90aiim0b4c.xn--p1ai',(self.root/'.env.production').read_text())
    def test_existing_configuration_not_overwritten(self):
        p=self.root/'.env.production'; p.write_text('existing-config')
        self.assertNotEqual(self.run_generator('tickets.example.com').returncode,0)
        self.assertEqual(p.read_text(),'existing-config')
    def test_invalid_hostnames_rejected(self):
        for host in ['https://example.com','localhost','127.0.0.1','a.example.com:8080','*.example.com','example.com/path','example.com\nBAD=x']:
            with self.subTest(host=host): self.assertNotEqual(self.run_generator(host).returncode,0)
        self.assertFalse((self.root/'.env.production').exists())
@unittest.skipIf(yaml is None, "Optional structure checks need PyYAML; env tests use standard library only.")
class ComposeStructureTests(unittest.TestCase):
    def setUp(self): self.c=yaml.safe_load((ROOT/'compose.production.yml').read_text())
    def test_application_and_database_ports_are_not_published(self):
        for name in ['db','backend','frontend','scheduler']: self.assertNotIn('ports',self.c['services'][name])
    def test_only_gateway_exposes_http_https(self):
        self.assertEqual(self.c['services']['nginx']['ports'],['80:80','443:443'])
        self.assertIn('bootstrap',self.c['services']['nginx-bootstrap']['profiles'])
    def test_backend_data_uses_named_volumes(self):
        self.assertIn('media_data:/app/media',self.c['services']['backend']['volumes'])
        self.assertIn('postgres_data:/var/lib/postgresql/data',self.c['services']['db']['volumes'])
    def test_test_database_has_different_project_and_no_live_volume(self):
        c=yaml.safe_load((ROOT/'compose.check.yml').read_text())
        self.assertNotEqual(c['name'],self.c['name']); self.assertNotIn('volumes',c['services']['testdb'])
        self.assertIn('/var/lib/postgresql/data',c['services']['testdb']['tmpfs'])
    def test_server_side_host_is_not_public_variable(self):
        e=self.c['services']['frontend']['environment']; self.assertEqual(e['API_INTERNAL_HOST'],'${PUBLIC_HOST}')
        self.assertNotIn('NEXT_PUBLIC_API_INTERNAL_HOST',e)
    def test_default_public_forms_are_disabled(self):
        e=self.c['services']['backend']['environment']
        for key in ['PUBLIC_FORMS_ENABLED','ORDER_INTAKE_ENABLED','CLIENT_ANALYTICS_ENABLED']:
            self.assertEqual(e[key],'${'+key+':-false}')
    def test_bootstrap_and_application_passwords_differ(self):
        self.assertNotEqual(self.c['services']['db']['environment']['POSTGRES_PASSWORD'],self.c['services']['backend']['environment']['POSTGRES_PASSWORD'])
    def test_deployment_references_existing_build_files(self):
        for name in ['backend','frontend']:
            build=self.c['services'][name]['build']; self.assertTrue((ROOT/build['context']/build.get('dockerfile','Dockerfile')).is_file())
if __name__=='__main__': unittest.main(verbosity=2)
