# KC Ledger Windows package builder. Requires Python 3.12, Node.js 22 and Inno Setup 6.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($version -ne "3.12") { throw "Python 3.12 is required; found $version" }
if (!(Test-Path "package-lock.json")) { throw "package-lock.json is missing; generate and commit a lockfile" }
npm ci
if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
npm run typecheck
if ($LASTEXITCODE -ne 0) { throw "Frontend type checking failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Vite build failed" }
python -m pip install -e ".[desktop]"
if ($LASTEXITCODE -ne 0) { throw "Python desktop install failed" }
$env:DJANGO_SECRET_KEY = "build-only-" + [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
$env:DJANGO_DEBUG = "1"
$env:LEDGER_DB_PATH = Join-Path $env:TEMP ("kc-ledger-build-" + [guid]::NewGuid().ToString("N") + ".sqlite3")
python backend\manage.py collectstatic --noinput
if ($LASTEXITCODE -ne 0) { throw "Collectstatic failed" }
Remove-Item Env:\DJANGO_SECRET_KEY
Remove-Item Env:\DJANGO_DEBUG
Remove-Item Env:\LEDGER_DB_PATH
$pkgArgs = @("--noconfirm","--clean","--windowed","--onedir","--name","KC Ledger","--paths","backend","--add-data","backend;backend","--add-data","dist;dist","--add-data","backend\ledger\templates;ledger\templates","--add-data","backend\ledger\migrations;ledger\migrations","--add-data","backend\staticfiles;backend\staticfiles","--collect-submodules","config","--collect-submodules","ledger","--collect-all","django","--collect-all","ninja","--collect-all","whitenoise","--collect-all","apscheduler","--collect-all","pydantic","--collect-all","webview","--collect-all","reportlab","desktop\main.py")
python -m PyInstaller @pkgArgs
if ($LASTEXITCODE -ne 0) { throw "Desktop packaging failed" }
$exe = "dist\KC Ledger\KC Ledger.exe"
if (!(Test-Path $exe)) { throw "KC Ledger.exe was not produced" }
Get-FileHash -Algorithm SHA256 $exe
# Bundle Microsoft's signed Evergreen bootstrapper to install WebView2 if absent.
$webviewBootstrapper = Join-Path $root 'desktop\MicrosoftEdgeWebView2Setup.exe'
Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $webviewBootstrapper
$signature = Get-AuthenticodeSignature -FilePath $webviewBootstrapper
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft') {
  throw 'WebView2 bootstrapper is missing a valid Microsoft Authenticode signature'
}
Get-FileHash -Algorithm SHA256 $webviewBootstrapper

if (Get-Command ISCC.exe -ErrorAction SilentlyContinue) {
  ISCC.exe desktop\KC-Ledger.iss
  if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
  Get-ChildItem "installer-output\*.exe" | Get-FileHash -Algorithm SHA256
} else {
  Write-Warning "Inno Setup 6 not installed; desktop executable built but installer absent"
}
