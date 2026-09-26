@echo off
setlocal
set "AT_ROOT=%~dp0"
set "AT_PYTHON=%AT_ROOT%tools\venvs\seed-vc\Scripts\python.exe"
set "AT_UI=%AT_ROOT%tools\aethertune-ui.py"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

pushd "%AT_ROOT%"
if errorlevel 1 goto root_error
if not exist "%AT_PYTHON%" goto python_error
if not exist "%AT_UI%" goto ui_error

"%AT_PYTHON%" "%AT_UI%"
set "AT_EXIT=%ERRORLEVEL%"
popd
if not "%AT_EXIT%"=="0" (
    echo.
    echo [AetherTune] UI exited with code %AT_EXIT%.
    echo Review the error above.
    pause
)
endlocal & exit /b %AT_EXIT%

:root_error
echo [AetherTune] Cannot enter the project directory:
echo "%AT_ROOT%"
goto show_error

:python_error
echo [AetherTune] Seed-VC Python was not found:
echo "%AT_PYTHON%"
echo Confirm that tools\venvs\seed-vc has been created.
goto pop_and_show_error

:ui_error
echo [AetherTune] The control UI was not found:
echo "%AT_UI%"
goto pop_and_show_error

:pop_and_show_error
popd

:show_error
echo Press any key to close this window.
pause
endlocal & exit /b 2
