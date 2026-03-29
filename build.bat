@echo off
cd /d "%~dp0"
echo.
echo [APL] Installing requirements...
pip install -r requirements.txt

echo.
echo [APL] Building standalone executable...
pyinstaller --noconfirm --onefile --windowed --name "APL" main.py

echo.
echo [APL-SEARCH] Building standalone Search-Explorer executable...
pyinstaller --noconfirm --onefile --windowed --name "APL_Search" search_main.py

echo.
echo [APL] Build complete! You can find APL.exe and APL_Search.exe in the 'dist' folder.
echo Copy both EXEs to your USB drive.
pause
