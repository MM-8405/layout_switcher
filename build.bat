@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo Installing requirements...
pip install customtkinter pyperclip pillow pyinstaller
echo.

echo Building icon (from the app's own logo)...
python language_switcher.py --make-icon
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
echo Building exe...
pyinstaller --noconfirm --clean --onefile --noconsole --name LayoutSwitcher --icon icon.ico --collect-all customtkinter language_switcher.py
echo.
echo Done. Your file: dist\LayoutSwitcher.exe
pause
