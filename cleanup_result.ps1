# Check disk space after cleanup
$result = ""
$result += "=== KAPASITAS DISK SETELAH CLEANUP ===`r`n"
Get-Volume | Where-Object { $_.DriveLetter } | ForEach-Object {
    $letter = $_.DriveLetter
    $freeGB = [math]::Round($_.SizeRemaining / 1GB, 2)
    $totalGB = [math]::Round($_.Size / 1GB, 2)
    $usedPercent = if ($totalGB -gt 0) { [math]::Round((1 - $_.SizeRemaining / $_.Size) * 100, 1) } else { 0 }
    $result += "  ${letter}: $freeGB GB free / $totalGB GB total ($usedPercent% terpakai)`r`n"
}
$result | Out-File -FilePath "C:\Users\Arvy Kairi\Desktop\bot\kabot\cleanup_report.txt" -Encoding UTF8
Write-Host $result
