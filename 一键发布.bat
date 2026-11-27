@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   SHF 雷达 · 推送到 GitHub
echo ============================================
echo.

set GHUSER=%~1
if "%GHUSER%"=="" set GHUSER=mudengPZ
set REPO=shf-radar
set PX=http://127.0.0.1:7890

echo 目标仓库: https://github.com/%GHUSER%/%REPO%
echo 代理地址: %PX%  （Clash 默认端口，若不用代理可忽略）
echo.

git remote remove origin 2>nul
git remote add origin https://github.com/%GHUSER%/%REPO%.git
git branch -M main

echo [1/3] 检查到 GitHub 的连通性...
git -c http.proxy=%PX% -c https.proxy=%PX% ls-remote --heads origin >nul 2>&1
if not errorlevel 1 (
  echo     经代理连通，开始推送。
  git -c http.proxy=%PX% -c https.proxy=%PX% push -u origin main
  goto result
)

echo     代理不通，改用直连...
git ls-remote --heads origin >nul 2>&1
if not errorlevel 1 (
  echo     直连可用，开始推送。
  git push -u origin main
  goto result
)

echo.
echo 两条路都不通。请确认：
echo   1. 代理软件是否在运行（本脚本按 7890 端口探测）
echo   2. 能否用浏览器打开 https://github.com
echo.
pause
exit /b 1

:result
if errorlevel 1 (
  echo.
  echo 推送失败。常见原因：
  echo   1. 仓库还没建，或仓库名不是 %REPO%
  echo   2. 用户名填错（本脚本默认 mudengPZ，可拖拽时传入）
  echo   3. 弹出的 GitHub 登录窗口被关掉了，重跑本脚本即可
  echo.
  pause
  exit /b 1
)

echo.
echo ============================================
echo   推送成功
echo ============================================
echo.
echo 还差两步，都在网页上点：
echo.
echo   第 1 步 打开 https://github.com/%GHUSER%/%REPO%/settings/pages
echo            Source 选 GitHub Actions，点 Save
echo.
echo   第 2 步 打开 https://github.com/%GHUSER%/%REPO%/settings/secrets/actions
echo            New repository secret
echo            Name 填 XIANYU_STATE
echo            Secret 粘贴 tools\state.b64 的全部内容
echo            （这个文件 6.7 KB，能存进去；旧的 state.b64 有 180 KB 会被拒）
echo.
echo 网址: https://%GHUSER%.github.io/%REPO%/
echo     首次发布约 1-2 分钟生效
echo.
pause
