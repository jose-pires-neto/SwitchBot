@echo off
title SwitchBot — Desktop Pet
color 0A

echo.
echo  ==========================================
echo    SwitchBot Desktop Pet
echo  ==========================================
echo.

:: Instala o Electron na primeira execucao
cd /d "%~dp0electron"
if not exist "node_modules\electron" (
    echo  [1/2] Instalando Electron ^(apenas na primeira vez^)...
    call npm install
    echo  Electron instalado com sucesso!
    echo.
)

:: Inicia o servidor Python em background
echo  [2/2] Iniciando servidor Python...
start "" /B python "%~dp0main.py"

:: Aguarda o Flask subir
timeout /t 2 /nobreak > nul

:: Abre o mascote Electron
echo  Abrindo mascote...
echo.
echo  Atalhos:
echo    Alt+Space = Mostrar/ocultar input
echo    Alt+H     = Ocultar mascote
echo    Alt+M     = Mostrar mascote
echo.
.\node_modules\.bin\electron.cmd .
