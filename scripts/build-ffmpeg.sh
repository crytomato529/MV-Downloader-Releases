#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C TZ=UTC

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/.build"
PREFIX="$WORK/prefix"
LOGS="$WORK/logs"
INPUTS="$WORK/inputs"
SOURCE="$WORK/source"
STAGE="$WORK/package"
DIST="$ROOT/dist"
mkdir -p "$PREFIX" "$LOGS" "$INPUTS" "$SOURCE" "$STAGE/bin" "$STAGE/licenses" "$DIST/tools" "$DIST/source"
exec > >(tee "$LOGS/build.log") 2>&1
trap 'status=$?; printf "Build failed at line %s, exit %s\n" "$LINENO" "$status" >&2; exit "$status"' ERR
JOBS="${BUILD_JOBS:-$(nproc)}"
CC=x86_64-w64-mingw32-gcc-win32
CXX=x86_64-w64-mingw32-g++-win32
CROSS=x86_64-w64-mingw32-
command -v "$CC" >/dev/null
command -v "$CXX" >/dev/null

# Only these three verified source archives are fetched; no dependency autodetection.
python3 - "$ROOT/sources.lock.json" "$INPUTS" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
lock = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = pathlib.Path(sys.argv[2])
for source in lock['sources']:
    dest = out / source['file']
    if not dest.exists():
        req = urllib.request.Request(source['url'], headers={'User-Agent': 'MV-Downloader-public-tool-build'})
        with urllib.request.urlopen(req, timeout=120) as response:
            data = response.read(25 * 1024 * 1024 + 1)
        if len(data) > 25 * 1024 * 1024:
            raise RuntimeError('Unexpected source size: ' + source['name'])
        dest.write_bytes(data)
    data = dest.read_bytes()
    if len(data) != source['bytes'] or hashlib.sha256(data).hexdigest() != source['sha256']:
        raise RuntimeError('Source digest mismatch: ' + source['name'])
    print(source['name'], source['commit'], source['sha256'])
PY

for name in ffmpeg x264 dav1d; do
    file="$(python3 -c 'import json,sys; print(next(s["file"] for s in json.load(open(sys.argv[1]))["sources"] if s["name"] == sys.argv[2]))' "$ROOT/sources.lock.json" "$name")"
    mkdir -p "$SOURCE/$name"
    tar -xf "$INPUTS/$file" -C "$SOURCE/$name" --strip-components=1
done

# MinGW's native Windows threads avoid a libwinpthread DLL dependency.
export CC CXX
export AR="${CROSS}ar" RANLIB="${CROSS}ranlib" STRIP="${CROSS}strip"
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
cat > "$WORK/mingw64.meson" <<EOF
[binaries]
c = '$CC'
cpp = '$CXX'
ar = '${CROSS}ar'
strip = '${CROSS}strip'
windres = '${CROSS}windres'
pkgconfig = 'pkg-config'
[properties]
needs_exe_wrapper = true
[built-in options]
c_args = ['-O2']
c_link_args = ['-static', '-static-libgcc']
cpp_link_args = ['-static', '-static-libgcc', '-static-libstdc++']
[host_machine]
system = 'windows'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'
EOF

(
    cd "$SOURCE/x264"
    ./configure --prefix="$PREFIX" --host=x86_64-w64-mingw32 --cross-prefix="$CROSS" \
        --enable-static --enable-pic --disable-cli --disable-opencl \
        --disable-lavf --disable-swscale --disable-avs --disable-ffms --disable-gpac --disable-lsmash \
        --extra-ldflags='-static -static-libgcc' 2>&1 | tee "$LOGS/x264-configure.log"
    make -j"$JOBS" 2>&1 | tee "$LOGS/x264-make.log"
    make install 2>&1 | tee "$LOGS/x264-install.log"
)
cp "$SOURCE/x264/config.log" "$LOGS/x264-config.log"

