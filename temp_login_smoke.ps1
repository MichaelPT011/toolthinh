$exe = "G:\Tool veo\veo3-safe-clone-release\build\dist\Tool_Veo3s_Thinh\Tool Veo3's Thinh.exe"
$log = "G:\Tool veo\veo3-safe-clone-release\build\dist\Tool_Veo3s_Thinh\data\logs\app.log"
$userData = "G:\Tool veo\veo3-safe-clone-release\build\dist\Tool_Veo3s_Thinh\data\chrome-user-data-bundled"

Remove-Item $log -Force -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $exe -ArgumentList "--smoke-login-browser" -PassThru
Start-Sleep -Seconds 12

$alive = $false
$exitCode = ""
if ($p) {
    $alive = -not $p.HasExited
    if (-not $alive) {
        $exitCode = $p.ExitCode
    }
}

$managedChrome = Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($userData) } |
    Select-Object ProcessId, CommandLine

Write-Output ("EXE_ALIVE={0}" -f $alive)
Write-Output ("EXE_EXITCODE={0}" -f $exitCode)
Write-Output ("MANAGED_CHROME_COUNT={0}" -f @($managedChrome).Count)
if ($managedChrome) {
    $managedChrome | Format-List
}
if (Test-Path $log) {
    Get-Content $log -Tail 200
}
else {
    Write-Output "NO_LOG"
}
