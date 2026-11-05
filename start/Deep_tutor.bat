@echo off
:: 1. 进入项目目录
X:
cd X:\AI\DeepTutor-main

:: 2. 激活 Conda 环境 (请确保你的 conda 已经加入环境变量，或者使用绝对路径)
:: 如果是 Miniconda，通常路径如下：
call D:\miniconda\Scripts\activate.bat deeptutor_env

:: 3. 启动 Web 服务
echo DeepTutor 正在启动，请稍后...
python scripts/start_web.py

pause