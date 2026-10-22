#!/usr/bin/env python3
"""Static compatibility checks against the actual uploaded Django source.

Usage: python scripts/check-backend-source.py ../tickethub/backend
No Django import, DB, HTTP call, or provider query is performed. A passing result
only establishes that the source contracts used by this frontend are present.
"""
from __future__ import annotations
import argparse
import ast
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend', type=Path, help='directory containing manage.py')
    root = parser.parse_args().backend.resolve()
    if not (root / 'manage.py').is_file():
        parser.error('Expected the backend directory containing manage.py')
    results: list[tuple[str, bool]] = []

    def source(path: str) -> str:
        return (root / path).read_text(encoding='utf-8-sig')

    def node(path: str, name: str) -> ast.ClassDef:
        return next(item for item in ast.parse(source(path)).body
                    if isinstance(item, ast.ClassDef) and item.name == name)

    def fields(path: str, name: str) -> set[str]:
        return {target.id for item in node(path, name).body if isinstance(item, ast.Assign)
                for target in item.targets if isinstance(target, ast.Name)}

    def check(label: str, ok: bool) -> None:
        results.append((label, ok))
        print(('PASS ' if ok else 'FAIL ') + label)

    def action(path: str, cls: str, name: str, method: str, detail: bool, route: str | None = None) -> None:
        fn = next((item for item in node(path, cls).body if isinstance(item, ast.FunctionDef) and item.name == name), None)
        matching = False
        if fn:
            for decorator in fn.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id == 'action':
                    kw = {key.arg: key.value for key in decorator.keywords}
                    actual = ast.literal_eval(kw['url_path']) if 'url_path' in kw else name
                    matching = (ast.literal_eval(kw['detail']) == detail
                                and method in ast.literal_eval(kw['methods']) and actual == (route or name))
        check(f'{cls}.{name}: {method.upper()} /{route or name}/ detail={detail}', matching)

    check('source router /staff/external-events/', "router.register('staff/external-events'" in source('external_events/urls.py'))
    check('plan router /staff/plans/', "router.register('staff/plans'" in source('venues/urls.py'))
    for name, route, detail in [('preview', 'preview', False), ('import_event', 'import', False), ('sync', 'sync', True)]:
        action('external_events/views.py', 'ExternalEventViewSet', name, 'post', detail, route)
    for name, method, route in [('preview', 'get', 'preview'), ('block_preview', 'post', 'block-preview'), ('csv_preview', 'post', 'csv-preview'), ('bulk_edit', 'post', 'bulk-edit'), ('image', 'post', 'image'), ('publish', 'post', 'publish'), ('clone_version', 'post', 'clone-version')]:
        action('venues/views.py', 'StaffPlanViewSet', name, method, True, route)
    action('events/views.py', 'StaffEventViewSet', 'image', 'post', True)
    check('import input strict fields', fields('external_events/serializers.py', 'ImportSerializer') == {'provider', 'url', 'mode', 'preview'})
    check('IMPORT_ONLY is the only import mode', "choices=['IMPORT_ONLY']" in source('external_events/serializers.py'))
    check('import requires IsAdmin', 'permission_classes = [IsAdmin]' in source('external_events/views.py'))
    check('IsAdmin verifies staff role', "request.user.staff_role == 'ADMIN'" in source('core/permissions.py'))
    check('staff session requires password backend', "users.backends.StaffPasswordBackend" in source('core/permissions.py'))
    check('bulk edit fields', fields('venues/editor_api.py', 'EditSerializer') == {'expected_version', 'create', 'update', 'delete'})
    check('block preview fields', fields('venues/editor_api.py', 'BlockSerializer') == {'sector','rows','seats_per_row','row_start','seat_start','seat_step','x','y','width','row_spacing','angle','curve','reverse_alternate','aisles_after'})
    check('CSV preview text field', fields('venues/editor_api.py', 'CSVSerializer') == {'text'})
    check('base image multipart fields', fields('core/serializers.py', 'ImageUploadSerializer') == {'image', 'rights_source', 'rights_confirmed'})
    for path, cls in [('events/views.py', 'EventImageSerializer'), ('venues/views.py', 'PlanImageSerializer')]:
        check(f'{cls} adds expected_version', fields(path, cls) == {'expected_version'})
    check('bulk version checked', 'check_version(plan, expected_version)' in source('venues/editor_services.py'))
    check('bulk transaction locks plan', 'select_for_update()' in source('venues/editor_services.py'))
    check('maximum 2000 changes', 'MAX_BATCH = 2000' in source('venues/geometry.py'))
    check('maximum 50000 seats', 'MAX_SEATS = 50000' in source('venues/geometry.py'))
    check('preview returns plan and seats', "Response({'plan':" in source('venues/views.py') and "'seats': SeatSerializer" in source('venues/views.py'))
    check('background optional for publication', 'if plan.image:' in source('venues/services.py') and "plan.status == 'DRAFT' and plan.seats.exists()" in source('venues/services.py'))
    failed = sum(not ok for _, ok in results)
    print(f'\n{len(results)} source contract checks; {failed} failed. NO live API/Django integration was tested.')
    return 1 if failed else 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, SyntaxError, StopIteration, ValueError) as exc:
        print(f'Cannot validate the supplied backend source: {exc}', file=sys.stderr)
        raise SystemExit(2) from exc
