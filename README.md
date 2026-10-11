# MV Downloader Releases

This repository holds public download information and the build materials for separately distributed third-party tools. Application source code and user data are not included.

## Pinned FFmpeg tools

The manual **Build portable FFmpeg tools** workflow builds `ffmpeg.exe` and `ffprobe.exe` for Windows x64 from the exact archives in `sources.lock.json`:

- FFmpeg 8.1.1, upstream commit `239f2c733de417201d7ad3b3b8b0d9b63285b2b1`.
- x264 commit `0480cb05fa188d37ae87e8f4fd8f1aea3711f7ee`.
- dav1d 1.5.3, upstream commit `b546257f770768b2c88258c533da38b91a06f737`.

Source archives have fixed SHA-256 digests and are checked before extraction. The x264 archive is served by the GitHub mirror; its pinned commit was checked against the canonical VideoLAN repository. FFmpeg and dav1d are served by their upstream release site or project mirror.

External-library autodetection is disabled. Only x264 and dav1d are enabled as external libraries, linked statically. Native FFmpeg H264, VP9, AAC and Opus decoders, local-file containers, scale filters, and H264/AAC output remain enabled. AV1 software decoding uses dav1d. Networking and ffplay are disabled because the application supplies local media files.

The build rejects non-system DLL dependencies. A separate Windows job starts both tools, checks required codecs, and encodes and trims synthetic media. The application's real-media acceptance tests run separately before a software release.

## Build locally on Ubuntu 24.04

Install the packages listed in `.github/workflows/build-tools.yml`, then run:

```sh
bash scripts/build-ffmpeg.sh
```

Outputs:

- `ffmpeg-win64-tools`: Windows binary ZIP, build manifest and SHA256SUMS.
- `ffmpeg-corresponding-source`: complete actual source-input ZIP, build manifest and SHA256SUMS.
- `ffmpeg-windows-verification`: real Windows smoke-test report.

The source ZIP contains the three original input archives in full, all build and verification scripts, pinned-source manifest, configuration output, configure/make logs, toolchain versions and license notices. It does not contain application source or user media.

GitHub Actions artifacts expire and require a signed-in account to download. They are build outputs for maintainers, not the public corresponding-source download location. Before distributing a software package containing these binaries, attach the binary ZIP **and its matching corresponding-source ZIP** to the same public GitHub Release, include their SHA-256 values, and place clear source-download instructions beside the software download and inside its third-party notices. Keep the matching source available while the binary download is offered. No written three-year source offer is used by these materials.

The software release page and update JSON will be added after the complete portable package is verified. Publishing these build materials does not publish the application source.

## Licensing

The FFmpeg executables built here are GPL-3.0-or-later (`--enable-gpl --enable-version3`). x264 is GPL-2.0-or-later; dav1d is BSD-2-Clause. License texts from the exact downloaded sources and MinGW toolchain notices are included in both output ZIPs. Build materials written for this repository are MIT licensed; this does not change the licenses of any upstream source or executable. See `licenses/THIRD_PARTY_NOTICES.md`.

Native networking and Windows Schannel TLS remain enabled for HTTPS/HLS fallback. External dependency autodetection remains disabled; no external TLS library is linked.
