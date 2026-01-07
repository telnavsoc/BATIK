@echo off
:: Pindah ke folder project agar Python bisa menemukan file src
cd /d "D:\eman\BATIK\"

:: Judul Terminal
title BATIK Watchdog System

:: Jalankan Script Python
:: Menggunakan 'py' agar otomatis mendeteksi Python yang terinstall
echo [BATIK] Memulai Sistem Watchdog...
py bin/service_watchdog.py

:: Jika script error/berhenti, jangan langsung tutup jendela (untuk debugging)
pause