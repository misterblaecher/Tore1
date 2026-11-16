$adb='C:\Users\miste\AppData\Local\Android\sdk\platform-tools\adb.exe'
$dest=$PSScriptRoot
function Tap($x,$y) { & $adb shell input tap $x $y }
function Back { & $adb shell input keyevent 4; Start-Sleep -Milliseconds 700 }
function Capture($name) {
Start-Sleep -Seconds 2
& $adb shell screencap -p /sdcard/tore.png
& $adb pull /sdcard/tore.png "$dest\$name.png" | Out-Null
& $adb shell uiautomator dump /sdcard/tore-ui.xml | Out-Null
& $adb pull /sdcard/tore-ui.xml "$dest\ui.xml" | Out-Null
[xml]$ui=Get-Content "$dest\ui.xml"
$ui.SelectNodes('//node') | Where-Object {$_.'content-desc' -or $_.text} | ForEach-Object { "$($_.'content-desc') $($_.text) $($_.bounds)" }
}
