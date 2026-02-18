$foundryPath = "C:\Program Files\Foundry Virtual Tabletop\Foundry Virtual Tabletop.exe"
$password = "Qvzgx025"
$delaySeconds = 30

Write-Host "Launching Foundry VTT..."
Start-Process -FilePath $foundryPath

Write-Host "Waiting $delaySeconds seconds for Foundry to load..."
Start-Sleep -Seconds $delaySeconds

Write-Host "Attempting to focus window and enter password..."
$wshell = New-Object -ComObject WScript.Shell
$wshell.AppActivate("Foundry Virtual Tabletop")
Start-Sleep -Milliseconds 500
$wshell.SendKeys($password)
Start-Sleep -Milliseconds 500
$wshell.SendKeys("{ENTER}")

Write-Host "Password entered. Foundry should be logging in."
