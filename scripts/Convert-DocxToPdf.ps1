param(
    [Parameter(Mandatory = $false, Position = 0)]
    [string]$InputPath = ".",

    [Parameter(Mandatory = $false)]
    [string]$OutputDirectory = "",

    [Parameter(Mandatory = $false)]
    [string]$LibreOfficePath = "C:\Program Files\LibreOffice\program\soffice.exe",

    [Parameter(Mandatory = $false)]
    [switch]$Recursive,

    [Parameter(Mandatory = $false)]
    [switch]$Force,

    [Parameter(Mandatory = $false)]
    [switch]$OpenAfterConvert
)

$ErrorActionPreference = "Stop"

function Resolve-AbsolutePath {
    param([string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Path))
}

function Get-PdfPageCount {
    param([string]$Path)

    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        $text = [System.Text.Encoding]::GetEncoding(28591).GetString($bytes)
        $matches = [regex]::Matches($text, "(?<!s)/Type\s*/Page\b")
        return $matches.Count
    }
    catch {
        return 0
    }
}

function Get-DocxFiles {
    param([string]$Path, [bool]$UseRecursive)

    $resolved = Resolve-AbsolutePath $Path

    if (-not (Test-Path -LiteralPath $resolved)) {
        throw "Input path does not exist: $resolved"
    }

    $item = Get-Item -LiteralPath $resolved

    if (-not $item.PSIsContainer) {
        if ($item.Extension -ine ".docx") {
            throw "Input file is not a .docx file: $resolved"
        }

        return @($item)
    }

    $searchOption = if ($UseRecursive) { "AllDirectories" } else { "TopDirectoryOnly" }
    return @(Get-ChildItem -LiteralPath $resolved -File -Filter "*.docx" -Recurse:($searchOption -eq "AllDirectories") |
        Where-Object { $_.Name -notlike "~$*" } |
        Sort-Object FullName)
}

function Find-LibreOfficePath {
    param([string]$PreferredPath)

    if ((-not [string]::IsNullOrWhiteSpace($PreferredPath)) -and (Test-Path -LiteralPath $PreferredPath)) {
        return $PreferredPath
    }

    $registryKeys = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )

    $install = Get-ItemProperty $registryKeys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -like "*LibreOffice*" -and $_.InstallLocation } |
        Select-Object -First 1

    if ($install) {
        $candidate = Join-Path $install.InstallLocation "program\soffice.exe"
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $command = Get-Command soffice -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    return $null
}

function Get-LibreOfficeCliPath {
    param([string]$Path)

    $cliPath = [System.IO.Path]::ChangeExtension($Path, ".com")
    if (Test-Path -LiteralPath $cliPath) {
        return $cliPath
    }

    return $Path
}

if (-not (Test-Path -LiteralPath $LibreOfficePath)) {
    $detectedLibreOfficePath = Find-LibreOfficePath -PreferredPath $LibreOfficePath
    if (-not $detectedLibreOfficePath) {
        throw "LibreOffice was not found. Install LibreOffice or pass -LibreOfficePath."
    }

    $LibreOfficePath = $detectedLibreOfficePath
}

$LibreOfficePath = Get-LibreOfficeCliPath -Path $LibreOfficePath

$sources = Get-DocxFiles -Path $InputPath -UseRecursive:$Recursive.IsPresent

if ($sources.Count -eq 0) {
    Write-Host "No .docx files found."
    exit 0
}

$rootOutput = $null
if ($OutputDirectory -ne "") {
    $rootOutput = Resolve-AbsolutePath $OutputDirectory
    New-Item -ItemType Directory -Force -Path $rootOutput | Out-Null
}

$results = New-Object System.Collections.Generic.List[object]
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("cm-libreoffice-export-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    foreach ($source in $sources) {
        $destinationDirectory = if ($rootOutput) { $rootOutput } else { Join-Path $source.DirectoryName "exports" }
        New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null

        $destination = Join-Path $destinationDirectory ([System.IO.Path]::ChangeExtension($source.Name, ".pdf"))
        if ((Test-Path -LiteralPath $destination) -and -not $Force) {
            $pageCount = Get-PdfPageCount -Path $destination
            $results.Add([pscustomobject]@{
                Source = $source.FullName
                Output = $destination
                Status = "SkippedExisting"
                SizeBytes = (Get-Item -LiteralPath $destination).Length
                PageCount = $pageCount
            })
            continue
        }

        $workDirectory = Join-Path $tempRoot ([guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Force -Path $workDirectory | Out-Null

        $arguments = @(
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--convert-to",
            "pdf",
            "--outdir",
            $workDirectory,
            $source.FullName
        )

        & $LibreOfficePath @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "LibreOffice failed for '$($source.FullName)' with exit code $LASTEXITCODE."
        }

        $converted = Join-Path $workDirectory ([System.IO.Path]::ChangeExtension($source.Name, ".pdf"))
        if (-not (Test-Path -LiteralPath $converted)) {
            throw "LibreOffice did not create the expected PDF for '$($source.FullName)'."
        }

        Move-Item -LiteralPath $converted -Destination $destination -Force:$Force.IsPresent

        $outputItem = Get-Item -LiteralPath $destination
        $pageCount = Get-PdfPageCount -Path $destination
        $status = if (($outputItem.Length -gt 0) -and ($pageCount -gt 0)) { "Verified" } else { "NeedsReview" }

        $results.Add([pscustomobject]@{
            Source = $source.FullName
            Output = $destination
            Status = $status
            SizeBytes = $outputItem.Length
            PageCount = $pageCount
        })

        if ($OpenAfterConvert) {
            Invoke-Item -LiteralPath $destination
        }
    }
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

$results | Select-Object Status, PageCount, SizeBytes, Output | Format-Table -AutoSize

$failed = @($results | Where-Object { $_.Status -eq "NeedsReview" })
if ($failed.Count -gt 0) {
    Write-Warning "$($failed.Count) PDF export(s) need manual review."
    exit 2
}
