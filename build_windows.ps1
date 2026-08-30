$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Os testes falharam; build cancelado." }
python -m PyInstaller --noconfirm --clean "AdegaDoBruninho.spec"
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o executável." }
Copy-Item ".env.example" "dist\AdegaDoBruninho\.env.example" -Force
Copy-Item "README.md","RELEASE_NOTES.md","VERSION" "dist\AdegaDoBruninho" -Force
& "dist\AdegaDoBruninho\AdegaDoBruninho.exe" --smoke-test
if ($LASTEXITCODE -ne 0) { throw "O executável falhou no smoke test." }
Write-Host "Build concluído: dist\AdegaDoBruninho\AdegaDoBruninho.exe"
