# StrandsAgent-Mem0

带**短期 + 长期记忆**能力的 AI Agent 参考实现。应用层用 [Strands Agents SDK](https://strandsagents.com/)，长期记忆用 [Mem0](https://mem0.ai/)，数据面全部落到 AWS。

**目标区域**：AWS 中国区（`cn-north-1` / `cn-northwest-1`）。CloudFormation 模板跨分区可移植（用 `AWS::URLSuffix` / `AWS::Partition`），**同一份 YAML 也能部署到 AWS 海外区**（`us-east-1` 等），方便开发验证。

**已实测组合**（us-east-1 全链路 7/7 通过）：Bedrock Claude Sonnet 4.5 + Bedrock Titan Embed v2 + Aurora PostgreSQL 16.14 (pgvector 0.8.2) + S3 SessionManager + Strands 1.50.2 + Mem0 2.0.15。

**版本要求**
- Python **3.11**（Amazon Linux 2023 的 `python3.11` 包；系统自带 python3.9 保留给 aws CLI/dnf 使用）
- `strands-agents >= 1.50.2`
- `mem0ai >= 2.0.15`

## 选一条路径

| 场景 | 走这条 | 时间 | 前置 |
|------|-------|------|------|
| 只想跑 demo 看效果 | [→ 本地试玩](#本地试玩免-aws-10-分钟) | ~10 分钟 | Docker + Python 3.11 + 一个 LLM API Key |
| 上云做 POC / 生产 | [→ AWS 完整部署](#aws-完整部署已实测) | ~20 分钟 | AWS 账号 + VPC/子网 + AWS CLI + SSM 插件 |
| 接入到已有项目 | [→ 作为库嵌入](#作为库嵌入已有项目) | 视情况 | — |

## 架构

```
┌──────────────────────────────────────────────────────────────┐
│  Strands Agent  (OpenAIModel / BedrockModel)                 │
│  Tools:  remember  ·  recall  ·  forget  + 业务工具           │
└───────────────────┬────────────────────────┬─────────────────┘
                    │                        │
            短期记忆 │                        │ 长期记忆
                    ▼                        ▼
   ┌──────────────────────────┐   ┌────────────────────────────┐
   │ Strands 内置              │   │ Mem0 v2                    │
   │  SlidingWindow (窗口)     │   │  ├─ LLM (抽取事实)         │
   │  + S3SessionManager       │   │  ├─ Embedder (向量化)      │
   │    (完整会话持久化)        │   │  └─ Vector Store           │
   │                          │   │      Aurora PG + pgvector  │
   │  本地开发可切               │   │      (可选: OpenSearch)    │
   │  FileSessionManager       │   │                            │
   └──────────────────────────┘   └────────────────────────────┘
```

**记忆分工**

| 层 | 后端 | 数据 | 生命周期 | 检索方式 |
|----|------|------|---------|---------|
| 短期 (in-context) | 内存 SlidingWindow | 最近 N 条完整消息 | 会话内 | 直接进 LLM 上下文 |
| 短期持久化 | S3 | 完整消息 JSON | 30 天 (S3 lifecycle) | 按 `session_id` 拉取 |
| 长期 | Aurora PG + pgvector (HNSW) | Mem0 抽取的事实 | 持久 | 融合评分（语义+BM25+实体）|

Agent 通过 `remember` / `recall` / `forget` 工具**主动**管理长期记忆——不是每轮强制注入，而是模型判断"值得记住"或"需要唤起"时才调用。

## 支持的 Provider

**LLM**（走 OpenAI 兼容协议或 Bedrock）

| Provider | Base URL / 说明 | 常用模型 |
|----------|--------|---------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat`, `deepseek-reasoner` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-max`, `qwen-plus`, `qwen-turbo` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-plus`, `glm-4` |
| OpenAI 直连 | `https://api.openai.com/v1` | `gpt-4o`, `gpt-4o-mini` |
| Amazon Bedrock | 走 boto3 (**海外区可用**) | `us.anthropic.claude-sonnet-4-5-*`, `us.amazon.nova-pro-v1:0` |

**Embedding**

| Provider | 常用模型 | 维度 |
|----------|---------|-----|
| 通义千问 | `text-embedding-v3` | 1024 |
| 智谱 | `embedding-3` | 2048 |
| OpenAI | `text-embedding-3-small` / `-large` | 1536 / 3072 |
| Bedrock | `amazon.titan-embed-text-v2:0` | 1024 |

> **中文场景注意**：Bedrock Titan Embed v2 是英文优先，跨语言语义匹配偏弱（实测中文问题 "工作" 匹配英文事实 "frontend engineer" 命中率不高）。中文生产建议用 **Qwen `text-embedding-v3`** 或自托管 **BGE-M3**。

## 目录结构

```
StrandsAgent-Mem0/
├── config/
│   ├── settings.py             # 环境变量 → pydantic 配置对象
│   └── mem0_config.py          # 构造 Mem0 config dict (LLM/Embedder/VectorStore)
├── memory/
│   ├── long_term.py            # Mem0 长期记忆薄封装 (add / search / delete)
│   └── session.py              # Strands S3SessionManager + SlidingWindow 组装
├── agents/
│   ├── memory_tools.py         # @tool: remember / recall / forget
│   └── memory_agent.py         # 拼装 Agent (OpenAIModel 或 BedrockModel)
├── examples/
│   ├── basic_chat.py           # 单用户跨 session 记忆演示
│   ├── multi_user.py           # 多用户记忆隔离演示
│   └── direct_memory_api.py    # 绕过 Agent 直接用 Mem0
├── infrastructure/
│   ├── cloudformation/memory-infra.yaml   # S3 + Aurora Serverless v2 + EC2 + IAM
│   ├── pgvector_bootstrap.sql             # CREATE EXTENSION vector
│   └── bootstrap.sh                       # EC2 上装 venv + 依赖
├── validate.py                 # 端到端 7 步连通性校验脚本
├── app.py                      # 交互式 CLI
├── requirements.txt
└── .env.example
```

## 本地试玩（免 AWS，10 分钟）

适合：想快速看看跨 session 记忆是什么样，不想开云资源。

**前置**：Docker、Python 3.11、一个 LLM API Key（DeepSeek / OpenAI / 通义千问 任一）。

```bash
# 1. 克隆代码 + 装依赖
git clone <this-repo> && cd StrandsAgent-Mem0
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 本地起 pgvector (postgres + 扩展)
#    <YOUR_LOCAL_PG_PWD> 换成一个自己起的字母数字密码, 记住给 .env 用
docker run -d --name mem0-pg \
    -e POSTGRES_PASSWORD=<YOUR_LOCAL_PG_PWD> \
    -e POSTGRES_DB=mem0 \
    -p 5432:5432 \
    pgvector/pgvector:pg16
sleep 5
docker exec mem0-pg psql -U postgres -d mem0 -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 3. 配置 .env
cp .env.example .env
```

编辑 `.env`，改成这几行（其余保持 example 默认）：

```bash
# 用你有的 API Key,以 DeepSeek 为例
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-your-deepseek-key
LLM_MODEL=deepseek-chat

# Embedding: 用通义千问 (DeepSeek 官方没 embedding)
EMBEDDER_PROVIDER=qwen
EMBEDDER_API_KEY=sk-your-dashscope-key
EMBEDDER_MODEL=text-embedding-v3
EMBEDDER_DIMS=1024

# 短期记忆走本地文件
SESSION_BACKEND=file
SESSION_FILE_DIR=./.sessions

# 长期记忆走本地 pgvector 容器
VECTOR_STORE_PROVIDER=pgvector
PGVECTOR_HOST=localhost
PGVECTOR_PASSWORD=<YOUR_LOCAL_PG_PWD>   # 跟上一步 docker run 时填的一致
PGVECTOR_DBNAME=mem0
PGVECTOR_SSLMODE=disable
```

```bash
# 4. 验证 + 试聊
python validate.py       # 7 项检查应该全绿
python app.py --user alice
```

清理：`docker rm -f mem0-pg && rm -rf .sessions`

## AWS 完整部署（已实测）

以下步骤已在 **us-east-1** 用 Bedrock + Aurora 走通 7/7 验证。中国区流程一致，只需换 `--region` 和 VPC/Subnet，并把 `.env` 里 LLM/Embedding 换成 DeepSeek/Qwen。

**前置**：
- AWS 账号 + IAM 权限（CloudFormation / EC2 / RDS / S3 / IAM / SSM）
- 至少一个 VPC，含 2 个位于不同 AZ 的子网
- 本地装好 `aws` CLI 和 SSM Session Manager 插件：
  ```bash
  # macOS
  brew install --cask session-manager-plugin
  # 其他平台: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
  ```
- 把这份代码推到你能访问的 git repo（GitHub 私有 / CodeCommit / GitLab 都行），EC2 从那里 clone

### 1. 部署基础设施

一次拉起 **VPC + S3 + Aurora Serverless v2 + EC2 (Amazon Linux 2023) + SG + IAM**。EC2 带 SSM Session Manager，免 SSH 密钥。

```bash
# 生成一个强随机密码 (纯字母数字, 24 字符)
DB_PWD=$(python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24)))")
```

> **栈名 = 资源前缀**。所有资源命名（S3 bucket / IAM role / Aurora 等）以栈名为前缀。多栈共存时，只需要栈名不同即可，无需其他配置。

**无脑一键（默认自建 VPC + subnet + IGW）**

```bash
aws cloudformation deploy \
  --stack-name strands-mem0 \
  --template-file infrastructure/cloudformation/memory-infra.yaml \
  --region us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      DBMasterPassword="$DB_PWD" \
      EnableBedrockAccess=true         # 海外区用 Bedrock 时开启; 中国区留 false
```

CFN 会自动创建 `10.99.0.0/16` VPC + 2 个 public subnet + IGW，全免费资源。

**复用已有 VPC（企业环境推荐）**

```bash
aws cloudformation deploy \
  --stack-name strands-mem0 \
  --template-file infrastructure/cloudformation/memory-infra.yaml \
  --region us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      CreateNewVpc=false \
      VpcId=vpc-xxxx \
      DBSubnetIds=subnet-aaaa,subnet-bbbb \
      EC2SubnetId=subnet-public-cccc \
      DBMasterPassword="$DB_PWD" \
      EnableBedrockAccess=true
```

保存下密码（后面 `.env` 要用）：
```bash
echo "生成的 DB 密码: $DB_PWD"
```

> **⚠️ 密码规则**：`DBMasterPassword` 只能是字母数字（CFN `AllowedPattern` 已强制）。
> Mem0 的 pgvector 后端内部把密码拼成 PostgreSQL URI，若含 `#` `!` `@` `/` `:` `?` `&` `=` `%` 等 URL 保留字符会被截断，出现 `password authentication failed`。

> **⚠️ Aurora 引擎版本**：默认 `PostgresEngineVersion=16.14`。若报 `Cannot find version X.Y for aurora-postgresql`，用当区可用版本覆盖：
> ```bash
> aws rds describe-db-engine-versions --region us-east-1 --engine aurora-postgresql \
>   --query 'DBEngineVersions[].EngineVersion'
> ```

关键 Outputs：
- `SessionBucketName` — 后面 `.env` 里填
- `DBWriterEndpoint` — Aurora 写节点
- `AppInstanceId` — EC2 实例 ID
- `SessionManagerLoginCmd` — 直接复制执行即可登进 EC2

### 2. 登录 EC2（免 SSH 密钥）

```bash
aws ssm start-session --target <AppInstanceId> --region us-east-1
```

### 3. 传代码 + 初始化环境

在 EC2 上：

```bash
# SSM 默认登入用户是 ssm-user, 但 /opt/strands-mem0 属主是 ec2-user。
# 先切到 ec2-user 的 login shell (PATH/HOME/权限一次到位):
sudo -u ec2-user -i
cd /opt/strands-mem0

# 传代码 (选一):
#  A. 已推到 git repo:
git clone https://your-repo/StrandsAgent-Mem0.git .
#  B. 通过 S3 中转:
#     本地: tar czf code.tgz . && aws s3 cp code.tgz s3://<bucket>/code.tgz
#     EC2:  aws s3 cp s3://<bucket>/code.tgz . && tar xzf code.tgz

bash infrastructure/bootstrap.sh    # 建 venv (python3.11)、装依赖、生成 .env 模板
```

### 4. 配置 `.env`

`.env.example` 已经列全变量。**推荐三种预设**：

<details>
<summary><b>海外区 · Bedrock（已实测 7/7 通过）</b></summary>

```bash
LLM_PROVIDER=bedrock
LLM_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_REGION=us-east-1

EMBEDDER_PROVIDER=bedrock
EMBEDDER_MODEL=amazon.titan-embed-text-v2:0
EMBEDDER_DIMS=1024

AWS_REGION=us-east-1
SESSION_BACKEND=s3
SESSION_S3_BUCKET=<CFN 输出的 SessionBucketName>

VECTOR_STORE_PROVIDER=pgvector
PGVECTOR_HOST=<CFN 输出的 DBWriterEndpoint>
PGVECTOR_USER=postgres
PGVECTOR_PASSWORD=<CFN 参数里填的密码>
PGVECTOR_DBNAME=mem0
PGVECTOR_SSLMODE=require
```
</details>

<details>
<summary><b>海外区 · OpenAI 直连</b></summary>

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

EMBEDDER_PROVIDER=openai
EMBEDDER_API_KEY=sk-...
EMBEDDER_BASE_URL=https://api.openai.com/v1
EMBEDDER_MODEL=text-embedding-3-small
EMBEDDER_DIMS=1536

# 其余 AWS 相关同上
```
</details>111

<details>
<summary><b>中国区 · DeepSeek + 通义千问</b></summary>

```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-your-deepseek-key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

EMBEDDER_PROVIDER=qwen
EMBEDDER_API_KEY=sk-your-dashscope-key
EMBEDDER_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDER_MODEL=text-embedding-v3
EMBEDDER_DIMS=1024

AWS_REGION=cn-northwest-1
# 其余 AWS 相关同上
```
</details>

### 5. 启用 pgvector 扩展（只需一次）

```bash
source .env
PGPASSWORD="$PGVECTOR_PASSWORD" psql \
    -h "$PGVECTOR_HOST" -U "$PGVECTOR_USER" -d "$PGVECTOR_DBNAME" \
    -f infrastructure/pgvector_bootstrap.sql
```

### 6. 端到端校验

```bash
source .venv/bin/activate
python validate.py
```

`validate.py` 会依次检查 7 项：`.env` → LLM → Embedding → S3 → Aurora + pgvector → Mem0 add/search → Strands Agent 一轮对话。全绿即打通。

### 7. 试聊 / 跑示例

```bash
python app.py --user alice                # 交互式 CLI
PYTHONPATH=. python examples/basic_chat.py   # 跨 session 记忆演示
PYTHONPATH=. python examples/multi_user.py   # 多用户记忆隔离
```

> `examples/` 里的脚本没做 sys.path 处理，需要用 `PYTHONPATH=.` 从项目根运行。或者用 `python -m` 也行，`app.py` 本身在根目录不受影响。

## 作为库嵌入已有项目

只需三步：

```python
# 1. 复制 config/ + memory/ + agents/ 到你项目, 或作为子模块引入
# 2. .env 里填好 LLM / Embedder / VectorStore / Session 配置
# 3. 在你的代码里:
from agents import build_memory_agent

agent = build_memory_agent(
    session_id="my-session-42",     # 每次会话唯一
    user_id="user-1024",            # 长期记忆按此隔离
    agent_id="customer-support-bot", # 多机器人场景可用
    system_prompt="你的业务 prompt...",
    extra_tools=[my_business_tool_1, my_business_tool_2],  # 你自己的工具
)

response = agent("用户输入")
print(response)
```

`build_memory_agent` 内部已经装配好：
- 主 LLM（OpenAIModel 或 BedrockModel）
- 长期记忆（Mem0 → Aurora PG / OpenSearch）
- 短期记忆（Strands SessionManager → S3 / File）
- `remember` / `recall` / `forget` 工具

对话完 Agent 会自动决定要不要写长期记忆，也会自动从长期记忆里检索。跨进程/跨机器重启后，只要 `session_id` 和 `user_id` 一致就能续上。

## 已实测记忆行为示例

Session 1（Alice 首次对话）：
```
>>> 我叫 Alice，是一名前端工程师，喜欢用 TypeScript。
[Tool: remember] → 已写入长期记忆
>>> 顺便再告诉你，我不喜欢吃香菜。
[Tool: remember] → 已写入长期记忆
```

Mem0 抽取出的事实（存在 Aurora PG）：
```
- User's name is Alice and works as a frontend engineer
- Alice prefers using TypeScript for frontend development
- Alice does not like eating cilantro (香菜)
```

Session 2（**全新 session，同一 user_id**）：
```
>>> 我不吃什么?
[Tool: recall] → hit: "Alice does not like eating cilantro"
"我记得你不吃香菜！"
```

## 切换向量库到 OpenSearch

改 `.env` 一行，代码无需改：

```bash
VECTOR_STORE_PROVIDER=opensearch
OPENSEARCH_HOST=vpc-xxxxx.es.amazonaws.com
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=xxx
```

## 清理资源

```bash
# 1. S3 bucket 因 DeletionPolicy: Retain 不会自动删,先清内容
BUCKET=$(aws cloudformation describe-stacks --stack-name strands-mem0 --region us-east-1 \
    --query 'Stacks[0].Outputs[?OutputKey==`SessionBucketName`].OutputValue' --output text)
aws s3 rm "s3://$BUCKET" --recursive --region us-east-1
aws s3api delete-bucket --bucket "$BUCKET" --region us-east-1

# 2. 删栈 (Aurora 因 DeletionPolicy: Snapshot 会留最终快照)
aws cloudformation delete-stack --stack-name strands-mem0 --region us-east-1
aws cloudformation wait stack-delete-complete --stack-name strands-mem0 --region us-east-1

# 3. (可选) 删 Aurora 最终快照
aws rds describe-db-cluster-snapshots --region us-east-1 \
    --query 'DBClusterSnapshots[?contains(DBClusterSnapshotIdentifier, `strands-mem0`)].DBClusterSnapshotIdentifier'
aws rds delete-db-cluster-snapshot --region us-east-1 \
    --db-cluster-snapshot-identifier <snapshot-id>
```

## 成本参考（us-east-1，POC 规模）

- Aurora Serverless v2 (0.5-2 ACU) ≈ **$1.5-3 / 天**
- EC2 t3.small ≈ **$0.5 / 天**
- S3 存储 & 请求：可忽略
- Bedrock 调用：按 token 计费

