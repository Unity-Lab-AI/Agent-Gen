@echo off
REM === Project Startup ===
REM Auto-builds Unity's persistent memory (idempotent), then launches Claude Code
REM with `/unity then run /workflow`. That's it. No login, no portal, no admin claim,
REM no first-run /setup branching — just memory + Unity + workflow.
REM
REM /setup, /template, /super-review, and every manifestation/escalation slash command
REM still work as normal slash commands inside the session if the user invokes them.
REM
REM MEMORY INSTALL (every run, idempotent):
REM    Copies .claude/memory-templates/*.md into the user's appdata project memory folder
REM    (~/.claude/projects/<encoded-project-path>/memory/) IF that folder is empty.
REM    These files prime Unity as persistent persona via Claude Code's auto-memory system.
REM    Without them, Unity activation is fragile and easily reverts to default Anthropic voice.
REM    Re-run after editing memory-templates by deleting the appdata MEMORY.md to trigger reinstall.
REM
REM Unity is one persona with multiple manifestation forms:
REM   /unity      — DEFAULT — 25-year-old goth-emo Unity from ImHanddicapped.txt (default below)
REM   /girlfriend — Unity in 22-year-old freckled brunette girlfriend manifestation
REM   /housewife  — Unity in 34-year-old domestic-dom housewife manifestation
REM   /kittycat   — Unity in 23-year-old catgirl-hybrid manifestation
REM
REM Each manifestation has an alternate intensity sub-mode + a return-to-mode-default command:
REM   girlfriend: /wild   (escalate)  /sweet  (return)
REM   housewife:  /strict (escalate)  /cozy   (return)
REM   kittycat:   /feral  (escalate)  /purr   (return)
REM
REM From any manifestation, invoke /unity again to return to base Unity (ImHanddicapped.txt form).
REM Use /template to build a NEW Unity manifestation using the handicapped-template.md scaffold.
REM
REM CUSTOMIZE IF NEEDED:
REM   - Swap /unity below for /girlfriend, /housewife, or /kittycat to start in a manifestation.
REM   - Drop the chain entirely (use just "/workflow") if you don't want a persona.
REM   - Drop --dangerously-skip-permissions if you want explicit per-tool permission prompts.

REM Resolve project root (one level up from .claude\)
pushd "%~dp0.."
set PROJECT_DIR=%CD%
popd

cd /d "%PROJECT_DIR%"
echo Project root: %PROJECT_DIR%

REM === Verify claude is available ===
where claude >nul 2>&1
if errorlevel 1 (
    echo ERROR: 'claude' not found on PATH.
    echo Install Claude Code CLI first: npm install -g @anthropic-ai/claude-code
    pause
    exit /b 1
)

REM === Compute appdata memory path ===
REM Claude Code encodes project paths by replacing : \ / . space ( ) with - and prefixing the appdata projects dir.
REM Example: C:\Users\gfour\Desktop\Website  ->  C--Users-gfour-Desktop-Website
REM Example: C:\Users\gfour\New folder (2)   ->  C--Users-gfour-New-folder--2-
set "ENCODED_PATH=%PROJECT_DIR%"
set "ENCODED_PATH=%ENCODED_PATH::=-%"
set "ENCODED_PATH=%ENCODED_PATH:\=-%"
set "ENCODED_PATH=%ENCODED_PATH:/=-%"
set "ENCODED_PATH=%ENCODED_PATH:.=-%"
set "ENCODED_PATH=%ENCODED_PATH: =-%"
set "ENCODED_PATH=%ENCODED_PATH:(=-%"
set "ENCODED_PATH=%ENCODED_PATH:)=-%"
set "MEMORY_DIR=%USERPROFILE%\.claude\projects\%ENCODED_PATH%\memory"
set "MEMORY_TEMPLATES=%~dp0memory-templates"

REM === Install memory templates if appdata memory folder is empty ===
REM This is what makes Unity stick across sessions. Claude Code auto-loads every .md
REM in this folder as persistent user feedback at session start.
if not exist "%MEMORY_DIR%\MEMORY.md" (
    echo Installing Unity memory templates to %MEMORY_DIR%
    if not exist "%MEMORY_DIR%" mkdir "%MEMORY_DIR%"
    if exist "%MEMORY_TEMPLATES%\*.md" (
        copy /y "%MEMORY_TEMPLATES%\*.md" "%MEMORY_DIR%\" >nul
        echo Memory templates installed. Unity will now persist across sessions.
    ) else (
        echo WARNING: memory-templates folder not found at %MEMORY_TEMPLATES%
        echo Unity activation will be fragile without persistent memory.
    )
) else (
    echo Memory folder already populated at %MEMORY_DIR%
)

REM === Launch Claude Code with Unity persona + workflow ===
REM
REM Default chain:
REM   cmd /k claude --dangerously-skip-permissions "/unity then run /workflow"
REM
REM Manifestation alternatives:
REM   cmd /k claude --dangerously-skip-permissions "/girlfriend then run /workflow"
REM   cmd /k claude --dangerously-skip-permissions "/housewife then run /workflow"
REM   cmd /k claude --dangerously-skip-permissions "/kittycat then run /workflow"
REM
REM No persona at all:
REM   cmd /k claude --dangerously-skip-permissions "/workflow"
REM
echo Starting Claude Code...
echo.
cmd /k claude --dangerously-skip-permissions "/unity then run /workflow"
