<#
Read local images with the installed Windows OCR engine using Windows PowerShell 5.1.
InputJson is a UTF-8 JSON array of image paths. Results preserve input order.
Only JSON is written to stdout; unavailable engines or invalid images exit nonzero.
This bridge performs no name correction, player lookup, downloading or installation.
#>
param(
    [string]$InputJson,
    [switch]$Info
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

try {
    if ($Info -and $InputJson) {
        throw 'Use either -Info or -InputJson, not both.'
    }
    if (-not $Info -and -not $InputJson) {
        throw 'Provide -InputJson or -Info.'
    }
    if ($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5) {
        throw 'This bridge requires Windows PowerShell 5.1, not PowerShell Core.'
    }

    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
    [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
    [Windows.Storage.FileAccessMode, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
    [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType=WindowsRuntime] | Out-Null

    $language = [Windows.Globalization.Language]::new('en-US')
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
    if ($null -eq $engine -or $engine.RecognizerLanguage.LanguageTag -ne 'en-US') {
        throw 'The installed Windows OCR en-US language model is unavailable.'
    }
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
        $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    if ($null -eq $asTask) {
        throw 'The Windows Runtime asynchronous task adapter is unavailable.'
    }

    function Await-OcrOperation($Operation, [Type]$ResultType) {
        $task = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
        $task.Wait()
        return $task.Result
    }

    $results = @()
    if (-not $Info) {
        $inputText = Get-Content -LiteralPath $InputJson -Raw -Encoding UTF8
        if ($inputText -notmatch '^\s*\[') {
            throw 'InputJson must contain a JSON array of image paths.'
        }
        # PowerShell 5.1 preserves the parsed array as one pipeline value.
        # An @() wrapper would nest it and make each path an array, not a string.
        $imagePaths = ConvertFrom-Json -InputObject $inputText
        foreach ($imagePath in $imagePaths) {
            if ($imagePath -isnot [string] -or [string]::IsNullOrWhiteSpace($imagePath)) {
                throw 'Every image path must be a nonempty string.'
            }
            $absolutePath = (Resolve-Path -LiteralPath $imagePath).ProviderPath
            if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
                throw ('Image is not a file: ' + $imagePath)
            }
            $stream = $null
            $bitmap = $null
            try {
                $file = Await-OcrOperation (
                    [Windows.Storage.StorageFile]::GetFileFromPathAsync($absolutePath)
                ) ([Windows.Storage.StorageFile])
                $stream = Await-OcrOperation (
                    $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
                ) ([Windows.Storage.Streams.IRandomAccessStream])
                $decoder = Await-OcrOperation (
                    [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
                ) ([Windows.Graphics.Imaging.BitmapDecoder])
                $bitmap = Await-OcrOperation (
                    $decoder.GetSoftwareBitmapAsync()
                ) ([Windows.Graphics.Imaging.SoftwareBitmap])
                $recognized = Await-OcrOperation (
                    $engine.RecognizeAsync($bitmap)
                ) ([Windows.Media.Ocr.OcrResult])
                $results += [PSCustomObject]@{
                    text = [string]$recognized.Text
                    lines = @($recognized.Lines | ForEach-Object { [string]$_.Text })
                }
            }
            finally {
                if ($null -ne $bitmap) { $bitmap.Dispose() }
                if ($null -ne $stream) { $stream.Dispose() }
            }
        }
    }

    $dllPath = Join-Path $env:SystemRoot 'System32\Windows.Media.Ocr.dll'
    [PSCustomObject]@{
        engine = 'windows_ocr'
        language = $engine.RecognizerLanguage.LanguageTag
        os_version = [Environment]::OSVersion.Version.ToString()
        dll_version = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($dllPath).FileVersion
        results = @($results)
    } | ConvertTo-Json -Depth 5 -Compress
}
catch {
    [Console]::Error.WriteLine($_.Exception.GetBaseException().Message)
    exit 1
}
