@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Freddy's Picks AI V8 - Windows Engineering Station
if not exist ".git" (
  echo.
  echo This folder is not a Git clone. Do not use a downloaded ZIP for engineering.
  echo Clone the repository with Git first:
  echo git clone https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data.git
  echo.
  pause
  exit /b 1
)

:menu
cls
echo ===========================================================
echo  FREDDY'S PICKS AI V8 ^| WINDOWS ENGINEERING STATION
echo ===========================================================
echo   1. First-time setup ^(Python 3.12, private .venv, tests^)
echo   2. Test every model engineering safety check
echo   3. Run NBA research on this laptop
echo   4. Run NFL research on this laptop
echo   5. Run NHL research on this laptop
echo   6. Run ALL eight sports on this laptop
echo   7. Open PHONE model control ^(signed-in GitHub^)
echo   8. Safely sync my laptop with GitHub main
echo   9. Show model project status
echo   0. Exit
echo.
echo  Champion-001: frozen. Betting picks: HOLD. No wagers.
echo.
choice /C 1234567890 /N /M "Select a number [1-9,0]: "
if errorlevel 10 goto quit
if errorlevel 9 goto status
if errorlevel 8 goto sync
if errorlevel 7 goto phone
if errorlevel 6 goto all
if errorlevel 5 goto nhl
if errorlevel 4 goto nfl
if errorlevel 3 goto nba
if errorlevel 2 goto tests
if errorlevel 1 goto setup

:setup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_setup.ps1"
goto done
:tests
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_model.ps1" -Action test
goto done
:nba
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_model.ps1" -Action run_nba
goto done
:nfl
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_model.ps1" -Action run_nfl
goto done
:nhl
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_model.ps1" -Action run_nhl
goto done
:all
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_model.ps1" -Action run_all
goto done
:phone
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_model.ps1" -Action phone
goto done
:sync
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_model.ps1" -Action sync
goto done
:status
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_model.ps1" -Action status
goto done
:done
if errorlevel 1 echo.
if errorlevel 1 echo This command did NOT finish successfully. Read the error above.
echo.
pause
goto menu
:quit
endlocal
exit /b 0
