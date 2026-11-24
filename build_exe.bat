@echo off
title Building FishLauncher.exe
echo Installing dependencies...
python -m pip install --upgrade minecraft-launcher-lib pyinstaller

echo Compiling standalone EXE...
python -m PyInstaller --noconfirm --onefile --windowed --name "FishLauncher" launcher.py

echo.
echo Done! Your executable is located at: dist\FishLauncher.exe
pause
