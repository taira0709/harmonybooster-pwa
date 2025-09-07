@echo off
setlocal
cd /d %~dp0

REM venv なければ作る
if not exist venv (
  python -m venv venv
)

REM 依存（初回だけ多少時間がかかる）
call .\venv\Scripts\activate.bat
if exist requirements.txt (
  pip install -r requirements.txt >nul 2>&1
)

REM Basic認証（必要なら値を変えてOK）
set BASIC_AUTH_USER=hbuser
set BASIC_AUTH_PASS=hb2025

REM 起動（PORTを変えたいときは set PORT=5001 など）
python app.py
