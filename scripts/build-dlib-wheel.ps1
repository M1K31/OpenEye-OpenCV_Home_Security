# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# Build a dlib wheel for Windows from the official PyPI source release.
#
#     powershell -ExecutionPolicy Bypass -File scripts\build-dlib-wheel.ps1
#     powershell -ExecutionPolicy Bypass -File scripts\build-dlib-wheel.ps1 -DlibVersion 20.0.1 -OutDir dist
#
# WHY
#
# dlib publishes no binary wheel for any platform - PyPI carries only
# dlib-<version>.tar.gz. On macOS and Linux a compiler is usually present and
# the source build succeeds. On Windows it is not, so `pip install` fails and
# takes every other package in the same command with it.
#
# `dlib-bin` is a third-party repackaging that ships prebuilt wheels, and
# install-deps.ps1 falls back to it. But pip matches requirements by
# DISTRIBUTION name, and face_recognition declares "Requires-Dist: dlib
# (>=19.7)" - which dlib-bin does not satisfy, so pip fetches the sdist and
# builds it anyway. A wheel produced here is named `dlib` and satisfies that
# requirement directly.
#
# This is the same work .github/workflows/build-dlib-windows.yml performs. The
# workflow calls this script rather than repeating the steps, so the thing CI
# runs and the thing you can run by hand cannot drift apart.
#
# REQUIREMENTS
#
#   - Python 3.9-3.12 (the wheel is specific to the minor version building it)
#   - CMake on PATH
#   - Visual Studio Build Tools with the "Desktop development with C++" workload
#
# dlib is Boost Software License 1.0, which permits binary redistribution.

