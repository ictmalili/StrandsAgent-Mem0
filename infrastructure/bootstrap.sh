#!/usr/bin/env bash
# EC2 上首次准备环境的引导脚本。
# 前置: 已通过 git clone 或 scp 把仓库放到 /opt/strands-mem0 (或当前目录)。
#
# 用法:
#   bash infrastructure/bootstrap.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "[bootstrap] 项目目录: $REPO_DIR"

# 1) Python 虚拟环境 (显式用 python3.11, 避开 AL2023 系统 python3.9)
if [[ ! -d .venv ]]; then
    echo "[bootstrap] 创建 venv"
    if command -v python3.11 >/dev/null 2>&1; then
        python3.11 -m venv .venv
    else
        python3 -m venv .venv
    fi
fi
source .venv/bin/activate

# 2) 依赖
echo "[bootstrap] 升级 pip & 安装 requirements.txt"
pip install --upgrade pip
pip install -r requirements.txt

# 3) 提示用户初始化 .env
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "[bootstrap] 已从 .env.example 生成 .env, 请编辑后再运行 validate.py"
fi

# 4) 提示 pgvector 扩展初始化
cat <<EOF

============================================================
下一步:
  1. 编辑 .env, 填入 LLM/Embedder API Key 和 CFN 输出的 AWS 资源:
       vi .env
  2. 启用 pgvector 扩展 (只需一次):
       source .env
       PGPASSWORD="\$PGVECTOR_PASSWORD" psql \\
           -h \$PGVECTOR_HOST -U \$PGVECTOR_USER -d \$PGVECTOR_DBNAME \\
           -f infrastructure/pgvector_bootstrap.sql
  3. 运行连通性校验:
       source .venv/bin/activate
       python validate.py
  4. 交互式对话:
       python app.py --user alice
============================================================
EOF
