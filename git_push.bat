@echo off
title Git Push Helper

echo ==========================================
echo          GIT PUSH HELPER
echo ==========================================
echo.

:: Show changed files first
echo Changed / untracked files in this project:
echo ------------------------------------------
git status --short
echo ------------------------------------------
echo.

:: Ask for files to add
echo What files do you want to add?
echo   [1] All files  (git add .)
echo   [2] Specific files (pick from the list above)
echo.
set /p FILE_CHOICE="Enter 1 or 2: "

if "%FILE_CHOICE%"=="1" (
    echo.
    echo Adding all files...
    git add .
    if errorlevel 1 (
        echo ERROR: git add failed.
        pause
        exit /b 1
    )
) else if "%FILE_CHOICE%"=="2" (
    echo.
    echo Enter filenames separated by spaces.
    echo Example: agent\rag_engine.py config.py data\faqs.txt
    echo.
    set /p FILES="Files: "
    echo.
    echo Adding: %FILES%
    git add %FILES%
    if errorlevel 1 (
        echo ERROR: git add failed. Check the filenames and try again.
        pause
        exit /b 1
    )
) else (
    echo Invalid choice. Exiting.
    pause
    exit /b 1
)

echo.
echo Files staged successfully.
echo.

:: Show what's staged
echo Staged changes:
echo ------------------------------------------
git status --short
echo ------------------------------------------
echo.

:: Ask for commit message
set /p COMMIT_MSG="Enter commit message: "

if "%COMMIT_MSG%"=="" (
    echo ERROR: Commit message cannot be empty.
    pause
    exit /b 1
)

echo.
echo Committing...
git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo ERROR: git commit failed.
    pause
    exit /b 1
)

echo.
echo Pushing to remote...
git push
if errorlevel 1 (
    echo ERROR: git push failed. Check your connection or remote settings.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Done! Changes pushed successfully.
echo ==========================================
echo.
pause
