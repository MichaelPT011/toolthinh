@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  where python >nul 2>nul && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo Khong tim thay Python. Hay cai Python 3.11 hoac moi hon roi mo lai file nay.
  pause
  exit /b 1
)

call %PYTHON_CMD% bootstrap.py
if errorlevel 1 (
  echo Moi truong chay bi loi. Hay gui anh man hinh loi nay de duoc ho tro.
  pause
  exit /b 1
)
