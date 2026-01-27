@echo off
title BATIK LAUNCHER
echo Memeriksa Sistem BATIK...

REM --- 1. Pindah ke Direktori Kerja ---
cd /d "%~dp0"

REM --- 2. Cek apakah Streamlit sudah jalan di Port 8501 ---
netstat -an | find "8501" >nul
if %errorlevel%==0 (
    echo Server sudah berjalan. Membuka Aplikasi...
    goto OPEN_APP
)

REM --- 3. Jika belum jalan, Nyalakan Streamlit (Background) ---
echo Menyalakan Server Batik (Tunggu sebentar)...
start /B pythonw -m streamlit run dashboard.py --server.headless true

REM --- 4. Beri waktu server untuk booting (5 detik) ---
timeout /t 5 /nobreak >nul

:OPEN_APP
REM --- 5. Buka Chrome App ---
echo Membuka Dashboard...
start "" "C:\Program Files\Google\Chrome\Application\chrome_proxy.exe" --profile-directory=Default --app-id=fkkhajlpfoflidlepdpofgkmlcgcobng

exit