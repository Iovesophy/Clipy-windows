@echo off
echo Clipy for Windows - build script
echo.

:: Install dependencies
pip install -r requirements.txt
pip install pyinstaller

:: Build single-file executable
pyinstaller ^
    --noconsole ^
    --onefile ^
    --name ClipyForWindows ^
    --icon resources/icon.ico ^
    --hidden-import win32timezone ^
    --collect-all keyboard ^
    main.py

echo.
echo Build complete! Check dist\ClipyForWindows.exe
pause
