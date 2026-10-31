@echo off
chcp 65001 >nul
start "" powershell -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0launch_gui.ps1"