meson setup "$WORK/dav1d-build" "$SOURCE/dav1d" --cross-file="$WORK/mingw64.meson" \
    --prefix="$PREFIX" --libdir=lib --buildtype=release --default-library=static \
    --wrap-mode=nodownload -Denable_tools=false -Denable_tests=false -Denable_examples=false \
    2>&1 | tee "$LOGS/dav1d-configure.log"
meson compile -C "$WORK/dav1d-build" -j "$JOBS" 2>&1 | tee "$LOGS/dav1d-make.log"
meson install -C "$WORK/dav1d-build" 2>&1 | tee "$LOGS/dav1d-install.log"
cp "$WORK/dav1d-build/meson-logs/meson-log.txt" "$LOGS/dav1d-meson.log"

(
    cd "$SOURCE/ffmpeg"
    ./configure --prefix="$PREFIX" --enable-cross-compile --target-os=mingw32 \
        --arch=x86_64 --cpu=x86-64 --cross-prefix="$CROSS" --cc="$CC" --cxx="$CXX" \
        --pkg-config=pkg-config --pkg-config-flags=--static \
        --extra-cflags="-I$PREFIX/include" --extra-ldflags="-L$PREFIX/lib -static -static-libgcc -static-libstdc++" \
        --disable-autodetect --enable-static --disable-shared --enable-gpl --enable-version3 \
        --enable-libx264 --enable-libdav1d --enable-w32threads \
        --disable-ffplay --disable-doc --disable-debug \
        --extra-version=mv-downloader-portable \
        2>&1 | tee "$LOGS/ffmpeg-configure.log"
    make -j"$JOBS" ffmpeg.exe ffprobe.exe 2>&1 | tee "$LOGS/ffmpeg-make.log"
)
cp "$SOURCE/ffmpeg/ffbuild/config.log" "$LOGS/ffmpeg-config.log"
cp "$SOURCE/ffmpeg/ffbuild/config.mak" "$LOGS/ffmpeg-config.mak"
cp "$SOURCE/ffmpeg/config.h" "$LOGS/ffmpeg-config.h"
cp "$SOURCE/ffmpeg/config_components.h" "$LOGS/ffmpeg-config_components.h"
cp "$SOURCE/ffmpeg/ffmpeg.exe" "$SOURCE/ffmpeg/ffprobe.exe" "$STAGE/bin/"
"${CROSS}strip" "$STAGE/bin/ffmpeg.exe" "$STAGE/bin/ffprobe.exe"

for file in COPYING.GPLv2 COPYING.GPLv3 COPYING.LGPLv2.1 COPYING.LGPLv3 LICENSE.md; do
    cp "$SOURCE/ffmpeg/$file" "$STAGE/licenses/FFmpeg-$file"
done
cp "$SOURCE/x264/COPYING" "$STAGE/licenses/x264-COPYING.txt"
cp "$SOURCE/dav1d/COPYING" "$STAGE/licenses/dav1d-COPYING.txt"
cp "$ROOT/licenses/THIRD_PARTY_NOTICES.md" "$STAGE/licenses/THIRD_PARTY_NOTICES.md"
cp "$ROOT/LICENSE" "$STAGE/licenses/build-materials-LICENSE.txt"
for package in gcc-mingw-w64-x86-64-win32 g++-mingw-w64-x86-64-win32 mingw-w64-common mingw-w64-x86-64-dev binutils-mingw-w64-x86-64; do
    if [[ -f "/usr/share/doc/$package/copyright" ]]; then
        cp "/usr/share/doc/$package/copyright" "$STAGE/licenses/toolchain-$package.txt"
    fi
done
dpkg-query -W -f='${binary:Package}\t${Version}\n' > "$LOGS/installed-build-packages.tsv"
"$CC" --version > "$LOGS/compiler-version.txt"
nasm -v > "$LOGS/nasm-version.txt"
meson --version > "$LOGS/meson-version.txt"

