param(
    [Parameter(Mandatory=$true)][string]$ToolsDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$toolsPath = (Resolve-Path -LiteralPath $ToolsDirectory).Path
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$outputPath = (Resolve-Path -LiteralPath $OutputDirectory).Path
$ffmpegPath = Join-Path $toolsPath 'bin/ffmpeg.exe'
$ffprobePath = Join-Path $toolsPath 'bin/ffprobe.exe'
$report = [ordered]@{passed=$false; os=[Environment]::OSVersion.VersionString; checks=@()}
function Run-Tool([string]$File, [string[]]$Arguments) {
    $text = & $File @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Tool failed ($LASTEXITCODE): $File $($Arguments -join ' ')`n$text" }
    return ($text -join "`n")
}
try {
    $manifest = Get-Content -LiteralPath (Join-Path $toolsPath 'build-manifest.json') -Raw | ConvertFrom-Json
    foreach ($tool in $manifest.tools) {
        $actual = (Get-FileHash -LiteralPath (Join-Path $toolsPath "bin/$($tool.file)") -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $tool.sha256) { throw "Digest mismatch: $($tool.file)" }
    }
    $report.checks += 'Both binary hashes match build-manifest.json'
    $report.ffmpeg_version = Run-Tool $ffmpegPath @('-hide_banner','-version')
    $report.ffprobe_version = Run-Tool $ffprobePath @('-hide_banner','-version')
    $decoders = Run-Tool $ffmpegPath @('-hide_banner','-decoders')
    $encoders = Run-Tool $ffmpegPath @('-hide_banner','-encoders')
    foreach ($name in @('h264','vp9','libdav1d','aac','opus')) {
        if ($decoders -notmatch "(?m)^\s+\S+\s+$name\s+") { throw "Missing decoder: $name" }
    }
    foreach ($name in @('libx264','aac')) {
        if ($encoders -notmatch "(?m)^\s+\S+\s+$name\s+") { throw "Missing encoder: $name" }
    }
    $report.checks += 'H264, VP9, AV1/dav1d, AAC and Opus decoding; x264 and AAC encoding'
    $sample = Join-Path $outputPath 'synthetic-source.mp4'
    $clip = Join-Path $outputPath 'synthetic-clip.mp4'
    Run-Tool $ffmpegPath @('-y','-hide_banner','-loglevel','error','-f','lavfi','-i','testsrc2=size=160x90:rate=15:duration=3','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=3','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-shortest',$sample) | Out-Null
    Run-Tool $ffmpegPath @('-y','-hide_banner','-loglevel','error','-ss','0.5','-i',$sample,'-t','1.25','-vf','scale=160:90,scale=trunc(iw/2)*2:trunc(ih/2)*2','-c:v','libx264','-preset','medium','-crf','18','-profile:v','high','-level','4.2','-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-ar','48000','-ac','2','-movflags','+faststart',$clip) | Out-Null
    $info = Run-Tool $ffprobePath @('-v','error','-show_streams','-show_format','-of','json',$clip) | ConvertFrom-Json
    if (@($info.streams | Where-Object codec_type -eq video).Count -ne 1) { throw 'Clip video stream missing' }
    if (@($info.streams | Where-Object codec_type -eq audio).Count -ne 1) { throw 'Clip audio stream missing' }
    if ([Math]::Abs([double]$info.format.duration - 1.25) -gt 0.15) { throw 'Clip duration mismatch' }
    Run-Tool $ffmpegPath @('-v','error','-xerror','-i',$clip,'-f','null','-') | Out-Null
    $report.checks += 'Real synthetic H264/AAC encode, accurate clip, streams and complete decode'
    $report.clip_duration_seconds = [double]$info.format.duration
    $report.passed = $true
} catch {
    $report.error = $_.Exception.Message
    throw
} finally {
    $report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $outputPath 'windows-smoke.json') -Encoding utf8
}
