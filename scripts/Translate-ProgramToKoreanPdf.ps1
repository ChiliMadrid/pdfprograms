param(
    [Parameter(Mandatory = $true)]
    [string]$SourceDocx,

    [Parameter(Mandatory = $false)]
    [string]$OutputDirectory = ".\korean_exports",

    [Parameter(Mandatory = $false)]
    [string]$LibreOfficePath = "C:\Program Files\LibreOffice\program\soffice.exe",

    [Parameter(Mandatory = $false)]
    [int]$LimitParagraphs = 0,

    [Parameter(Mandatory = $false)]
    [double]$FontScale = 1.0,

    [Parameter(Mandatory = $false)]
    [double]$IntroFontScale = 0.86,

    [Parameter(Mandatory = $false)]
    [double]$LineScale = 0.94
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = "C:\Users\Chili\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$translator = Join-Path $root "scripts\translate_docx_to_korean.py"
$converter = Join-Path $root "scripts\Convert-DocxToPdf.ps1"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Bundled Python runtime not found: $python"
}

$source = Resolve-Path -LiteralPath $SourceDocx
$outDir = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputDirectory))
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$baseName = [System.IO.Path]::GetFileNameWithoutExtension($source.Path)
$koreanDocx = Join-Path $outDir ($baseName + " Korean.docx")

$env:PYTHONIOENCODING = "utf-8"
$args = @($translator, $source.Path, $koreanDocx, "--font-scale", $FontScale, "--intro-font-scale", $IntroFontScale, "--line-scale", $LineScale)
if ($LimitParagraphs -gt 0) {
    $args += @("--limit", $LimitParagraphs)
}

& $python @args
if ($LASTEXITCODE -ne 0) {
    throw "Translation failed for $($source.Path)"
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $converter $koreanDocx -OutputDirectory $outDir -LibreOfficePath $LibreOfficePath -Force
if ($LASTEXITCODE -ne 0) {
    throw "PDF conversion failed for $koreanDocx"
}

Get-ChildItem -LiteralPath $outDir -Filter ($baseName + " Korean.pdf") | Select-Object FullName,Length,LastWriteTime
