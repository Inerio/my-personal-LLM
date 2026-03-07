@echo off
echo ============================================
echo  Gustave Code — Demarrage
echo ============================================
echo.

REM Verifier Docker
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERREUR] Docker n'est pas lance !
    echo Demarrez Docker Desktop puis relancez ce script.
    pause
    exit /b 1
)
echo [OK] Docker est lance.

REM Verifier le fichier .env
if not exist ".env" (
    echo [INFO] Fichier .env non trouve, copie depuis .env.example...
    copy .env.example .env
    echo [!] Editez le fichier .env avec vos cles API avant de continuer.
    echo     Ouvrez: %cd%\.env
    pause
)

REM Verifier les modeles Ollama
echo.
echo [INFO] Verification des modeles Ollama...
ollama list 2>nul | findstr "gustave" >nul
if %ERRORLEVEL% neq 0 (
    echo [!] Les modeles personnalises ne sont pas installes.
    echo     Lancez d'abord: setup-models.bat
    echo.
    set /p INSTALL="Voulez-vous lancer l'installation maintenant ? (O/N): "
    if /i "%INSTALL%"=="O" (
        call setup-models.bat
    )
)

REM Lancer Docker Compose
echo.
echo [INFO] Demarrage des services...
echo.
docker compose up --build -d

echo.
echo ============================================
echo  Gustave Code est lance !
echo.
echo  Frontend:  http://localhost:3000
echo  Backend:   http://localhost:8000
echo  API Docs:  http://localhost:8000/docs
echo  Ollama:    http://localhost:11434
echo  ChromaDB:  http://localhost:8001
echo.
echo  Pour voir les logs: docker compose logs -f
echo  Pour arreter:       docker compose down
echo ============================================
echo.

REM Ouvrir le navigateur
start http://localhost:3000

pause
