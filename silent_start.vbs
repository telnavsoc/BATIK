Set WshShell = CreateObject("WScript.Shell")

' Jalankan Watchdog dengan pythonw (Tanpa Window)
WshShell.Run "pythonw.exe " & chr(34) & "D:\eman\BATIK\bin\service_watchdog.py" & chr(34), 0

' Jalankan Tray Monitor dengan pythonw (Tanpa Window)
WshShell.Run "pythonw.exe " & chr(34) & "D:\eman\BATIK\bin\batik_tray.py" & chr(34), 0

Set WshShell = Nothing