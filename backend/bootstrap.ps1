#!/usr/bin/env pwsh
Write-Host "Looking for a suitable Python interpreter (3.12 or 3.11)..."
$desired = @('3.12','3.11')
$foundPython = $null
foreach ($v in $desired) {
  try {
    $out = & py -$v -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) { $foundPython = $out.Trim(); break }
  } catch { }
  try {
    $exeName = "python$v"
    $out2 = & $exeName -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $out2) { $foundPython = $out2.Trim(); break }
  } catch { }
}

if (-Not $foundPython) {
  Write-Host "No suitable alternative Python (3.12/3.11) found on PATH; attempting with current Python..."
  $pyver = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
  $pyver = $pyver.Trim()
  Write-Host "Using current Python version: $pyver"
  Write-Host "Note: Installation may fail if wheels are not available for this version."
  $foundPython = python -c "import sys; print(sys.executable)"
  $foundPython = $foundPython.Trim()
}

if ($foundPython) {
  Write-Host "Found Python interpreter: $foundPython"
  $venvDir = Join-Path -Path $PSScriptRoot -ChildPath '.venv'
  if (-Not (Test-Path $venvDir)) {
    Write-Host "Creating virtualenv at $venvDir..."
    & $foundPython -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create virtualenv with $foundPython"; exit $LASTEXITCODE }
  } else {
    Write-Host "Virtualenv already exists at $venvDir"
  }
  $venvPython = Join-Path -Path $venvDir -ChildPath 'Scripts\\python.exe'
  Write-Host "Upgrading pip, setuptools, wheel, and build inside venv..."
  & $venvPython -m pip install --upgrade pip setuptools wheel build
  if ($LASTEXITCODE -ne 0) { Write-Error "Failed to upgrade packaging tools in venv"; exit $LASTEXITCODE }

  Write-Host "Installing requirements from requirements.txt..."
  $req = Join-Path -Path $PSScriptRoot -ChildPath 'requirements.txt'
  Write-Host "Using requirements file: $req"
  & $venvPython -m pip install -r "$req"
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "pip install failed with build isolation; retrying with --no-build-isolation..."
    & $venvPython -m pip install --no-build-isolation -r "$req"
    if ($LASTEXITCODE -ne 0) {
      Write-Error "pip install (with --no-build-isolation) also failed. See output above for details."
      exit $LASTEXITCODE
    }
  }

  Write-Host "Dependencies installed successfully."
} else {
  Write-Error "Could not find any Python interpreter."
  exit 1
}
