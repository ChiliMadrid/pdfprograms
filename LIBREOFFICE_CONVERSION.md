# LibreOffice Conversion Workflow

This workspace uses LibreOffice to convert the strength program `.docx` files to PDF without editing the source files.

## Install LibreOffice

Install LibreOffice with the standard Windows installer. The workflow first checks:

```powershell
C:\Program Files\LibreOffice\program\soffice.exe
```

If LibreOffice is installed somewhere else, pass that path with `-LibreOfficePath`.

On this PC, LibreOffice is currently installed at:

```powershell
D:\Chili\Programs\LibreOffice\program\soffice.exe
```

The script can detect that registry install location automatically.

For command-line conversion, the script automatically prefers `soffice.com` next to `soffice.exe` when it exists.

## Convert One File

```powershell
.\scripts\Convert-DocxToPdf.ps1 ".\The First Flame\The First Flame.docx"
```

By default, the PDF is written to an `exports` folder beside the source file.

## Convert All Program DOCX Files

```powershell
.\scripts\Convert-DocxToPdf.ps1 . -Recursive -OutputDirectory ".\exports"
```

This creates PDFs in the root `exports` folder and leaves the original `.docx` and existing `.pdf` files untouched.

## Replace an Existing Export

```powershell
.\scripts\Convert-DocxToPdf.ps1 . -Recursive -OutputDirectory ".\exports" -Force
```

Use `-Force` only when you deliberately want to replace PDFs in the chosen export folder.

## Verification

The script reports one row per source file:

- `Verified` means the PDF exists, is not empty, and has a detectable page count.
- `SkippedExisting` means the PDF already existed and was left alone.
- `NeedsReview` means the export exists but should be opened manually before use.

For visual review, add `-OpenAfterConvert` when converting a small number of files.
