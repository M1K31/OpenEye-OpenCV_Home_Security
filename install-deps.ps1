# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# OpenEye - optional heavy dependencies, Windows
#
# The Windows counterpart to install-deps.sh. Installs the optional packages
# that pip cannot resolve on its own here, and reports honestly when one is
# unavailable rather than aborting the whole install.
#
#     powershell -ExecutionPolicy Bypass -File install-deps.ps1
#     powershell -ExecutionPolicy Bypass -File install-deps.ps1 -Feature face
#
# WHY THIS SCRIPT EXISTS
#
# Face recognition cannot be expressed in a requirements file on Windows:
#
#   1. `dlib` publishes no Windows wheel for any CPython version, so pip falls
#      back to a source build that needs CMake and the Visual Studio C++ build
#      tools, and fails without them - taking every other package in the same
#      `pip install` down with it. `dlib-bin` ships prebuilt wheels for
#      cp39-cp313 and provides the same `dlib` module.
#
#   2. `face_recognition` declares `Requires-Dist: dlib (>=19.7)`. pip resolves
#      by DISTRIBUTION name, not import name, so `dlib-bin` being installed does
#      not satisfy it - pip downloads the dlib sdist and tries to build it
#      regardless. It must be installed with `--no-deps`, with its remaining
#      dependencies supplied directly.
#
# `--no-deps` is not permitted inside a requirements file, and environment
# markers cannot help with point 2, so the sequence has to live in a script.

[CmdletBinding()]
param(
    # Which optional feature to install. "all" is the default.
    [ValidateSet('all', 'face', 'audio', 'objects')]
    [string]$Feature = 'all',

    # Python to install into. Defaults to the active virtual environment.
    [string]$Python = '',

    # Where to look for a dlib wheel built by this project, if one has been
    # published. A URL or a local directory; passed to pip as --find-links.
    # Leave empty to go straight to the dlib-bin fallback.
    [string]$DlibWheelIndex = $env:OPENEYE_DLIB_WHEEL_INDEX
)

$ErrorActionPreference = 'Stop'

