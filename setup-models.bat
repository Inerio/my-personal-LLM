@echo off
echo ============================================
echo  Gustave Code — Installation des modeles
echo  RTX 3080 12GB + 64GB RAM
echo  Versions NON CENSUREES (abliterated)
echo ============================================
echo.

REM Verifier qu'Ollama est installe
where ollama >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERREUR] Ollama n'est pas installe !
    echo Telechargez-le depuis: https://ollama.com/download/windows
    pause
    exit /b 1
)

echo [INFO] Ollama version:
ollama --version
echo.

REM ============================================
REM Telecharger les modeles de base
REM ============================================

echo ============================================
echo  Etape 1/4 : Telechargement des modeles
echo  Versions abliterated (non censurees)
echo ============================================
echo.

echo [1/3] Telechargement JOSIEFIED Qwen3 8B Q8_0 (Profil Rapide ~9 GB)...
ollama pull goekdenizguelmez/JOSIEFIED-Qwen3:8b-q8_0
echo.

echo [2/3] Telechargement LLaMA 3.3 70B Abliterated Q4_K_M (Profil LLaMA ~43 GB)...
ollama pull huihui_ai/llama3.3-abliterated:70b-instruct-q4_K_M
echo.

echo [3/3] Telechargement Dolphin Mixtral 8x22B Q4_0 (Profil Mixtral ~80 GB)...
echo [ATTENTION] Ce modele est tres volumineux, ~80 GB de RAM necessaires !
ollama pull dolphin-mixtral:8x22b
echo.

REM ============================================
REM Telecharger le modele d'embeddings
REM ============================================

echo [BONUS] Telechargement du modele d'embeddings (nomic-embed-text)...
ollama pull nomic-embed-text
echo.

REM ============================================
REM Creer les profils personnalises
REM ============================================

echo ============================================
echo  Etape 2/4 : Creation des profils qualite
echo ============================================
echo.

echo [1/3] Creation du profil Rapide (8B JOSIEFIED Qwen3)...
ollama create gustave-fast -f modelfiles/Modelfile-fast
echo.

echo [2/3] Creation du profil LLaMA (70B Abliterated)...
ollama create gustave-llama -f modelfiles/Modelfile-llama
echo.

echo [3/3] Creation du profil Mixtral (8x22B Dolphin)...
ollama create gustave-mixtral -f modelfiles/Modelfile-mixtral
echo.

REM ============================================
REM Verification
REM ============================================

echo ============================================
echo  Etape 3/4 : Verification
echo ============================================
echo.

echo Modeles installes:
ollama list
echo.

REM ============================================
REM Test rapide
REM ============================================

echo ============================================
echo  Etape 4/4 : Test rapide
echo ============================================
echo.

echo Test du profil Rapide (8B JOSIEFIED Qwen3)...
echo "Bonjour, reponds en une phrase." | ollama run gustave-fast
echo.

echo ============================================
echo  Installation terminee !
echo.
echo  Profils disponibles (tous non censures):
echo    gustave-fast    (8B JOSIEFIED Qwen3)
echo    gustave-llama   (70B LLaMA Abliterated)
echo    gustave-mixtral (8x22B Dolphin Mixtral)
echo.
echo  Lancez le raccourci 'Gustave Code' pour demarrer l'application
echo ============================================
pause
