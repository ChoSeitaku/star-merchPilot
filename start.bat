@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ===========================================================================
REM  电商运营助手 · 一键启动脚本（Windows）
REM
REM  依次完成：Python 依赖 -> 前端依赖 -> 前端构建 -> 启动后端服务
REM  依赖安装使用清华镜像（PyPI 直连在部分网络下不可用）
REM ===========================================================================

cd /d "%~dp0"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"
set "PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PORT=8004"

echo.
echo ============================================================
echo   电商运营助手 · 单品运营闭环工作台
echo ============================================================
echo.

REM ---------------------------------------------------------------- 1. Python
if not exist "%PY%" (
    echo [1/4] 未找到虚拟环境，正在创建 %VENV% ...
    where python >nul 2>nul
    if errorlevel 1 (
        echo     [错误] 未找到 python，请先安装 Python 3.12+ 并加入 PATH
        pause
        exit /b 1
    )
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo     [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
) else (
    echo [1/4] 虚拟环境已存在：%VENV%
)

REM ---------------------------------------------------------- 2. Python 依赖
echo [2/4] 检查 Python 依赖 ...
"%PY%" -c "import fastapi, uvicorn, sqlalchemy, openpyxl, jwt, multipart" >nul 2>nul
if errorlevel 1 (
    echo     正在安装依赖（使用清华镜像）...
    "%PY%" -m ensurepip --upgrade >nul 2>nul
    "%PY%" -m pip install -i %PIP_MIRROR% --timeout 60 --retries 8 --progress-bar off ^
        fastapi uvicorn sqlalchemy pydantic pydantic-settings pyjwt openpyxl python-multipart
    if errorlevel 1 (
        echo     [错误] Python 依赖安装失败，请检查网络后重试
        pause
        exit /b 1
    )
) else (
    echo     Python 依赖已就绪
)

REM ------------------------------------------------------------ 3. 前端构建
echo [3/4] 检查前端构建产物 ...
if exist "frontend\dist\index.html" (
    echo     前端已构建：frontend\dist
    set /p REBUILD=    是否重新构建前端？(y/N):
    if /i "!REBUILD!"=="y" goto :build_frontend
    goto :start_server
)

:build_frontend
where npm >nul 2>nul
if errorlevel 1 (
    echo     [警告] 未找到 npm，跳过前端构建；后端仍可运行，接口文档见 /docs
    goto :start_server
)

pushd frontend
if not exist "node_modules" (
    echo     安装前端依赖（首次较慢，请耐心等待）...
    call npm install --no-audit --no-fund
    if errorlevel 1 (
        echo     [警告] 前端依赖安装失败，跳过构建
        popd
        goto :start_server
    )
)
echo     构建前端 ...
call npm run build
if errorlevel 1 (
    echo     [警告] 前端构建失败，仅启动后端
) else (
    echo     前端构建完成：frontend\dist
)
popd

REM ------------------------------------------------------------ 4. 启动服务
:start_server
echo [4/4] 启动后端服务 ...
echo.
echo ------------------------------------------------------------
echo   访问地址：http://127.0.0.1:%PORT%
echo   接口文档：http://127.0.0.1:%PORT%/docs
echo.
echo   演示账号：
echo     admin    / admin123      管理员（全部权限）
echo     operator / operator123   运营人员（业务编辑 + 投放确认）
echo     viewer   / viewer123     查看人员（只读）
echo.
echo   首次体验建议：用 admin 登录后，在工作台点击「创建演示数据」
echo ------------------------------------------------------------
echo   按 Ctrl+C 停止服务
echo ------------------------------------------------------------
echo.

cd backend
"..\%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo 服务已停止。
pause