python3 - "$ROOT" "$WORK" "$STAGE" "$DIST" <<'PY'
import hashlib, json, os, pathlib, re, subprocess, sys, zipfile
root, work, stage, dist = map(pathlib.Path, sys.argv[1:])
allowed = {'advapi32.dll','avicap32.dll','bcrypt.dll','comdlg32.dll','crypt32.dll','d3d11.dll','d3d12.dll','dwmapi.dll','dxgi.dll','gdi32.dll','kernel32.dll','mf.dll','mfplat.dll','msvcrt.dll','ntdll.dll','ole32.dll','oleaut32.dll','psapi.dll','secur32.dll','setupapi.dll','shell32.dll','shlwapi.dll','user32.dll','vfw32.dll','winmm.dll','ws2_32.dll','wtsapi32.dll'}
tools = []
for binary in sorted((stage/'bin').glob('*.exe')):
    dump = subprocess.check_output(['x86_64-w64-mingw32-objdump','-p',str(binary)], text=True)
    (work/'logs'/f'{binary.stem}-pe-imports.txt').write_text(dump)
    imports = sorted(set(re.findall(r'DLL Name:\s*(\S+)', dump, flags=re.I)))
    unexpected = [name for name in imports if name.lower() not in allowed and not name.lower().startswith(('api-ms-win-', 'ext-ms-win-'))]
    if not imports or unexpected:
        raise RuntimeError(f'Unexpected/non-system DLL dependency in {binary.name}: {unexpected}')
    if 'pei-x86-64' not in dump:
        raise RuntimeError('Not a Windows x64 PE: ' + binary.name)
    data = binary.read_bytes()
    tools.append(dict(file=binary.name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), imported_system_dlls=imports))
config = (work/'logs'/'ffmpeg-config_components.h').read_text()
required = ['LIBX264_ENCODER','AAC_ENCODER','AAC_DECODER','H264_DECODER','VP9_DECODER','LIBDAV1D_DECODER','OPUS_DECODER','SCALE_FILTER','MOV_DEMUXER','MATROSKA_DEMUXER','MP4_MUXER']
for name in required:
    if not re.search(r'^#define CONFIG_' + name + r' 1$', config, re.M):
        raise RuntimeError('Required built-in capability missing: ' + name)
manifest = dict(schema=1, ffmpeg_version='8.1.1', platform='windows-x86_64', license='GPL-3.0-or-later', third_party_static_libraries=['x264','dav1d'], dependency_autodetection=False, external_non_system_dlls=[], sources=json.loads((root/'sources.lock.json').read_text())['sources'], tools=tools, build_run_url=f'https://github.com/{os.environ.get("GITHUB_REPOSITORY", "crytomato529/MV-Downloader-Releases")}/actions/runs/{os.environ.get("GITHUB_RUN_ID", "local")}', build_scripts_revision=os.environ.get('GITHUB_SHA','local'))
payload = json.dumps(manifest, indent=2) + '\n'
(stage/'build-manifest.json').write_text(payload)
(dist/'tools'/'build-manifest.json').write_text(payload)
(dist/'source'/'build-manifest.json').write_text(payload)
with zipfile.ZipFile(dist/'tools'/'ffmpeg-tools-win64.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for path in sorted(stage.rglob('*')):
        if path.is_file(): archive.write(path, path.relative_to(stage).as_posix())
with zipfile.ZipFile(dist/'source'/'ffmpeg-tools-corresponding-source.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for folder, prefix in [(work/'inputs','inputs'),(work/'logs','logs'),(stage/'licenses','licenses'),(root/'scripts','scripts'),(root/'.github'/'workflows','workflows')]:
        for path in sorted(folder.rglob('*')):
            if path.is_file(): archive.write(path, prefix+'/'+path.relative_to(folder).as_posix())
    for path in [root/'sources.lock.json',root/'README.md',root/'LICENSE',work/'mingw64.meson',stage/'build-manifest.json']:
        archive.write(path, path.name)
checksums=[]
for folder in ['tools','source']:
    for path in sorted((dist/folder).glob('*.zip')):
        checksums.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name)
for folder in ['tools','source']:
    (dist/folder/'SHA256SUMS').write_text('\n'.join(checksums)+'\n')
print(payload)
PY

printf 'Built binaries and complete source inputs in %s\n' "$DIST"
