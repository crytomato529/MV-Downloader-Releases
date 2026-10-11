# Third-party tool notices

These notices apply to the FFmpeg/ffprobe tools built by this repository. They do not assign a license to the separate MV Downloader application or its other bundled components.

| Component | Exact source | License |
| --- | --- | --- |
| FFmpeg | 8.1.1, `239f2c733de417201d7ad3b3b8b0d9b63285b2b1` | GPL-3.0-or-later for this `--enable-gpl --enable-version3` build |
| x264 | `0480cb05fa188d37ae87e8f4fd8f1aea3711f7ee` | GPL-2.0-or-later |
| dav1d | 1.5.3, `b546257f770768b2c88258c533da38b91a06f737` | BSD-2-Clause |
| MinGW-w64/GCC runtime portions | Actual versions recorded in build logs | Upstream notices and applicable GCC Runtime Library Exception; included toolchain copyright files |

Copyrights remain with the upstream authors. Complete, unmodified license texts are copied from the exact source inputs into `licenses/` in both build output ZIPs. FFmpeg's source licensing details are in its `LICENSE.md`. The full three input source archives, fixed hashes, compilation scripts, configuration and build logs are provided in `ffmpeg-tools-corresponding-source.zip` for the corresponding binary build.

Public distributors must publish that matching source ZIP and binary provenance beside the downloadable software package, with clear source links inside the software package. GitHub's automatically generated repository “Source code” archive contains these build scripts only and is not the complete FFmpeg source ZIP.

Official sources:

- FFmpeg: https://ffmpeg.org/releases/ and https://www.ffmpeg.org/legal.html
- x264: https://code.videolan.org/videolan/x264 (pinned archive mirror: https://github.com/mirror/x264)
- dav1d: https://code.videolan.org/videolan/dav1d and https://github.com/videolan/dav1d
- GCC Runtime Library Exception: https://www.gnu.org/licenses/gcc-exception-3.1.html
- MinGW-w64 licensing: https://www.mingw-w64.org/license/
