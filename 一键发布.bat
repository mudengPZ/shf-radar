@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   SHF 猎手 · 推送到 GitHub
echo ============================================
echo.
echo 前提：已经在 GitHub 上建好一个 Public 仓库，名字叫 shf-radar
echo 地址形如 https://github.com/你的用户名/shf-radar
echo.

set /p GHUSER=请输入你的 GitHub 用户名（不带 @）:
if "%GHUSER%"=="" (
  echo 没有输入用户名，已退出。
  pause
  exit /b 1
)

git remote remove origin 2>nul
git remote add origin https://github.com/%GHUSER%/shf-radar.git
git branch -M main

echo.
echo 正在推送，稍后会弹出 GitHub 登录窗口，按提示授权即可...
echo.

git push -u origin main

if errorlevel 1 (
  echo.
  echo 推送失败。常见原因：
  echo   1. 仓库还没建，或仓库名不是 shf-radar
  echo   2. 用户名填错
  echo   3. 登录窗口被关掉了，重跑本脚本即可
) else (
  echo.
  echo 推送成功。
  echo 接下来去仓库 Settings - Pages，把 Source 改成 GitHub Actions。
  echo 网址会是 https://%GHUSER%.github.io/shf-radar/
)

echo.
pause
