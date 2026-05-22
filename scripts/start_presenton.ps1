# Presenton Docker 기동 — MCP http://localhost:5000/mcp
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".env")) {
    Write-Host "`.env` 없음 — `.env.example`을 복사한 뒤 PRESENTON_USERNAME/PASSWORD를 설정하세요."
    Copy-Item ".env.example" ".env" -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path "presenton_data" | Out-Null

Write-Host "Presenton 컨테이너 기동 중 (포트 ${env:PRESENTON_PORT:-5000})..."
docker compose -f docker-compose.presenton.yml up -d

$port = if ($env:PRESENTON_PORT) { $env:PRESENTON_PORT } else { "5000" }
Write-Host "UI:  http://localhost:$port"
Write-Host "MCP: http://localhost:$port/mcp"
Write-Host "AutoPM `.env`: PRESENTON_BASE_URL=http://127.0.0.1:$port, AUTOPM_PRESENTON_USE_MCP=true"
