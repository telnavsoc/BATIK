@echo off
title BATIK Dashboard Launcher
cd /d %~dp0
streamlit run dashboard.py
pause