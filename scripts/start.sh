#!/bin/bash
# SiteGuard AI - 一键启动脚本
# 兼容: Linux / macOS / Windows (Git Bash, MSYS2)

# ── 定位项目根目录 ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# ── 检测 Windows bash 环境 ──
case "$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')" in
    mingw*|msys*|cygwin*)
        IS_WINDOWS=true
        ;;
    *)
        IS_WINDOWS=false
        ;;
esac

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
ok()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
info() { echo -e "  ${CYAN}[INFO]${NC} $1"; }

echo ""
echo "========================================"
echo "  SiteGuard AI - 工地安全风险监测系统"
echo "========================================"
if $IS_WINDOWS; then
    info "检测到 Windows Bash 环境"
fi
echo ""

# ═══════════════════════════════════════════
#  1. 环境检查
# ═══════════════════════════════════════════
echo "[1/6] 检查运行环境..."

# 查找可用的 Python（优先 python3，fallback python）
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &> /dev/null; then
        PY_VER=$("$cmd" --version 2>&1)
        if echo "$PY_VER" | grep -qE "Python 3\.[0-9]+"; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "未找到 Python 3.8+，请安装后重试"
    echo "按回车退出..."
    read
    exit 1
fi
echo "  Python  $("$PYTHON" --version 2>&1 | awk '{print $2}')"

if ! command -v node &> /dev/null; then
    fail "未找到 Node.js，请安装 Node.js 16+"
    echo "按回车退出..."
    read
    exit 1
fi
echo "  Node    $(node --version 2>&1)"

if ! command -v pnpm &> /dev/null; then
    info "pnpm 未安装，正在安装..."
    npm install -g pnpm
    if ! command -v pnpm &> /dev/null; then
        fail "pnpm 安装失败，请手动执行: npm install -g pnpm"
        echo "按回车退出..."
        read
        exit 1
    fi
fi
echo "  pnpm    $(pnpm --version 2>&1)"

ok "环境检查通过"

# ═══════════════════════════════════════════
#  2. 虚拟环境
# ═══════════════════════════════════════════
echo ""
echo "[2/6] 准备 Python 虚拟环境..."

if $IS_WINDOWS; then
    VENV_ACTIVATE="venv/Scripts/activate"
    VENV_PYTHON="$ROOT/venv/Scripts/python"
else
    VENV_ACTIVATE="venv/bin/activate"
    VENV_PYTHON="$ROOT/venv/bin/python"
fi

if [ ! -f "$VENV_ACTIVATE" ]; then
    info "正在创建虚拟环境..."
    "$PYTHON" -m venv venv
    if [ ! -f "$VENV_ACTIVATE" ]; then
        fail "虚拟环境创建失败"
        echo "按回车退出..."
        read
        exit 1
    fi
fi

# 激活虚拟环境
source "$VENV_ACTIVATE"

# 升级 pip
"$VENV_PYTHON" -m pip install --upgrade pip -q 2>/dev/null || true

echo "  虚拟环境: $VIRTUAL_ENV"
ok "虚拟环境就绪"

# ═══════════════════════════════════════════
#  3. Python 依赖
# ═══════════════════════════════════════════
echo ""
echo "[3/6] 安装 Python 依赖..."

if ! "$VENV_PYTHON" -m pip install -r requirements.txt -q 2>/dev/null; then
    # 重试一次，打印输出以便排查
    warn "静默安装失败，重试中（显示详情）..."
    "$VENV_PYTHON" -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        fail "Python 依赖安装失败"
        echo "  请手动执行: pip install -r requirements.txt"
        echo "按回车退出..."
        read
        exit 1
    fi
fi
ok "Python 依赖安装完成"

# ═══════════════════════════════════════════
#  4. 前端依赖
# ═══════════════════════════════════════════
echo ""
echo "[4/6] 安装前端依赖 (pnpm)..."

pnpm install --loglevel error 2>/dev/null || pnpm install
if [ $? -ne 0 ]; then
    fail "前端依赖安装失败"
    echo "  请手动执行: pnpm install"
    echo "按回车退出..."
    read
    exit 1
fi
ok "前端依赖安装完成"

# ═══════════════════════════════════════════
#  5. 配置文件 & 模型检查
# ═══════════════════════════════════════════
echo ""
echo "[5/6] 检查配置与模型..."

if [ ! -f ".env" ]; then
    info "正在从 .env.example 创建 .env..."
    cp .env.example .env
    info "已创建 .env，请根据需要修改配置"
else
    echo "  .env 已存在"
fi

# 模型文件检查（兼容 Windows find）
if $IS_WINDOWS; then
    MODEL_COUNT=$(find data/models -maxdepth 1 -name "*.pt" 2>/dev/null | wc -l)
else
    MODEL_COUNT=$(find data/models -maxdepth 1 -name "*.pt" 2>/dev/null | wc -l)
fi

if [ "$MODEL_COUNT" -eq 0 ] 2>/dev/null; then
    warn "data/models/ 目录下未找到 .pt 模型文件"
    echo "  请将训练好的模型放入 data/models/ 目录"
else
    echo "  模型文件: $MODEL_COUNT 个 .pt 文件"
fi

ok "配置检查完成"

# ═══════════════════════════════════════════
#  6. 启动服务
# ═══════════════════════════════════════════
echo ""
echo "[6/6] 启动服务..."

# 启动后端（后台）
echo "  启动后端 (FastAPI + uvicorn)..."
cd "$ROOT/apps/server"
"$VENV_PYTHON" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd "$ROOT"

# 等待后端就绪
sleep 3

# 检查后端是否存活
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    fail "后端启动失败，请检查: cd apps/server && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    echo "按回车退出..."
    read
    exit 1
fi

# 启动前端（后台）
echo "  启动前端 (Vite + Vue 3)..."
cd "$ROOT/apps/web"
pnpm dev &
FRONTEND_PID=$!
cd "$ROOT"

echo ""
echo "========================================"
echo "  系统启动完成！"
echo ""
echo "  前端:     http://localhost:3000"
echo "  后端:     http://localhost:8000"
echo "  API 文档:  http://localhost:8000/docs"
echo "========================================"
echo ""
echo "按 Ctrl+C 停止所有服务..."
echo ""

# ── 优雅停止 ──
cleanup() {
    echo ""
    echo "正在停止服务..."
    kill $FRONTEND_PID $BACKEND_PID 2>/dev/null
    wait $FRONTEND_PID $BACKEND_PID 2>/dev/null
    echo "服务已停止"
    exit 0
}
trap cleanup INT TERM

# 等待子进程
wait
