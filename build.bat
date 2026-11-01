@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo === [1/3] Installing requirements ===
pip install -r requirements.txt
pip install pyinstaller
echo.

echo === [2/3] Generating icon from the app logo ===
python layout_switcher.py --make-icon
echo.

rem The old exe may be locked if the app is running; retry deleting it.
set /a tries=0
:del_old
if not exist "dist\LayoutSwitcher.exe" goto build
del /f /q "dist\LayoutSwitcher.exe" >nul 2>&1
if not exist "dist\LayoutSwitcher.exe" goto build
set /a tries+=1
if %tries% GEQ 10 goto busy
timeout /t 1 /nobreak >nul
goto del_old

:busy
echo [ERROR] dist\LayoutSwitcher.exe is locked. Close the running app and try again.
pause
exit /b 1

:build
echo === [3/3] Building exe ===
pyinstaller --noconfirm --clean --onefile --noconsole --name LayoutSwitcher --icon assets\icon.ico --collect-all customtkinter layout_switcher.py
echo.
echo Done!  -^>  dist\LayoutSwitcher.exe
pause
