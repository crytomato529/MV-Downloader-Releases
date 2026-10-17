# MV Downloader · 公开下载

Windows 10/11 x64 绿色软件：粘贴歌单，从 YouTube 下载 MV，预览原片、拖动选区并导出完整视频或剪辑片段。默认截取 20 秒，可调整长度；下载清晰度 1080p 封顶。

[下载 2.5.1 预览版](https://github.com/crytomato529/MV-Downloader-Releases/releases/tag/v2.5.1-preview)

请下载 **MV-Downloader-2.5.1-Windows-x64-Portable-preview.zip**，完整解压后双击 **MV Downloader.exe**。可以免费分享完整原包。首次使用无需 GitHub 账号，也不需要 AI、Python 或开发环境。界面需要 Windows .NET 4.8 与 [Microsoft WebView2](https://developer.microsoft.com/microsoft-edge/webview2/)。

2.5.1 修复待确认视频选区保存失败、切歌反复提示未保存及失败歌曲无法打开的问题；保存失败后仍可继续修复。支持最多 100 首、年份/赛季与逐首 YouTube 参考链接。已完成歌曲可立即预览、剪辑和导出，无须等整单结束；打包包含点击时已完成的歌曲并附其余状态。候选版本分别说明来源依据和画面类型，循环动画需要确认，纯静止封面会被排除。音轨可由本地文件或明确的 YouTube 音源替换，支持手动偏移/速度和同步预览，原片保留，可恢复原音轨。高分辨率和码率不保证画面/声音本身质量，请试听核对。

软件默认每天检查一次新版；发现新版时显示提示，支持手动检查、稍后提醒、跳过本版和关闭自动检查。更新检查只读取公开版本清单，不发送歌单或视频。

升级前关闭软件并备份整个旧文件夹，按包内“升级说明.txt”原地替换程序、工具与说明，保留“数据”“导出”和已有“素材”。本包不含开发者的歌单、视频、日志或账号。当前为预览版，尚未在另一台干净电脑验收。

软件源码保存在私有仓库。本公开仓库用于软件下载、更新清单、说明和第三方视频工具的构建材料。Release 中的工具源码 ZIP 面向需要源码的开发者，普通使用者只需上面的绿色软件 ZIP。

---

# MV Downloader Releases

This repository holds public download information and the build materials for separately distributed third-party tools. Application source code and user data are not included.

## Pinned FFmpeg tools

The manual **Build portable FFmpeg tools** workflow builds `ffmpeg.exe` and `ffprobe.exe` for Windows x64 from the exact archives in `sources.lock.json`:

- FFmpeg 8.1.1, upstream commit `239f2c733de417201d7ad3b3b8b0d9b63285b2b1`.
- x264 commit `0480cb05fa188d37ae87e8f4fd8f1aea3711f7ee`.
- dav1d 1.5.3, upstream commit `b546257f770768b2c88258c533da38b91a06f737`.

Source archives have fixed SHA-256 digests and are checked before extraction. The x264 archive is served by the GitHub mirror; its pinned commit was checked against the canonical VideoLAN repository. FFmpeg and dav1d are served by their upstream release site or project mirror.

External-library autodetection is disabled. Only x264 and dav1d are enabled as external libraries, linked statically. Native FFmpeg H264, VP9, AAC and Opus decoders, local-file containers, scale filters, and H264/AAC output remain enabled. AV1 software decoding uses dav1d. Native networking and Windows Schannel TLS are enabled for HTTPS/HLS fallback; ffplay is disabled.

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

GitHub Actions artifacts expire and require a signed-in account to download. They are build outputs for maintainers, not the public corresponding-source download location. Before distributing a software package containing these binaries, attach the complete software ZIP containing these executables **and their matching corresponding-source ZIP** to the same public GitHub Release, include their SHA-256 values, and place clear source-download instructions beside the software download and inside its third-party notices. Keep the matching source available while the binary download is offered. No written three-year source offer is used by these materials.

The software release page and update JSON will be added after the complete portable package is verified. Publishing these build materials does not publish the application source.

## Licensing

The FFmpeg executables built here are GPL-3.0-or-later (`--enable-gpl --enable-version3`). x264 is GPL-2.0-or-later; dav1d is BSD-2-Clause. License texts from the exact downloaded sources and MinGW toolchain notices are included in both output ZIPs. Build materials written for this repository are MIT licensed; this does not change the licenses of any upstream source or executable. See `licenses/THIRD_PARTY_NOTICES.md`.

Native networking and Windows Schannel TLS remain enabled for HTTPS/HLS fallback. External dependency autodetection remains disabled; no external TLS library is linked.

## Pinned standalone downloader

The **Build minimal Windows downloader** workflow uses `downloader.lock.json` and `scripts/build-downloader.py`. It builds yt-dlp 2026.08.19 with EJS 0.8.0, standard Python urllib/SSL networking and a bundled local JavaScript solver, which uses the application's Node runtime. Optional networking, crypto and audio extensions are excluded and the executable archive is checked for their absence.

Exact source archives, wheel inputs, CPython Windows dependency sources, original notices and build logs are in **yt-dlp-minimal-corresponding-source.zip**. The downloader binary is included in the main portable software ZIP, alongside FFmpeg/ffprobe and Node. The matching source bundles remain separately downloadable in the same public Release. Normal users only need the portable software ZIP.
