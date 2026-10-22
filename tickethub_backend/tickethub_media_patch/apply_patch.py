"""Apply only this patch, preserving local edits outside named functions. No database access."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid


def raw_hash(data): return hashlib.sha256(data).hexdigest()
def text_hash(text): return raw_hash(text.replace('\r\n','\n').encode())
def node_hash(node): return raw_hash(ast.dump(node,include_attributes=False).encode())


def nodes(text):
    result={}
    def visit(body,prefix=''):
        for node in body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                result[prefix+node.name]=node
                if isinstance(node,ast.ClassDef):visit(node.body,prefix+node.name+'.')
    visit(ast.parse(text).body);return result


def replace_nodes(current, payload, changes):
    oldnodes,newnodes=nodes(current),nodes(payload)
    oldlines,newlines=current.splitlines(keepends=True),payload.splitlines(keepends=True)
    replacements=[]
    for entry in changes:
        name=entry['name']
        if name not in oldnodes or name not in newnodes:
            raise ValueError(f'Не найден {name}.')
        old,new=oldnodes[name],newnodes[name]
        if node_hash(old)==node_hash(new):continue
        if node_hash(old) not in entry['accepted'] and not entry.get('allow_test_edit'):
            raise ValueError(f'{name} содержит неизвестные изменения; нужна ручная сверка.')
        start=min([old.lineno]+[n.lineno for n in old.decorator_list])-1
        new_start=min([new.lineno]+[n.lineno for n in new.decorator_list])-1
        replacements.append((start,old.end_lineno,''.join(newlines[new_start:new.end_lineno])))
    for start,end,text in sorted(replacements,reverse=True):oldlines[start:end]=[text]
    result=''.join(oldlines);ast.parse(result)
    return result


def main():
    parser=argparse.ArgumentParser(description='Media + complete geometry patch for Tickethub after PortalBilet v2.')
    parser.add_argument('--project',required=True)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    root=Path(args.project).resolve();patch=Path(__file__).resolve().parent
    if not (root/'backend/manage.py').is_file():parser.error('Нужен корень проекта с backend/manage.py.')
    if not (root/'backend/venues/migrations/0004_external_layout.py').exists():
        parser.error('Сначала установите предыдущий PortalBilet v2 patch.')
    competing=[p.name for p in (root/'backend/venues/migrations').glob('0005*.py') if p.name!='0005_all_geometry_seats.py']
    if competing:parser.error('Уже есть другая venues/0005: '+', '.join(competing)+'. Ничего не изменено.')
    manifest=json.loads((patch/'manifest.json').read_text(encoding='utf-8'))
    pending,conflicts=[],[]
    for entry in manifest['files']:
        rel=entry['path'];target=(root/rel).resolve();source=(patch/'payload'/rel).resolve()
        if not target.is_relative_to(root) or not source.is_relative_to((patch/'payload').resolve()):
            parser.error('Небезопасный путь в manifest.')
        if not source.is_file() or raw_hash(source.read_bytes())!=entry['sha256']:
            parser.error(f'Повреждён payload: {rel}')
        if target.exists() and not target.is_file():conflicts.append(rel+': не обычный файл');continue
        old=target.read_bytes() if target.exists() else None
        new=source.read_bytes()
        if old==new:continue
        try:
            if entry['mode']=='nodes':
                if old is None:raise ValueError('Исходный файл отсутствует.')
                current=old.decode('utf-8-sig').replace('\r\n','\n')
                new=replace_nodes(current,new.decode('utf-8'),entry['nodes']).encode('utf-8')
            elif entry['mode']=='replacements':
                if old is None:raise ValueError('Файл конфигурации отсутствует.')
                current=old.decode('utf-8-sig').replace('\r\n','\n')
                for change in entry['replacements']:
                    if change['new'] in current:continue
                    if current.count(change['old'])!=1:raise ValueError('Изменён нужный блок конфигурации; нужна ручная сверка.')
                    current=current.replace(change['old'],change['new'],1)
                new=current.encode('utf-8')
            else:
                digest=text_hash(old.decode('utf-8-sig')) if old is not None else None
                if old is not None and digest==text_hash(new.decode('utf-8-sig')):continue
                if digest not in entry['accepted']:raise ValueError('Есть локальные изменения; перезапись запрещена.')
            if new==old:continue
            if target.suffix=='.py':ast.parse(new.decode('utf-8'),filename=rel)
            pending.append((target,new,old))
        except (ValueError,SyntaxError,UnicodeError) as exc:conflicts.append(f'{rel}: {exc}')
    if conflicts:
        print('STOP. Ничего не изменено:\n'+'\n'.join(conflicts));return 2
    print(f'Compatible. Files to apply: {len(pending)}.')
    print('Сохраняются .env, compose.yaml, events/models.py и существующая events/0003.')
    print('Production: точечно увеличиваются лимит Nginx и /tmp в compose.prod.yaml.')
    for target,_,_ in pending:print('  '+str(target.relative_to(root)))
    if args.check or not pending:return 0
    backup=root/'backups'/('media-layout-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    backup.mkdir(parents=True)
    completed=[]
    try:
        for target,new,old in pending:
            if (target.read_bytes() if target.exists() else None)!=old:raise RuntimeError(f'Файл изменился во время установки: {target}')
            relative=target.relative_to(root)
            if old is not None:
                saved=backup/relative;saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(old)
            target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name(target.name+'.patch-'+uuid.uuid4().hex)
            try:
                temporary.write_bytes(new)
                if target.exists():shutil.copymode(target,temporary)
                os.replace(temporary,target)
                completed.append((target,old))
            finally:temporary.unlink(missing_ok=True)
        (backup/'patch-record.json').write_text(json.dumps({'patch':manifest['id'],
            'files':[{'path':str(t.relative_to(root)),'previously_existed':o is not None} for t,_,o in pending]},indent=2))
    except Exception as exc:
        for target,old in reversed(completed):
            if old is None:target.unlink(missing_ok=True)
            else:target.write_bytes(old)
        print(f'Установка не завершена; замены отменены: {exc}',file=sys.stderr);return 3
    print(f'Applied {len(completed)} files. Backup: {backup}')
    print('Выполните проверки миграций, migrate, тесты и backfill_layout_seats из README. База данных не изменялась установщиком.')
    return 0


if __name__=='__main__':raise SystemExit(main())
