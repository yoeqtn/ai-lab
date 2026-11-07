# AI Lab

企业客服 Agent 实验项目：FastAPI + LangGraph + RAG（pgvector）。

包含三块能力：

- **知识库 RAG**：上传 txt / md / pdf / docx → 解析 → 切块 → 向量化 → pgvector 检索（带租户隔离与来源）
- **客服 Agent**：工具调用（查订单、查政策、提交退款、创建工单、查审批进度）
- **人工审批 + 会话记忆**：LangGraph interrupt 闸门 + 后台退款工单，checkpoint 持久化到 PostgreSQL

> 整体设计、关键流程和取舍说明见 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**。

## 目录结构

```
.
├── app/                      # 应用代码（唯一包入口）
│   ├── main.py               # FastAPI 创建、lifespan、路由装配、/health
│   ├── api/                  # HTTP 接口层
│   │   ├── chat.py           # /agent、/agent/approve、/conversations
│   │   ├── knowledge.py      # /、/upload
│   │   └── admin.py          # /admin/approvals...
│   ├── core/
│   │   ├── config.py         # 读取 .env（唯一配置入口）
│   │   ├── db.py             # SQLAlchemy 异步引擎 / Session
│   │   └── security.py       # X-API-Key 鉴权
│   ├── models.py             # ORM 模型
│   ├── crud.py               # 审批工单的原子状态流转
│   ├── services/             # 业务能力（与 Web 框架无关）
│   │   ├── chunking.py       # 文本切块
│   │   ├── parsers.py        # pdf/docx/txt 解析
│   │   ├── embedding.py      # 批量向量化
│   │   ├── ingest.py         # 切块 → 向量 → 入库
│   │   └── refund_gateway.py # 退款网关（演示桩）
│   └── agent/                # LangGraph Agent
│       ├── graph.py          # 图定义：agent → review → tools
│       ├── tools.py          # 工具集
│       └── checkpointer.py   # PostgreSQL checkpoint 连接串
├── docs/ARCHITECTURE.md      # 架构与设计说明
├── tests/                    # pytest 测试
├── scripts/                  # 手动运行的学习/演示脚本
├── alembic/                  # 数据库迁移
├── run.py                    # 跨平台启动入口（Windows 事件循环适配）
├── docker-compose.yml        # PostgreSQL + pgvector
├── .github/workflows/ci.yml  # ruff + pytest
├── pyproject.toml
├── .env.example
└── .gitignore
```

## 快速开始

要求：Python 3.12+、Docker（或自备 PostgreSQL 并启用 `pgvector` 扩展）。

```bash
# 1. 启动数据库（pgvector/pgvector:pg16）
docker compose up -d

# 2. 安装依赖
uv sync

# 3. 配置环境变量
cp .env.example .env        # Windows: copy .env.example .env
#   然后填入 DASHSCOPE_API_KEY 等真实值

# 4. 建表（迁移会自动创建 pgvector 扩展、索引和演示用户）
uv run alembic upgrade head

# 5. 启动服务
uv run python run.py --reload
```

> Windows 上请用 `run.py`：psycopg 的异步连接不支持默认的 ProactorEventLoop，
> uvicorn 默认启动方式会在导入 app 前就创建它。`run.py` 显式指定了 Selector 循环。
> Linux/macOS 也可以直接 `uv run uvicorn app.main:app --reload`。

启动时会自动调用 `AsyncPostgresSaver.setup()` 建 checkpoint 表（幂等）。

检查服务状态：

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok","database":"up","graph":"ready"}
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/agent` | 对话（可带 `thread_id` 续聊） |
| POST | `/agent/approve` | 审批被 interrupt 拦住的操作 |
| GET | `/conversations` | 当前用户的会话列表 |
| POST | `/upload` | 上传文档入库（≤2MB） |
| GET | `/admin/approvals?status=pending` | 待审批退款列表 |
| POST | `/admin/approvals/{ticket_no}/decide` | 批准/拒绝 |
| GET | `/health` | 健康检查 |

请求头（均为可选，默认值适合本地演示）：

| 请求头 | 默认 | 用途 |
|---|---|---|
| `X-User-Id` | `1` | 会话归属；迁移会创建 id=1 的演示用户 |
| `X-Tenant-Id` | `demo` | 知识库租户隔离 |
| `X-API-Key` | 无 | 设置 `APP_API_TOKEN` 后，`/admin/*` 与 `/upload` 必须携带 |

## 审批模型

退款有两层人工把关：

1. **会话内确认**：`submit_refund` 金额 > 1000 时，LangGraph 在 `review` 节点 `interrupt`，调用方拿到 `pending_approval`，通过 `/agent/approve` 恢复。
2. **后台工单**：所有退款都会写入 `approvals` 表，由 `/admin/approvals/*` 审核；批准后调用支付网关，失败标记 `refund_failed` 等待重试。

同一订单同一时间只允许一张待审批单（部分唯一索引），审批状态用条件 `UPDATE ... RETURNING` 原子流转。

## 测试

```bash
uv run pytest -q      # 13 个测试
uvx ruff check .      # 静态检查
```

CI 在每次 push / PR 时运行 ruff + pytest。

## 运行脚本

脚本统一用 `-m` 方式从项目根目录运行，例如：

```bash
uv run python -m scripts.demo_memory
uv run python -m scripts.demo_interrupt
```

## 已知限制

- `_ORDERS` / `_TICKETS` 是进程内演示数据，多实例部署需换成真实服务。
- 鉴权是演示级：`X-User-Id` 头模拟用户，`X-API-Key` 保护管理端；生产应使用 JWT/OAuth2 + RBAC。
- 大文件入库仍同步执行；生产应改为后台任务队列。
- HTTP 接口尚未提供 SSE 流式输出（脚本中有演示）。
- 没有 RAG 效果评测集。

