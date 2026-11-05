@echo off
:: DeepTutor v1.7.1 launcher (project-local .venv)
cd /d X:\AI\DeepTutor-main

echo DeepTutor 正在启动，请稍后...
.venv\Scripts\python.exe scripts\start_web.py

pause
