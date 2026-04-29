@echo off
setlocal enabledelayedexpansion

echo.
echo  ==========================================
echo    SwitchBot — Build Executable
echo  ==========================================
echo.

:: 1. Build Python Backend
echo  [1/3] Gerando executável do Backend (Python)...
pyinstaller --noconsole --onefile --name backend main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [!] ERRO ao compilar o Python. Verifique se o PyInstaller está instalado.
    pause
    exit /b 1
)

:: Copia o executável para a raiz para o Electron encontrar
copy /Y dist\backend.exe .

:: 2. Prepare Electron
echo.
echo  [2/3] Instalando dependências do Electron...
cd electron
call npm install

:: 3. Build Electron App
echo.
echo  [3/3] Gerando aplicativo final (Electron)...
call npm run build

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [!] ERRO ao compilar o Electron.
    cd ..
    pause
    exit /b 1
)

cd ..

echo.
echo  ==========================================
echo    SUCESSO! O executável está em:
echo    electron/dist/SwitchBot...exe
echo  ==========================================
echo.
pause
