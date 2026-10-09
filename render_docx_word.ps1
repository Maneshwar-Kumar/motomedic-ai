param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$source = (Resolve-Path -LiteralPath $InputPath).Path
$target = [System.IO.Path]::GetFullPath($OutputPath)
$folder = [System.IO.Path]::GetDirectoryName($target)
New-Item -ItemType Directory -Path $folder -Force | Out-Null

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    try { $word.AutomationSecurity = 3 } catch { }
    $document = $word.Documents.Open($source, $false, $true, $false)
    $document.ExportAsFixedFormat($target, 17)
    Write-Output $target
}
finally {
    if ($document -ne $null) { $document.Close(0) }
    if ($word -ne $null) { $word.Quit() }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
