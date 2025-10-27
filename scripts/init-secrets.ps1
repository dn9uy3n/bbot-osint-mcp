Param()
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$secretsDir = Join-Path $root "secrets"
$apiTokenFile = Join-Path $secretsDir "api_token"
$neo4jPassFile = Join-Path $secretsDir "neo4j_password"
$credsOut = Join-Path $secretsDir "credentials.txt"

New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null

function Gen-Hex {
  # 256-bit token
  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
  ($bytes | ForEach-Object { $_.ToString('x2') }) -join ''
}

function Gen-Pass {
  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
  [Convert]::ToBase64String($bytes)
}

if (!(Test-Path $apiTokenFile) -or ((Get-Item $apiTokenFile).Length -eq 0)) {
  $apiToken = Gen-Hex
  [IO.File]::WriteAllText($apiTokenFile, $apiToken)
} else {
  $apiToken = Get-Content -Raw $apiTokenFile
}

if (!(Test-Path $neo4jPassFile) -or ((Get-Item $neo4jPassFile).Length -eq 0)) {
  $neoPass = Gen-Pass
  [IO.File]::WriteAllText($neo4jPassFile, $neoPass)
} else {
  $neoPass = Get-Content -Raw $neo4jPassFile
}

$content = @(
  "Generated at: $(Get-Date -Format o)",
  "",
  "API_TOKEN: $apiToken",
  "NEO4J_USERNAME: neo4j",
  "NEO4J_PASSWORD: $neoPass",
  "",
  "Keep this file secret. It is not committed to git (see secrets/.gitignore)."
) -join "`n"

[IO.File]::WriteAllText($credsOut, $content)

Write-Host "Secrets generated in $secretsDir"

