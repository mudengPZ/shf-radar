@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist tools\state.b64 (
  echo 找不到 tools\state.b64，请先运行 python tools\fetch_live.py --login
  pause
  exit /b 1
)
type tools\state.b64 | clip
echo 已复制 tools\state.b64 的全部内容到剪贴板。
echo 去仓库 Settings - Secrets and variables - Actions 新建 XIANYU_STATE，粘贴。
pause
