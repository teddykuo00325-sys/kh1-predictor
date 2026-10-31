@echo off
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0lamp_perf.ps1" -List
