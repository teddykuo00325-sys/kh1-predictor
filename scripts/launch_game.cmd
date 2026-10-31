@echo off
chcp 65001 >nul
title SanOLLamp Multi-Launcher
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_game.ps1"