function Write-Step { param($m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    OK   $m" -ForegroundColor Green }
function Write-Warn { param($m) Write-Host "    WARN $m" -ForegroundColor Yellow }
function Write-Fail { param($m) Write-Host "    FAIL $m" -ForegroundColor Red }

function Resolve-Python {
    if ($Python) { return $Python }
    # Prefer the project's virtual environment, matching install-deps.sh and
    # manage.py, so a feature is never installed into the system interpreter
    # while the server runs from .venv and reports it missing.
    $venv = Join-Path $PSScriptRoot 'opencv_surveillance\.venv\Scripts\python.exe'
    if (Test-Path $venv) { return $venv }
    if ($env:VIRTUAL_ENV) {
        $active = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
        if (Test-Path $active) { return $active }
    }
    Write-Warn 'No virtual environment found; using the python on PATH.'
    Write-Warn 'Create one first:  python -m venv opencv_surveillance\.venv'
    return 'python'
}

$Py = Resolve-Python
Write-Step "Using interpreter: $Py"

# Confirm the interpreter is actually runnable before anything depends on it.
#
# Without this the first `& $Py` throws PowerShell's raw "The term 'python' is
# not recognized" and, because that is a terminating error inside a script, the
# summary never runs and the script still exits 0 — reporting success for an
# install that did nothing. A missing interpreter is the one condition here
# that IS fatal, so it is the one that gets a non-zero exit.
$version = $null
try {
    $version = & $Py -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
} catch {
    $version = $null
}
if (-not $version) {
    Write-Fail "Cannot run '$Py'."
    Write-Host  '         Install Python 3.9-3.12 from https://www.python.org/downloads/'
    Write-Host  '         (tick "Add python.exe to PATH"), then create the environment:'
    Write-Host  '             python -m venv opencv_surveillance\.venv'
    Write-Host  '         Or point this script at an interpreter directly:'
    Write-Host  '             .\install-deps.ps1 -Python C:\path\to\python.exe'
    exit 1
}
Write-Host "    Python $version"
if ($version -notin @('3.9', '3.10', '3.11', '3.12')) {
    Write-Warn "OpenEye supports Python 3.9-3.12 (numpy<2 and opencv<4.11 do not build above it)."
    Write-Warn "Continuing, but expect resolution failures."
}

# Run a command, keeping its output OFF the success stream.
#
# PowerShell folds any uncaptured output from a function into that function's
# RETURN VALUE. Calling pip or python directly inside these installers therefore
# did two things at once: it hid the output (it was never written to the host),
# and it turned `return $true` into an array of [output..., $true]. The summary
# then tested that array for truthiness and reported success for anything
# non-empty — including a failure whose stderr happened to be captured.
#
# Capturing explicitly makes the return value a real boolean and lets us decide
# when the detail is worth showing: quiet on success, in full on failure.
function Invoke-Quiet {
    param([string]$Exe, [string[]]$Arguments, [switch]$ShowOutput)

    $output = & $Exe @Arguments 2>&1
    $ok = ($LASTEXITCODE -eq 0)
    if ($ShowOutput -and $ok -and $output) {
        $output | ForEach-Object { Write-Host $_ }
    }
    if (-not $ok -and $output) {
        $output | Select-Object -Last 12 | ForEach-Object { Write-Host "         $_" }
    }
    return $ok
}


function Install-FaceRecognition {
    Write-Step 'Face recognition (dlib-bin + face_recognition)'

    # setuptools first and pinned. face_recognition_models imports
    # pkg_resources at module load, which setuptools 82 removed - installing it
    # afterwards would not help, because the failure happens on import.
    if (-not (Invoke-Quiet $Py @('-m','pip','install','--quiet','setuptools<82'))) {
        Write-Fail 'could not pin setuptools'; return $false
    }

    if (-not (Invoke-Quiet $Py @('-m','pip','install','--quiet','--only-binary=:all:','numpy<2'))) {
        Write-Fail 'could not install numpy'; return $false
    }

    # Two ways to get dlib, tried in order. They are not equivalent.
    #
    # 1. A wheel WE built, published on this project's releases. It is named
    #    `dlib`, so face_recognition's "Requires-Dist: dlib (>=19.7)" resolves
    #    against it and everything downstream behaves normally.
    #
    # 2. dlib-bin, a third-party repackaging of the same library. It works and
    #    imports as `dlib`, but pip matches requirements by DISTRIBUTION name,
    #    not import name — so it does NOT satisfy that requirement, and
    #    face_recognition has to be installed with --no-deps and its own
    #    dependencies supplied by hand.
    #
    # Hence the two branches below. The first is preferred because it needs no
    # special handling; the second is the fallback when no wheel has been
    # published for this Python version yet.
    $usedOwnWheel = $false
    if ($DlibWheelIndex) {
        Write-Host "    trying published wheel index: $DlibWheelIndex"
        $usedOwnWheel = Invoke-Quiet $Py @(
            '-m','pip','install','--quiet','--only-binary=:all:',
            '--find-links', $DlibWheelIndex, 'dlib')
    }

    if ($usedOwnWheel) {
        Write-Ok 'dlib installed from the project wheel'
        # Resolves normally: no --no-deps, no hand-listed dependencies.
        if (-not (Invoke-Quiet $Py @('-m','pip','install','--quiet','face_recognition'))) {
            Write-Fail 'face_recognition install failed'; return $false
        }
    }
    else {
        if ($DlibWheelIndex) {
            Write-Warn 'no project wheel for this Python version; falling back to dlib-bin'
        }
        if (-not (Invoke-Quiet $Py @('-m','pip','install','--quiet','--only-binary=:all:','dlib-bin>=19.24'))) {
            Write-Fail 'no prebuilt dlib wheel for this Python version.'
            Write-Host  '         Options: use Python 3.9-3.12, or build from source with'
            Write-Host  '         CMake plus the Visual Studio C++ build tools installed.'
            return $false
        }
        # --no-deps is required here, for the reason given above.
        if (-not (Invoke-Quiet $Py @('-m','pip','install','--quiet','--no-deps','face_recognition','face_recognition_models'))) {
            Write-Fail 'face_recognition install failed'; return $false
        }
        # Its remaining dependencies, supplied by hand because --no-deps skipped them.
        if (-not (Invoke-Quiet $Py @('-m','pip','install','--quiet','--only-binary=:all:','click','pillow'))) {
            Write-Fail 'face_recognition dependencies failed'; return $false
        }
    }

    # Prove it, rather than trusting exit codes. An install that reports success
    # and then cannot import is the failure mode this whole script is about.
    $proof = @'
import numpy, dlib, face_recognition
img = numpy.zeros((120, 120, 3), dtype=numpy.uint8)
face_recognition.face_locations(img)
face_recognition.face_encodings(img)
print("    verified: dlib " + dlib.__version__ + " + face_recognition working")
'@
    if (-not (Invoke-Quiet $Py @('-c', $proof) -ShowOutput)) {
        Write-Fail 'installed, but does not import'; return $false
    }

    if (-not $usedOwnWheel) {
        # On the fallback path pip prints "face-recognition 1.3.0 requires
        # dlib>=19.7, which is not installed". It is expected and harmless -
        # dlib-bin supplies the same module under a different distribution
        # name, and the check above has just proved the module works. Said out
        # loud so it does not read as a problem.
        Write-Host '    note: pip may warn that "dlib is not installed" - expected,'
        Write-Host '          dlib-bin provides it under a different package name.'
    }
    Write-Ok 'face recognition available'
    return $true
}

function Install-Audio {
    Write-Step 'Two-way audio (sounddevice + aiortc)'
    if (-not (Invoke-Quiet $Py @('-m','pip','install','--quiet','--only-binary=:all:','sounddevice','aiortc','av'))) {
        Write-Warn 'two-way audio unavailable; OpenEye runs without it.'
        return $false
    }
    Write-Ok 'two-way audio available'
    return $true
}

function Install-ObjectDetection {
    Write-Step 'Object detection (torch + ultralytics)'
    Write-Host '    This is a large download (~2 GB). CPU build; add CUDA separately if wanted.'
    if (-not (Invoke-Quiet $Py @('-m','pip','install','--quiet','torch','torchvision','--index-url','https://download.pytorch.org/whl/cpu'))) {
        Write-Warn 'torch unavailable; object detection disabled.'; return $false
    }
    if (-not (Invoke-Quiet $Py @('-m','pip','install','--quiet','ultralytics'))) {
        Write-Warn 'ultralytics unavailable; object detection disabled.'; return $false
    }
    Write-Ok 'object detection available'
    return $true
}

$results = @{}
switch ($Feature) {
    'face'    { $results['face recognition'] = Install-FaceRecognition }
    'audio'   { $results['two-way audio']    = Install-Audio }
    'objects' { $results['object detection'] = Install-ObjectDetection }
    'all' {
        $results['face recognition'] = Install-FaceRecognition
        $results['two-way audio']    = Install-Audio
        $results['object detection'] = Install-ObjectDetection
    }
}

Write-Host ''
Write-Step 'Summary'
foreach ($name in $results.Keys) {
    if ($results[$name]) { Write-Ok "$name" } else { Write-Warn "$name not installed" }
}
Write-Host ''
Write-Host 'OpenEye runs without any of these; each feature reports itself'
Write-Host 'unavailable rather than failing. Check with:'
Write-Host '    python opencv_surveillance\manage.py doctor'

# Optional features are optional: a feature that could not be installed is not
# a failure of this script, so it exits 0. Only being unable to run at all is.
exit 0
