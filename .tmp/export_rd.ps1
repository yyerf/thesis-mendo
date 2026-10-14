$taskDoc = Join-Path (Get-Location).Path 'thesis-13-results-discussion-iteration-1-highlighted.docx'
$taskPdf = Join-Path (Get-Location).Path '.tmp/rd-preview.pdf'
$taskWord = $null
$taskOpened = $null
try {
    $taskWord = New-Object -ComObject Word.Application
    $taskWord.Visible = $false
    $taskWord.DisplayAlerts = 0
    $taskWord.AutomationSecurity = 3
    $taskOpened = $taskWord.Documents.Open($taskDoc, $false, $true, $false)
    $taskOpened.Repaginate()
    $taskOpened.ExportAsFixedFormat($taskPdf, 17)
    Write-Output ('Pages: ' + $taskOpened.ComputeStatistics(2))
    $taskOpened.Close(0)
    $taskOpened = $null
} finally {
    if ($null -ne $taskOpened) { $taskOpened.Close(0) }
    if ($null -ne $taskWord) { $taskWord.Quit(0) }
}
