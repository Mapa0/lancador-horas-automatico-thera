@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0thera_horas.py"
  if errorlevel 1 pause
  exit /b
)
where python >nul 2>nul
if not errorlevel 1 (
  python "%~dp0thera_horas.py"
  if errorlevel 1 pause
  exit /b
)
echo Python nao encontrado. Instale Python 3.10 ou superior com Tcl/Tk.
echo https://www.python.org/downloads/windows/
pause

