# PC Cache Cleanup Script
# Menampilkan space sebelum cleanup
Write-Host "=== SEBELUM CLEANUP ===" -ForegroundColor Yellow
Get-Volume | Where-Object { $_.DriveLetter } | Select-Object DriveLetter, @{N = 'FreeGB'; E = { [math]::Round($_.SizeRemaining / 1GB, 2) } }, @{N = 'TotalGB'; E = { [math]::Round($_.Size / 1GB, 2) } } | Format-Table -AutoSize

$totalFreed = 0

# 1. User Temp Files
Write-Host "`n[1/8] Membersihkan User Temp Files..." -ForegroundColor Cyan
$tempPath = $env:TEMP
$before = (Get-ChildItem $tempPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Remove-Item "$tempPath\*" -Recurse -Force -ErrorAction SilentlyContinue
$after = (Get-ChildItem $tempPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
$freed = [math]::Round(($before - $after) / 1MB, 2)
$totalFreed += $freed
Write-Host "  Dibersihkan: $freed MB"

# 2. Windows Temp
Write-Host "`n[2/8] Membersihkan Windows Temp..." -ForegroundColor Cyan
$winTemp = "C:\Windows\Temp"
$before = (Get-ChildItem $winTemp -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Remove-Item "$winTemp\*" -Recurse -Force -ErrorAction SilentlyContinue
$after = (Get-ChildItem $winTemp -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
$freed = [math]::Round(($before - $after) / 1MB, 2)
$totalFreed += $freed
Write-Host "  Dibersihkan: $freed MB"

# 3. Prefetch
Write-Host "`n[3/8] Membersihkan Prefetch..." -ForegroundColor Cyan
$prefetch = "C:\Windows\Prefetch"
$before = (Get-ChildItem $prefetch -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Remove-Item "$prefetch\*" -Recurse -Force -ErrorAction SilentlyContinue
$after = (Get-ChildItem $prefetch -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
$freed = [math]::Round(($before - $after) / 1MB, 2)
$totalFreed += $freed
Write-Host "  Dibersihkan: $freed MB"

# 4. Windows Update Cache
Write-Host "`n[4/8] Membersihkan Windows Update Cache..." -ForegroundColor Cyan
$wuCache = "C:\Windows\SoftwareDistribution\Download"
$before = (Get-ChildItem $wuCache -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Remove-Item "$wuCache\*" -Recurse -Force -ErrorAction SilentlyContinue
$after = (Get-ChildItem $wuCache -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
$freed = [math]::Round(($before - $after) / 1MB, 2)
$totalFreed += $freed
Write-Host "  Dibersihkan: $freed MB"

# 5. Thumbnail Cache
Write-Host "`n[5/8] Membersihkan Thumbnail Cache..." -ForegroundColor Cyan
$thumbPath = "$env:LOCALAPPDATA\Microsoft\Windows\Explorer"
$before = (Get-ChildItem $thumbPath -Filter "thumbcache_*" -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Remove-Item "$thumbPath\thumbcache_*" -Force -ErrorAction SilentlyContinue
$after = (Get-ChildItem $thumbPath -Filter "thumbcache_*" -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
$freed = [math]::Round(($before - $after) / 1MB, 2)
$totalFreed += $freed
Write-Host "  Dibersihkan: $freed MB"

# 6. DNS Cache
Write-Host "`n[6/8] Membersihkan DNS Cache..." -ForegroundColor Cyan
ipconfig /flushdns | Out-Null
Write-Host "  DNS Cache dibersihkan"

# 7. Recycle Bin
Write-Host "`n[7/8] Mengosongkan Recycle Bin..." -ForegroundColor Cyan
try {
    Clear-RecycleBin -Force -ErrorAction SilentlyContinue
    Write-Host "  Recycle Bin dikosongkan"
}
catch {
    Write-Host "  Recycle Bin sudah kosong atau tidak bisa diakses"
}

# 8. Browser Cache (Chrome, Edge, Firefox)
Write-Host "`n[8/8] Membersihkan Browser Cache..." -ForegroundColor Cyan
$browserCaches = @(
    "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache",
    "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Code Cache",
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache",
    "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Code Cache",
    "$env:LOCALAPPDATA\Mozilla\Firefox\Profiles"
)
$browserFreed = 0
foreach ($cache in $browserCaches) {
    if (Test-Path $cache) {
        $before = (Get-ChildItem $cache -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        Remove-Item "$cache\*" -Recurse -Force -ErrorAction SilentlyContinue
        $after = (Get-ChildItem $cache -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $browserFreed += ($before - $after)
    }
}
$freed = [math]::Round($browserFreed / 1MB, 2)
$totalFreed += $freed
Write-Host "  Dibersihkan: $freed MB"

# Summary
Write-Host "`n=== HASIL CLEANUP ===" -ForegroundColor Green
Write-Host "Total space yang dibersihkan: $totalFreed MB ($([math]::Round($totalFreed/1024,2)) GB)" -ForegroundColor Green

Write-Host "`n=== SESUDAH CLEANUP ===" -ForegroundColor Yellow
Get-Volume | Where-Object { $_.DriveLetter } | Select-Object DriveLetter, @{N = 'FreeGB'; E = { [math]::Round($_.SizeRemaining / 1GB, 2) } }, @{N = 'TotalGB'; E = { [math]::Round($_.Size / 1GB, 2) } } | Format-Table -AutoSize
