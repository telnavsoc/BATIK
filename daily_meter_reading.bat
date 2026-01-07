@echo off
echo [INFO] Memulai Ritual Pagi BATIK (05:30 AM)...
date /t >> logs\daily_execution.log
time /t >> logs\daily_execution.log

:: 1. Masuk ke folder otak robot
cd /d "D:\eman\BATIK\bin"

:: 2. Jalankan Robot MARU (Cetak PDF)
echo [1/2] Menjalankan Robot MARU...
python robot_maru.py
echo [INFO] MARU Selesai. >> ..\logs\daily_execution.log

:: Beri napas 10 detik sebelum ganti aplikasi
timeout /t 10 /nobreak >nul

:: 3. Jalankan Robot PMDT (Baca Meter)
echo [2/2] Menjalankan Robot PMDT...
python robot_pmdt.py
echo [INFO] PMDT Selesai. >> ..\logs\daily_execution.log

echo [SUCCESS] Semua tugas pagi selesai.
:: Jendela akan menutup otomatis setelah 5 detik
timeout /t 5
exit