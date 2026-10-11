#!/usr/bin/env python3
"""Build a pinned yt-dlp with standard Python networking and bundled EJS only.

No application source or user data is an input. Every downloaded archive/wheel
is verified before it is used and is included in the corresponding source ZIP.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import ssl
import sqlite3
import subprocess
import sys
import tarfile
import urllib.request
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.build' / 'downloader'
INPUTS, LOGS = WORK / 'inputs', WORK / 'logs'
DIST = ROOT / 'dist' / 'downloader'
LOCK = json.loads((ROOT / 'downloader.lock.json').read_text(encoding='utf-8'))
EXCLUDED = [
    'brotli', 'brotlicffi', 'certifi', 'curl_cffi', 'mutagen', 'requests',
    'urllib3', 'websockets', 'Cryptodome', 'Crypto', 'secretstorage', 'cffi',
    'cryptography', 'jeepney', 'keyring', 'tkinter', 'pip', 'setuptools',
    'pkg_resources', 'packaging',
]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(args, cwd=None, name='command'):
    args = [str(a) for a in args]
    print(name, flush=True)
    p = subprocess.run(args, cwd=cwd or ROOT, text=True, encoding='utf-8',
                       errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       creationflags=0x08000000 if os.name == 'nt' else 0,
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    (LOGS / (name + '.log')).write_text(p.stdout, encoding='utf-8')
    if p.returncode:
        print(p.stdout[-15000:], flush=True)
        raise RuntimeError(f'{name} failed, exit {p.returncode}')
    return p.stdout


def fetch(item):
    target = INPUTS / item['file']
    if target.name != item['file']:
        raise ValueError('Unsafe input filename')
    if not target.exists():
        req = urllib.request.Request(item['url'], headers={'User-Agent': 'public-downloader-build'})
        with urllib.request.urlopen(req, timeout=180) as response, target.open('wb') as out:
            shutil.copyfileobj(response, out)
    if target.stat().st_size != item['bytes'] or digest(target) != item['sha256']:
        raise RuntimeError('Source digest mismatch: ' + item['file'])
    return item['file']


def unpack(item, target):
    stage = WORK / ('unpack-' + target.name)
    stage.mkdir()
    with tarfile.open(INPUTS / item['file']) as archive:
        archive.extractall(stage, filter='data')
    roots = list(stage.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise RuntimeError('Expected one archive root: ' + item['file'])
    roots[0].rename(target)
    stage.rmdir()


def zip_tree(root, target):
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for p in sorted(root.rglob('*')):
            if p.is_file():
                archive.write(p, p.relative_to(root).as_posix())


def collect_notices(py, source, output):
    output.mkdir(parents=True)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('Full Windows Python LICENSE.txt is missing')
    shutil.copy2(python_license, output / 'Python-Windows-LICENSE.txt')
    shutil.copy2(source / 'LICENSE', output / 'yt-dlp-Unlicense.txt')
    script = r'''
import importlib.metadata as m, json, pathlib, sys
out=pathlib.Path(sys.argv[1]); records=[]
for name in ['PyInstaller','pyinstaller-hooks-contrib','altgraph','packaging','pefile','pywin32-ctypes','yt-dlp-ejs']:
    d=m.distribution(name)
    for f in d.files or []:
        if any(x.lower().startswith(('license','copying','notice')) for x in f.parts):
            p=pathlib.Path(d.locate_file(f))
            if p.is_file():
                target=out/(name+'-'+str(f).replace('/','_').replace('\\','_'))
                target.write_bytes(p.read_bytes()); records.append({'distribution':name,'version':d.version,'file':target.name})
import yt_dlp_ejs
for p in pathlib.Path(yt_dlp_ejs.__file__).parent.rglob('*.js'):
    text=p.read_text(encoding='utf-8')
    if text.startswith('/*') and 'license' in text[:3000].lower():
        (out/('EJS-'+p.name+'-licenses.txt')).write_text(text.split('*/',1)[0]+'*/\n',encoding='utf-8')
print(json.dumps(records))
'''
    records = json.loads(run([py, '-c', script, output], name='collect-license-texts'))
    if not any(r['distribution'] == 'PyInstaller' for r in records):
        raise RuntimeError('PyInstaller full license was not collected')
    if not (output / 'EJS-lib.min.js-licenses.txt').is_file():
        raise RuntimeError('Bundled JavaScript licenses are missing')
    for item in LOCK['sources']:
        if item['name'] in ('yt-dlp', 'CPython', 'meriyah', 'astring'):
            continue
        with tarfile.open(INPUTS / item['file']) as archive:
            for member in archive.getmembers():
                base = Path(member.name).name.lower()
                if member.isfile() and member.size < 500_000 and base.startswith(('license', 'copying', 'notice')):
                    data = archive.extractfile(member).read()
                    name = item['name'] + '-' + member.name.replace('/', '_')
                    (output / name).write_bytes(data)
    notice = (
        'MINIMAL YT-DLP WINDOWS BUILD\n'
        'yt-dlp and EJS source: Unlicense. EJS JavaScript: Meriyah ISC; Astring MIT.\n'
        'Python: PSF license and the complete Windows Python third-party notices below.\n'
        'PyInstaller: GPLv2-or-later with the bootloader distribution exception.\n'
        'PyInstaller build dependencies are retained as source inputs; optional yt-dlp\n'
        'extensions including mutagen and curl_cffi are excluded and not distributed.\n'
        'This tool notice does not change the license of an independent calling application.\n'
        'See the corresponding source archive for exact sources, wheels, hashes and script.\n\n'
    )
    for p in sorted(output.iterdir()):
        notice += '\n' + '=' * 72 + '\n' + p.name + '\n' + '=' * 72 + '\n'
        notice += p.read_text(encoding='utf-8', errors='replace') + '\n'
    (output / 'THIRD_PARTY_LICENSES.txt').write_text(notice, encoding='utf-8')
    shutil.copy2(output / 'THIRD_PARTY_LICENSES.txt', source / 'THIRD_PARTY_LICENSES.txt')
    return records


def inspect_archive(py, exe):
    code = r'''
import json, sys
from PyInstaller.archive.readers import CArchiveReader
a=CArchiveReader(sys.argv[1]); pyz=next(n for n in a.toc if n.endswith('.pyz'))
p=a.open_embedded_archive(pyz)
print(json.dumps({'embedded_files':sorted(a.toc),'modules':sorted(p.toc)}))
'''
    result = json.loads(run([py, '-c', code, exe], name='inspect-frozen-archive'))
    forbidden = [m for m in result['modules'] if any(m == x or m.startswith(x + '.') for x in EXCLUDED)]
    if forbidden:
        raise RuntimeError('Excluded optional modules embedded: ' + ','.join(forbidden))
    for js in ('core.min.js', 'lib.min.js'):
        if not any(n.replace('\\', '/').endswith('/' + js) and 'yt_dlp_ejs' in n for n in result['embedded_files']):
            raise RuntimeError('Missing embedded EJS solver: ' + js)
    if not any(m == 'yt_dlp_ejs' for m in result['modules']):
        raise RuntimeError('Missing EJS Python module')
    write_json(LOGS / 'frozen-inventory.json', result)
    return result


def main():
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('Requires Windows x64')
    if platform.python_version() != LOCK['python_version']:
        raise RuntimeError('Wrong Python version: ' + platform.python_version())
    for p in (INPUTS, LOGS, DIST / 'tools', DIST / 'source'):
        p.mkdir(parents=True, exist_ok=True)
    inputs = list(LOCK['sources']) + [p[k] for p in LOCK['packages'] for k in ('source', 'wheel')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for name in pool.map(fetch, inputs):
            print('Verified ' + name, flush=True)
    source = WORK / 'yt-dlp-source'
    unpack(next(s for s in LOCK['sources'] if s['name'] == 'yt-dlp'), source)
    venv_dir = WORK / 'venv'
    venv.create(venv_dir, with_pip=True, system_site_packages=False)
    py = venv_dir / 'Scripts' / 'python.exe'
    wheels = [INPUTS / p['wheel']['file'] for p in LOCK['packages']]
    run([py, '-m', 'pip', 'install', '--no-index', '--no-deps', '--disable-pip-version-check', *wheels], name='install-verified-build-wheels')
    package = WORK / 'package'
    (package / 'bin').mkdir(parents=True)
    notices = collect_notices(py, source, package / 'licenses')
    run([py, 'devscripts/set-variant.py', 'mv-downloader-minimal', '-M',
         'Download updated MV Downloader portable package from its release page.'], cwd=source, name='set-official-build-variant')
    run([py, 'devscripts/make_lazy_extractors.py'], cwd=source, name='make-lazy-extractors')
    options = ['--clean', '--collect-all=yt_dlp_ejs'] + ['--exclude-module=' + x for x in EXCLUDED]
    run([py, '-m', 'bundle.pyinstaller', *options], cwd=source, name='pyinstaller-build')
    exe = source / 'dist' / 'yt-dlp.exe'
    version = run([exe, '--ignore-config', '--version'], name='binary-version').strip()
    if version != LOCK['yt_dlp_version']:
        raise RuntimeError('Unexpected downloader version: ' + version)
    listing = run([exe, '--ignore-config', '--no-remote-components', '--verbose', '--list-extractors'], name='binary-offline-extractors')
    if 'youtube' not in listing.lower():
        raise RuntimeError('YouTube extractor missing')
    inventory = inspect_archive(py, exe)
    node = run(['node', '--version'], name='node-version').strip()
    if node != 'v24.15.0':
        raise RuntimeError('Wrong JavaScript test runtime: ' + node)
    ejs_script = r'''import json,pathlib,yt_dlp_ejs;print(json.dumps([str(p) for p in pathlib.Path(yt_dlp_ejs.__file__).parent.rglob('*.js')]))'''
    for i, js in enumerate(json.loads(run([py, '-c', ejs_script], name='locate-ejs-solvers'))):
        run(['node', '--check', js], name=f'check-ejs-javascript-{i}')
    if 'OpenSSL 3.5.9' not in ssl.OPENSSL_VERSION or sqlite3.sqlite_version != '3.50.4':
        raise RuntimeError(f'Python dependency source mismatch: {ssl.OPENSSL_VERSION}, SQLite {sqlite3.sqlite_version}')
    revision = run(['git', 'rev-parse', 'HEAD'], name='build-revision').strip()
    run_url = 'https://github.com/' + os.environ['GITHUB_REPOSITORY'] + '/actions/runs/' + os.environ['GITHUB_RUN_ID']
    binary = package / 'bin' / 'yt-dlp.exe'
    shutil.copy2(exe, binary)
    manifest = {
        'schema': 1, 'passed': True, 'yt_dlp_version': version, 'variant': 'mv-downloader-minimal',
        'python_version': platform.python_version(), 'openssl_version': ssl.OPENSSL_VERSION,
        'sqlite_version': sqlite3.sqlite_version, 'ejs_version': '0.8.0',
        'pyinstaller_version': '6.22.3', 'build_scripts_revision': revision,
        'build_run_url': run_url, 'sha256': digest(binary), 'bytes': binary.stat().st_size,
        'license': 'Unlicense; Python PSF-2.0 and bundled notices; ISC; MIT; PyInstaller bootloader exception',
        'excluded_optional_modules': EXCLUDED, 'embedded_module_count': len(inventory['modules']),
        'license_files': notices, 'source_input_count': len(inputs),
        'verification': ['fixed input SHA256', 'Windows x64 binary starts', 'version', 'YouTube extractor',
                         'optional extensions absent', 'EJS Python and both JavaScript solvers embedded',
                         'Node 24 syntax checks', 'Python bundled dependency sources matched'],
    }
    write_json(package / 'build-manifest.json', manifest)
    source_package = WORK / 'corresponding-source'
    source_package.mkdir()
    shutil.copytree(INPUTS, source_package / 'inputs')
    shutil.copytree(LOGS, source_package / 'logs')
    shutil.copytree(package / 'licenses', source_package / 'licenses')
    for name in ('downloader.lock.json', 'LICENSE'):
        shutil.copy2(ROOT / name, source_package / name)
    (source_package / 'scripts').mkdir()
    (source_package / '.github' / 'workflows').mkdir(parents=True)
    shutil.copy2(ROOT / 'scripts' / 'build-downloader.py', source_package / 'scripts' / 'build-downloader.py')
    shutil.copy2(ROOT / '.github' / 'workflows' / 'build-downloader.yml', source_package / '.github' / 'workflows' / 'build-downloader.yml')
    write_json(source_package / 'build-manifest.json', manifest)
    (source_package / 'README.txt').write_text(
        'Exact source inputs for the minimal yt-dlp Windows x64 executable.\n'
        'All source archives and actual wheels are included under inputs/.\n'
        'Includes CPython and all seven Windows CPython source dependencies.\n'
        'Unpack and run scripts/build-downloader.py on Windows x64 with Python 3.13.16\n'
        'and Node 24.15.0. To avoid network input fetching, copy inputs/ into\n'
        '.build/downloader/inputs/ first. Every input is SHA256 checked before use.\n'
        'The upstream yt-dlp source is used with its official set-variant.py and\n'
        'make_lazy_extractors.py; its THIRD_PARTY_LICENSES.txt is replaced with\n'
        'the notice for this actual minimal build. No optional downloader extension\n'
        'is bundled. No main application source or user material is included.\n'
        'Logs include the actual build options and frozen file/module inventory.\n', encoding='utf-8')
    binary_zip = DIST / 'tools' / 'yt-dlp-minimal-win64.zip'
    source_zip = DIST / 'source' / 'yt-dlp-minimal-corresponding-source.zip'
    zip_tree(package, binary_zip)
    zip_tree(source_package, source_zip)
    for target in (DIST / 'tools', DIST / 'source'):
        write_json(target / 'build-manifest.json', manifest)
        (target / 'SHA256SUMS.txt').write_text(
            f'{digest(binary_zip)}  {binary_zip.name}\n{digest(source_zip)}  {source_zip.name}\n'
            f'{digest(binary)}  yt-dlp.exe\n', encoding='ascii')
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == '__main__':
    main()
