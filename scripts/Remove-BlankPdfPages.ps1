param(
    [Parameter(Mandatory = $true)]
    [string]$PdfPath,

    [Parameter(Mandatory = $false)]
    [double]$WhiteThreshold = 253.0,

    [Parameter(Mandatory = $false)]
    [int]$MaxTinyTextLength = 24
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = "C:\Users\Chili\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$script = Join-Path $root "scripts\remove_blank_pdf_pages.py"

& $python $script $PdfPath --white-threshold $WhiteThreshold --max-tiny-text-length $MaxTinyTextLength
if ($LASTEXITCODE -ne 0) {
    throw "Blank-page cleanup failed for $PdfPath"
}
