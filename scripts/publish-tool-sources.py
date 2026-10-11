#!/usr/bin/env python3
"""Upload verified source ZIPs to a draft release; never publish or change feeds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import zipfile

REPOSITORY = 'crytomato529/MV-Downloader-Releases'
ARTIFACTS = {'ffmpeg': ('ffmpeg-corresponding-source', 'ffmpeg-tools-corresponding-source.zip'),
             'ytdlp': ('yt-dlp-corresponding-source', 'yt-dlp-minimal-corresponding-source.zip')}
RUN_PATHS = {'ffmpeg': '.github/workflows/build-tools.yml',
             'ytdlp': '.github/workflows/build-downloader.yml'}
PROCESS_FLAGS = 0x08000000 if os.name == 'nt' else 0


def require(condition, message):
    if not condition:
        raise ValueError(message)


def gh_json(arguments):
    completed = subprocess.run(['gh', *arguments], capture_output=True, text=True, timeout=30,
                               creationflags=PROCESS_FLAGS)
    if completed.returncode:
        raise RuntimeError('GitHub validation request failed; exit=' + str(completed.returncode))
    return json.loads(completed.stdout)


def validate_inputs(environment):
    require(environment.get('GITHUB_REPOSITORY') == REPOSITORY, 'Only the trusted repository may publish these sources')
    tag = environment.get('RELEASE_TAG', '')
    match = re.fullmatch(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-preview)?', tag)
    require(match is not None and all(int(part) <= 65535 for part in match.groups()), 'Invalid release tag')
    inputs = {'tag': tag}
    for kind in ARTIFACTS:
        run = environment.get(kind.upper() + '_RUN', '')
        digest = environment.get(kind.upper() + '_SOURCE_SHA256', '')
        require(re.fullmatch(r'[1-9][0-9]{0,19}', run) is not None, 'Invalid build run number: ' + kind)
        require(re.fullmatch(r'[a-f0-9]{64}', digest) is not None, 'Invalid expected source SHA256: ' + kind)
        inputs[kind] = {'run': run, 'sha256': digest}
    return inputs


def validate_run(kind, expected):
    run = gh_json(['api', f"repos/{REPOSITORY}/actions/runs/{expected['run']}"])
    require(run.get('id') == int(expected['run']) and run.get('status') == 'completed'
            and run.get('conclusion') == 'success' and run.get('event') == 'workflow_dispatch'
            and run.get('path') == RUN_PATHS[kind]
            and run.get('head_repository', {}).get('full_name') == REPOSITORY
            and run.get('repository', {}).get('full_name') == REPOSITORY
            and re.fullmatch(r'[a-f0-9]{40}', run.get('head_sha', '')) is not None,
            'Expected successful trusted build run is required: ' + kind)
    inventory = gh_json(['api', f"repos/{REPOSITORY}/actions/runs/{expected['run']}/artifacts"])
    matches = [item for item in inventory.get('artifacts', []) if item.get('name') == ARTIFACTS[kind][0]]
    require(len(matches) == 1 and matches[0].get('expired') is False,
            'The exact source artifact is missing, ambiguous or expired: ' + kind)
    artifact = matches[0]
    require(artifact.get('workflow_run', {}).get('id') == run['id']
            and artifact.get('workflow_run', {}).get('head_sha') == run['head_sha'],
            'Source artifact does not match the successful build revision')
    return run


def draft_release(tag, filenames):
    release = gh_json(['api', f'repos/{REPOSITORY}/releases/tags/{tag}'])
    require(release.get('tag_name') == tag and release.get('draft') is True,
            'Target release must already exist as a draft')
    require(not set(filenames).intersection(asset.get('name') for asset in release.get('assets', [])),
            'Refusing to overwrite an existing release source asset')
    return release


def validate_source_archive(kind, directory, expected, run):
    directory = Path(directory).resolve()
    filename = ARTIFACTS[kind][1]
    path = directory / filename
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size < 2 * 1024**3,
            'Expected source ZIP is missing or outside the asset size limit')
    with path.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    require(digest == expected['sha256'], 'Source ZIP does not match the locally approved SHA256: ' + kind)
    with zipfile.ZipFile(path) as packed:
        seen, total = set(), 0
        for member in packed.infolist():
            name = member.orig_filename
            parts = name.rstrip('/').split('/')
            require(name and not name.startswith('/') and '\\' not in name
                    and not stat.S_ISLNK(member.external_attr >> 16)
                    and all(part not in ('', '.', '..') and part.rstrip(' .') == part
                            and re.search(r'[<>:"|?*\x00-\x1f]', part) is None
                            and re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I) is None
                            for part in parts), 'Unsafe source ZIP path')
            normalized = name.rstrip('/').casefold()
            require(normalized not in seen, 'Ambiguous source ZIP path')
            seen.add(normalized)
            total += member.file_size
            require(total < 2 * 1024**3, 'Unexpected source ZIP expanded size')
        require(packed.testzip() is None, 'Source ZIP CRC verification failed')
        manifest = json.loads(packed.read('build-manifest.json'))
        declared = json.loads((directory / 'build-manifest.json').read_text('utf-8'))
        require(manifest == declared, 'Source ZIP and artifact provenance disagree')
        require(manifest.get('build_run_url') == f"https://github.com/{REPOSITORY}/actions/runs/{expected['run']}"
                and manifest.get('build_scripts_revision') == run['head_sha'],
                'Source ZIP provenance does not match the successful run')
    return path, {'file': filename, 'bytes': path.stat().st_size, 'sha256': digest,
                  'run': expected['run'], 'revision': run['head_sha'], 'path_and_crc': 'passed'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('preflight', 'upload'))
    parser.add_argument('--artifacts', type=Path, default=Path('artifacts'))
    args = parser.parse_args()
    inputs = validate_inputs(os.environ)
    runs = {kind: validate_run(kind, inputs[kind]) for kind in ARTIFACTS}
    filenames = [item[1] for item in ARTIFACTS.values()]
    draft_release(inputs['tag'], filenames)
    if args.mode == 'preflight':
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            for kind in ARTIFACTS:
                output.write(f"{kind}_run={inputs[kind]['run']}\n")
        print('Both successful build runs and the target draft release passed preflight.')
        return
    checked = [validate_source_archive(kind, args.artifacts / kind, inputs[kind], runs[kind])
               for kind in ARTIFACTS]
    # Validate both complete assets before upload; check draft status once more.
    draft_release(inputs['tag'], filenames)
    result = subprocess.run(['gh', 'release', 'upload', inputs['tag'], *(str(path) for path, _ in checked),
                             '--repo', REPOSITORY], timeout=180, creationflags=PROCESS_FLAGS)
    if result.returncode:
        raise RuntimeError('Source asset upload failed; draft remains unpublished; inspect assets before retry')
    report = {'uploaded_to_draft': inputs['tag'], 'repository': REPOSITORY,
              'sources': [entry for _, entry in checked], 'release_published': False, 'feed_changed': False}
    Path('source-upload-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Verified source ZIPs uploaded to the existing draft; release and feeds remain unchanged.')


if __name__ == '__main__':
    main()
