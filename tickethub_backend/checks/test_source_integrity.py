"""Static checks only. These cannot certify ORM migrations, locks, or HTTP behaviour."""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / 'backend'
APPS = ['core','venues','events','tickets','orders','ticket_requests','payments','analytics','users','external_events','promotions']

def field_assignments(cls):
    result = {}
    for node in cls.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            if node.value.func.attr.endswith('Field') or node.value.func.attr == 'ForeignKey':
                result[node.targets[0].id] = node.value
    return result

def migration_operations():
    for path in sorted(B.glob('*/migrations/[0-9]*.py')):
        tree = ast.parse(path.read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Migration')
        for node in cls.body:
            if isinstance(node, ast.Assign) and node.targets[0].id == 'operations':
                for operation in node.value.elts:
                    yield path, operation.func.attr, {k.arg: k.value for k in operation.keywords}

class SourceIntegrityTests(unittest.TestCase):
    def test_migration_directories_are_packages(self):
        for app in APPS:
            with self.subTest(app=app):
                self.assertTrue((B / app / 'migrations' / '__init__.py').is_file(),
                                'A missing __init__.py can hide migrations from Django.')

    def test_all_python_files_parse(self):
        for path in ROOT.rglob('*.py'):
            with self.subTest(file=str(path.relative_to(ROOT))): ast.parse(path.read_text(), filename=str(path))

    def test_model_field_names_are_present_in_migrations(self):
        declared = {}
        common = {'id','created_at','updated_at'}
        for app in APPS:
            for cls in ast.parse((B/app/'models.py').read_text()).body:
                if not isinstance(cls, ast.ClassDef) or cls.name in ['User', 'Record']: continue
                fields = set(field_assignments(cls))
                if any(ast.unparse(base) == 'Record' for base in cls.bases): fields |= common
                declared[(app,cls.name.lower())] = fields
        migrated = {}
        for path, op, kw in migration_operations():
            app = path.parent.parent.name
            if op == 'CreateModel':
                name = ast.literal_eval(kw['name']).lower()
                migrated.setdefault((app,name),set()).update(ast.literal_eval(row.elts[0]) for row in kw['fields'].elts)
            elif op == 'AddField':
                migrated.setdefault((app,ast.literal_eval(kw['model_name'])),set()).add(ast.literal_eval(kw['name']))
        for key, names in declared.items():
            with self.subTest(model=key): self.assertEqual(names, migrated[key])

    def test_migration_dependencies_have_no_local_cycle(self):
        nodes = {}
        for path in sorted(B.glob('*/migrations/[0-9]*.py')):
            tree = ast.parse(path.read_text())
            cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Migration')
            deps = next(n.value for n in cls.body if isinstance(n,ast.Assign) and n.targets[0].id == 'dependencies')
            nodes[(path.parent.parent.name,path.stem)] = [ast.literal_eval(n) for n in deps.elts if isinstance(n,ast.Tuple)]
        active, done = set(), set()
        def visit(key):
            self.assertNotIn(key,active, f'Migration cycle: {key}')
            if key in done: return
            active.add(key)
            for dep in nodes[key]:
                if dep[0] in APPS:
                    self.assertIn(dep,nodes)
                    visit(dep)
            active.remove(key); done.add(key)
        for key in nodes: visit(key)

    def test_database_constraint_names_unique(self):
        # A later migration may deliberately replace a constraint under the same
        # name (venues.0005 does so). Check live names, not historical additions.
        active = {}
        for path, op, kw in migration_operations():
            if op == 'RemoveConstraint':
                name = ast.literal_eval(kw['name'])
                self.assertIn(name, active, f'Removing unknown constraint in {path}')
                del active[name]
            elif op == 'AddConstraint':
                name = next(ast.literal_eval(k.value) for k in kw['constraint'].keywords if k.arg == 'name')
                self.assertNotIn(name, active, f'Duplicate active constraint {name} in {path}')
                active[name] = str(path)

    def test_postgresql_has_no_sqlite_fallback(self):
        settings = (B/'config/settings/base.py').read_text()
        self.assertIn('django.db.backends.postgresql',settings)
        self.assertNotIn('django.db.backends.sqlite',settings)

    def test_no_critical_unimplemented_functions(self):
        for path in B.glob('*/services.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Raise) and node.exc:
                    self.assertNotIn('NotImplementedError', ast.unparse(node))
                if isinstance(node,ast.FunctionDef):
                    self.assertFalse(len(node.body)==1 and isinstance(node.body[0],ast.Pass), str(path)+':'+node.name)

    def test_no_wildcard_fields_in_customer_serializer_files(self):
        for app in ['users','events','venues','tickets','orders','ticket_requests']:
            source = (B/app/'serializers.py').read_text()
            self.assertNotIn('fields = "__all__"',source)
            self.assertNotIn("fields = '__all__'",source)

    def test_no_prohibited_dependencies(self):
        source = (B/'requirements.txt').read_text().lower()
        for name in ['celery','redis','rabbitmq','django-otp','pytest']:
            self.assertNotIn(name,source)

    def test_no_fan_id_document_model_fields(self):
        for app in APPS:
            tree = ast.parse((B/app/'models.py').read_text())
            for cls in tree.body:
                if isinstance(cls,ast.ClassDef):
                    for field in field_assignments(cls):
                        self.assertFalse(any(word in field for word in ['passport','snils','gosuslugi']), field)

    def test_migration_primary_keys_disable_serialization(self):
        for path, operation, kw in migration_operations():
            if operation != 'CreateModel':
                continue
            for row in kw['fields'].elts:
                field = row.elts[1]
                if not isinstance(field, ast.Call):
                    continue
                fields = {k.arg: k.value for k in field.keywords}
                if fields.get('primary_key') is not None and ast.literal_eval(fields['primary_key']):
                    with self.subTest(file=str(path), field=ast.literal_eval(row.elts[0])):
                        self.assertIn('serialize', fields)
                        self.assertFalse(ast.literal_eval(fields['serialize']))