[CmdletBinding()]
param(
    [string]$DlibVersion = '20.0.1',
    [string]$OutDir      = 'dist',
    [string]$Python      = 'python',
    # Skip the post-build verification. Not recommended: the check is what
    # distinguishes a wheel that exists from a wheel that works.
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Stop'

function Write-Step { param($m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    OK   $m" -ForegroundColor Green }
function Write-Fail { param($m) Write-Host "    FAIL $m" -ForegroundColor Red }

# --- toolchain ---------------------------------------------------------------
Write-Step 'Checking the build toolchain'

$pyVersion = $null
try { $pyVersion = & $Python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null } catch { }
if (-not $pyVersion) {
    Write-Fail "Cannot run '$Python'. Install Python 3.9-3.12 and add it to PATH,"
    Write-Host '         or pass -Python C:\path\to\python.exe'
    exit 1
}
Write-Host "    Python $pyVersion"
if ($pyVersion -notin @('3.9','3.10','3.11','3.12')) {
    Write-Fail "OpenEye supports Python 3.9-3.12 (numpy<2 caps it). Building for $pyVersion"
    Write-Host '         produces a wheel the application cannot be installed alongside.'
    exit 1
}

if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Fail 'CMake is not on PATH.'
    Write-Host '         Install it from https://cmake.org/download/ (tick "Add to PATH"),'
    Write-Host '         or with: winget install Kitware.CMake'
    exit 1
}
Write-Host "    $((cmake --version | Select-Object -First 1))"

# Checked explicitly so a missing C++ workload is named here rather than
# surfacing as a confusing compiler error several minutes into the build.
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
    $vs = & $vswhere -latest -products * `
            -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
            -property displayName 2>$null
    if (-not $vs) {
        Write-Fail 'Visual Studio C++ build tools not found.'
        Write-Host '         Install "Build Tools for Visual Studio" and select the'
        Write-Host '         "Desktop development with C++" workload:'
        Write-Host '         https://visualstudio.microsoft.com/downloads/'
        exit 1
    }
    Write-Host "    $vs"
} else {
    Write-Host '    (vswhere not present; assuming a usable compiler is configured)'
}

# --- build -------------------------------------------------------------------
Write-Step "Building dlib $DlibVersion (expect several minutes)"

# Build requirements installed directly, with isolation disabled.
#
# dlib's pyproject declares requires = [setuptools, wheel, packaging, cmake].
# Under pip's build isolation that `cmake` is resolved from PyPI into a fresh
# environment, and where no wheel matches the platform pip builds CMake ITSELF
# from source - which fails inside cmcurl without ever reaching dlib. dlib's own
# setup.py carries the comment "the pip cmake package is busted" about this.
# Measured: 68s to that failure with isolation, versus a working build without.
& $Python -m pip install --quiet --upgrade pip wheel setuptools packaging
if ($LASTEXITCODE -ne 0) { Write-Fail 'could not install build requirements'; exit 1 }

$started = Get-Date
& $Python -m pip wheel --no-deps --no-build-isolation --no-binary=:all: `
    --wheel-dir $OutDir "dlib==$DlibVersion"
if ($LASTEXITCODE -ne 0) {
    Write-Fail 'the build failed. The output above names the cause.'
    exit 1
}
$elapsed = [int]((Get-Date) - $started).TotalSeconds

$wheel = Get-ChildItem $OutDir -Filter 'dlib-*.whl' |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $wheel) { Write-Fail "no wheel produced in $OutDir"; exit 1 }
Write-Ok "built in ${elapsed}s: $($wheel.Name)"

if ($SkipVerify) { Write-Host ''; Write-Host "Wheel: $($wheel.FullName)"; exit 0 }

# --- verify ------------------------------------------------------------------
# A wheel that builds and cannot import is the failure this exists to prevent,
# so prove it in a clean interpreter rather than trusting the exit code.
Write-Step 'Verifying the wheel in a clean environment'

$venv = Join-Path ([System.IO.Path]::GetTempPath()) "dlib-verify-$(Get-Random)"
& $Python -m venv $venv
$vpy = Join-Path $venv 'Scripts\python.exe'

try {
    & $vpy -m pip install --quiet --upgrade pip "setuptools<82"
    & $vpy -m pip install --quiet --find-links $OutDir --only-binary=:all: dlib
    if ($LASTEXITCODE -ne 0) { Write-Fail 'the wheel would not install'; exit 1 }

    & $vpy -m pip install --quiet "numpy<2" pillow click
    if ($LASTEXITCODE -ne 0) { Write-Fail 'could not install test dependencies'; exit 1 }

    # The point of the whole exercise: face_recognition must resolve WITHOUT
    # --no-deps. If this needs it, the wheel is not satisfying "Requires-Dist:
    # dlib" and we have gained nothing over dlib-bin.
    & $vpy -m pip install --quiet face_recognition
    if ($LASTEXITCODE -ne 0) { Write-Fail 'face_recognition would not install against this wheel'; exit 1 }

    $installed = & $vpy -m pip list --format=freeze
    if ($installed -match 'dlib-bin') {
        Write-Fail 'dlib-bin was pulled in; the wheel did not satisfy the requirement.'
        exit 1
    }
    if (-not ($installed -match '(?m)^dlib==')) {
        Write-Fail 'dlib is not installed under its own distribution name.'
        exit 1
    }

    $proof = @'
import numpy, dlib, face_recognition, sys
img = numpy.zeros((120, 120, 3), dtype=numpy.uint8)
face_recognition.face_locations(img)
face_recognition.face_encodings(img)
print("    verified: dlib " + dlib.__version__ + " on Python " + sys.version.split()[0])
'@
    & $vpy -c $proof
    if ($LASTEXITCODE -ne 0) { Write-Fail 'the wheel installs but does not import'; exit 1 }

    Write-Ok 'face_recognition resolved against this wheel, no --no-deps needed'
}
finally {
    Remove-Item -Recurse -Force $venv -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host "Wheel: $($wheel.FullName)"
Write-Host ''
Write-Host 'To use it:'
Write-Host "    .\install-deps.ps1 -Feature face -DlibWheelIndex $OutDir"
Write-Host ''
Write-Host 'To share it, attach it to a GitHub release and point installs at that URL'
Write-Host 'with -DlibWheelIndex or the OPENEYE_DLIB_WHEEL_INDEX environment variable.'
exit 0
