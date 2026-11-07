# AI Lab 架构说明

> 面向面试/答辩的项目整体说明：它解决什么问题、怎么分层、关键流程如何运转、为什么这样设计、边界在哪里。

---

## 1. 项目定位

这是一个**企业客服 Agent**的完整演示项目，把三件事串在一条链路上：

1. **知识库 RAG**：上传 txt / md / pdf / docx，解析、切块、向量化后存入 PostgreSQL + pgvector，回答时先检索再生成。
2. **工具调用 Agent**：基于 LangGraph 的 `agent → review → tools` 循环，模型可以查订单、查政策、提交退款、创建工单。
3. **人工审批 + 会话记忆**：高风险操作在会话内中断等待确认；退款工单进入后台审批；会话状态持久化到 PostgreSQL，服务重启后仍可恢复。

定位是**学习/演示项目**，不追求生产级完备，但关键链路（多租户过滤、审批状态机、并发安全、迁移与索引）都按真实系统的思路做了。

---

## 2. 技术栈

| 层 | 选型 | 用途 |
|---|---|---|
| Web | FastAPI + Uvicorn | HTTP 接口、依赖注入、生命周期管理 |
| Agent | LangGraph + LangChain | 状态图、工具调用、interrupt 审批、checkpoint |
| LLM | 阿里云百炼（OpenAI 兼容协议） | qwen-max 对话、text-embedding 向量化 |
| 数据库 | PostgreSQL + pgvector | 业务数据、向量检索、LangGraph checkpoint |
| ORM / 迁移 | SQLAlchemy 2.x（async）+ Alembic | 异步访问、版本化迁移 |
| 质量 | pytest + ruff + GitHub Actions | 单测、静态检查、CI |

---

## 3. 总体架构

```
                        ┌──────────────────────────────┐
        浏览器 / 调用方   │  HTTP 请求                    │
                        └──────────────┬───────────────┘
                                       ▼
┌────────────────────────────────────────────────────────────────────┐
│ FastAPI（app/main.py）                                              │
│  /agent  /agent/approve  /conversations                            │
│  /upload  /admin/approvals...  /health                             │
└───────┬───────────────────────────┬────────────────────────────────┘
        │                           │
        ▼                           ▼
┌───────────────────────┐   ┌──────────────────────────────┐
│ LangGraph Agent       │   │ 知识库入库链路                │
│ app/agent/graph.py    │   │ parsers → chunking →         │
│                       │   │ embedding → ingest           │
│ START → agent         │   └──────────────┬───────────────┘
│         │ tool_calls? │                  │
│         ▼             │                  │
│      review ──interrupt──► 人工确认       │
│         │             │                  │
│         ▼             │                  │
│       tools ──────────┘                  │
└───────┬───────────────┬──────────────────┘
        │               │
        ▼               ▼
┌─────────────────┐  ┌────────────────────────────────────────────┐
│ 业务表           │  │ LangGraph checkpoint 表                     │
│ conversations   │  │ checkpoints / checkpoint_blobs / ...        │
│ messages        │  │ （由 AsyncPostgresSaver.setup() 创建）      │
│ approvals       │  └────────────────────────────────────────────┘
│ documents       │
│ chunks(向量)     │  ← 同一个 PostgreSQL 实例
└─────────────────┘
```

**一个关键点**：业务表和 checkpoint 表在同一个库里，但由两套驱动访问：
- 业务表：`asyncpg`（SQLAlchemy 异步引擎）
- checkpoint：`psycopg`（LangGraph 的 `AsyncPostgresSaver` 只接受同步风格 DSN）

`app/core/config.py` 里的 `async_database_url()` / `sync_database_url()` 负责在两者之间转换。

---

## 4. 目录与职责

```
app/
├── main.py                 # 生命周期、路由装配、/health
├── api/
│   ├── chat.py             # 对话、审批、会话列表
│   ├── knowledge.py        # 上传入库
│   └── admin.py            # 退款工单审批
├── core/
│   ├── config.py           # 唯一配置入口（.env）
│   ├── db.py               # 异步引擎 / Session
│   └── security.py         # X-API-Key 鉴权依赖
├── models.py               # ORM 模型
├── crud.py                 # 审批状态流转（条件 UPDATE，防竞态）
├── agent/
│   ├── graph.py            # 状态图、审批闸门、上下文裁剪
│   ├── tools.py            # 工具集
│   └── checkpointer.py     # checkpoint 连接串
└── services/
    ├── parsers.py          # pdf/docx/txt 解析
    ├── chunking.py         # 切块
    ├── embedding.py        # 批量向量化（并发）
    ├── ingest.py           # 切块 → 向量 → 入库
    └── refund_gateway.py   # 支付网关（演示桩）
```

设计原则：`api` 只做参数校验和编排，`services` 与 Web 框架无关，`agent` 只关心模型和工具。

---

## 5. 核心流程

### 5.1 知识入库（/upload）

```
UploadFile
  → 文件名清洗（防路径穿越）
  → 后缀白名单（txt/md/pdf/docx）
  → 大小限制（2MB）
  → extract_text：按类型分发
      · txt/md：UTF-8 → GBK 降级
      · pdf：pypdf 抽文字 + 去除页眉页脚（多页重复行）
      · docx：段落 + 表格（表格转 "a | b" 行）
  → 字数上限（MAX_UPLOAD_CHARS）
  → split_text：按空行分段，目标 400 字、重叠 80 字
  → embed_texts：10 条/批、最多 3 批并发
  → 单事务：删除同名旧文档 → 写 documents + chunks
```

**幂等**：同一 `(tenant_id, filename)` 重复上传会覆盖旧数据，避免重复检索结果。

### 5.2 检索（search_docs 工具）

```
用户问题
  → embedding
  → SELECT ... FROM chunks JOIN documents
     WHERE documents.tenant_id = 当前租户
     ORDER BY embedding <=> query_vector
     LIMIT 5
  → 过滤余弦距离 > REJECT_DISTANCE 的片段
  → 取前 3 条，带上来源文件名返回
```

- 距离用 pgvector 的 `<=>`（余弦距离 = 1 − 余弦相似度）。
- **租户过滤**放在 SQL 里，避免跨租户数据泄露。
- `chunks.embedding` 上有 HNSW 索引（`vector_cosine_ops`），数据量增大后不会退化成全表扫描。
- 返回值带来源文件名，便于追溯和展示引用。

### 5.3 Agent 图

```
START → agent ──(有 tool_calls)──→ review ──(放行)──→ tools
          ▲                          │                  │
          │                          └──(拒绝)──→ END   │
          └──────────────────────────────────────────────┘
          └──(无 tool_calls)──→ END
```

- `agent_node`：裁剪历史 → 拼 system prompt → 调 LLM。
- `review_node`：检查最后一条 AI 消息里的 `tool_calls`，命中审批规则就 `interrupt`。
- `tools`：`ToolNode(TOOLS, handle_tool_errors=True)`，工具异常会作为文本回传给模型，而不是让整张图崩掉。

**多工具调用的坑**：一条 AI 消息可能带多个 `tool_calls`。如果只审第一个，批准后 `ToolNode` 会把整条消息的所有调用都执行掉。因此 `review_node` 会**逐个 interrupt**，任何一个被拒绝就整体取消。

### 5.4 两层审批

| | 会话内闸门（interrupt） | 后台工单（approvals 表） |
|---|---|---|
| 触发 | `submit_refund` 金额 > 1000 | 所有退款提交 |
| 谁批 | 会话中的用户/客服确认意图 | 运营/风控人员 |
| 实现 | LangGraph `interrupt` + `Command(resume=...)` | 条件 `UPDATE ... RETURNING` |
| 状态 | 图暂停在 `review` 节点 | `pending → approved/rejected → refunded/refund_failed` |
| 目的 | 防止模型误操作 / 二次确认 | 企业侧资金风控 |

两者职责不同，所以保留了两层。流程：

```
用户要求退款
  → 模型调 submit_refund(amount)
  → amount > 1000 ? review 节点 interrupt → 用户确认
  → 工具写 approvals(pending)
  → 调用方拿到工单号，可随时用 check_approval / list_my_approvals 查询
  → /admin/approvals/{ticket}/decide 审核
       approved → 调支付网关 → refunded
       rejected → 终态
       网关失败 → refund_failed（留给重试任务）
```

**并发安全**：审批用 `UPDATE ... WHERE status='pending' RETURNING` 一条语句完成，两个管理员同时点批准只有一个能成功；唯一部分索引 `uq_approvals_pending_order` 保证同一订单不会出现两张待审批单。

### 5.5 会话记忆

- `thread_id` 由业务主键派生：`conv-{conversation.id}`。两套系统的会话天然对齐，不需要额外映射表。
- LangGraph 把**完整图状态**写进 checkpoint 表，用于：
  - 多轮对话（自动带历史）
  - interrupt 后恢复执行
  - 服务重启后继续
- `conversations` / `messages` 表保存**业务视角**的一轮问答，用于：
  - 会话列表展示
  - 后续的检索、审计、数据分析

**为什么要双存**：checkpoint 是“执行现场”，格式由 LangGraph 决定、不适合直接做业务查询；业务表是“对外账本”。两者职责不同，但要注意一致性——目前采用“先执行业务、再落业务表”的顺序，异常时可能少一条展示记录，不会影响可恢复性。

**上下文裁剪**：`agent_node` 用 `trim_messages` 只保留最近约 1200 token 的历史（中文按 1.5 token/字估算，官方估算对中文低估约 5 倍）。裁剪只影响送进模型的副本，checkpoint 里的完整历史不丢。

### 5.6 数据模型

```
users 1 ──── N conversations 1 ──── N messages

documents 1 ──── N chunks(embedding vector(1024))

approvals（独立工单，用 thread_id 关联对话）
  ticket_no unique
  status: pending / approved / rejected / refunded / refund_failed
  部分唯一索引：(order_id) WHERE status='pending'
```

关键索引：
- `chunks.embedding` HNSW（向量检索）
- `chunks.document_id`、`messages.conversation_id`、`conversations.user_id`（外键查询）
- `documents(tenant_id, filename)`（覆盖上传时查找旧文档）
- `approvals(thread_id)`（按会话查工单）

---

## 6. 关键设计取舍

| 决策 | 原因 | 代价 |
|---|---|---|
| `thread_id = conv-{id}` | 业务会话和 checkpoint 天然对齐，无需映射表 | 暴露了自增 id（可用随机 UUID 替代） |
| 两套数据库驱动 | asyncpg 性能好；checkpointer 只支持 psycopg | 需要维护两个 DSN 转换函数 |
| 审批分两层 | 用户确认 ≠ 企业风控 | 链路更长，需要向用户解释 |
| 历史裁剪在节点内做 | 不修改 state，checkpoint 保留完整历史 | 每次调用都要重新计算 token 估算 |
| 工具内部再校验参数 | 模型可能给出非法金额/订单号 | 少量重复校验逻辑 |
| 上传同步处理 | 实现简单，便于演示 | 大文件会阻塞请求，生产应改异步任务 |

---

## 7. 配置项

| 变量 | 默认 | 说明 |
|---|---|---|
| `LLM_MODEL` | `qwen-max` | 对话模型 |
| `DASHSCOPE_API_KEY` | 空 | 百炼 API Key（必填） |
| `EMBED_MODEL` | `qwen3.7-text-embedding` | 向量模型 |
| `EMBED_DIM` | `1024` | 向量维度，必须与 `chunks.embedding` 一致 |
| `EMBED_BATCH` | `10` | 单次请求条数上限 |
| `EMBED_CONCURRENCY` | `3` | 批量向量化并发数 |
| `DATABASE_URL` | 本地 postgres | 标准 `postgresql://` 格式 |
| `SQL_ECHO` | `false` | 是否打印 SQL |
| `REJECT_DISTANCE` | `0.55` | 检索距离阈值 |
| `MAX_INPUT_CHARS` | `4000` | 单条消息长度上限 |
| `MAX_UPLOAD_CHARS` | `200000` | 单文件解析后字符上限 |
| `APP_API_TOKEN` | 空 | 设置后 `/admin/*`、`/upload` 需 `X-API-Key` |
| `LLM_TIMEOUT` | `60` | 模型调用超时（秒） |

---

## 8. 本地运行

```bash
# 1. 启动 PostgreSQL + pgvector
docker compose up -d

# 2. 安装依赖
uv sync

# 3. 配置环境变量
cp .env.example .env      # Windows: copy .env.example .env
# 填入 DASHSCOPE_API_KEY

# 4. 建表（会先自动创建 pgvector 扩展）
uv run alembic upgrade head

# 5. 启动
uv run python run.py --reload
```

> **Windows 注意**：LangGraph 的 `AsyncPostgresSaver` 基于 psycopg 异步连接，
> 不支持 Windows 默认的 ProactorEventLoop；而 uvicorn 在导入 app 之前就创建了
> 事件循环，无法在 `app/main.py` 里补救。因此提供 `run.py`，在启动 uvicorn 前
> 把 loop factory 指定为 `SelectorEventLoop`。Linux/macOS 不受影响。
> 直接使用 `uvicorn app.main:app` 在 Windows 非 reload 模式下会启动失败。

启动时 `AsyncPostgresSaver.setup()` 会自动创建 checkpoint 表（幂等）。

### 迁移说明

- `1080f7cf2b49` 和 `9c522449fdf1` 最初由 autogenerate 生成时，误把 LangGraph 的 checkpoint 表当成多余表生成了 `DROP TABLE`。这两个迁移已修正：**不再触碰 checkpoint 表**。
  - 如果之前已经跑过旧版本迁移导致 checkpoint 表被删，重启应用会自动重建（历史会话会丢）。
- 新增迁移 `b7c1d2e3f4a5`：创建 pgvector 扩展、HNSW 索引、外键索引、级联删除、时间戳，以及演示用户 `id=1`。
- `alembic/env.py` 在跑迁移前会尝试 `CREATE EXTENSION IF NOT EXISTS vector`；没有权限时降级为警告。

---

## 9. 测试与质量

```bash
uv run pytest -q      # 当前 13 个测试
uvx ruff check .      # 静态检查
```

覆盖范围：
- 切块：长度约束、空输入
- 解析：PDF 文本抽取、乱码检查
- 审批规则：规则键必须与注册工具一致（回归测试）、金额阈值、非法金额、只读工具放行
- 路由：批准后去 tools，拒绝后结束
- 工具：订单查询、工单创建

CI（`.github/workflows/ci.yml`）在每次 push / PR 时执行 `ruff` + `pytest`。

---

## 10. 安全边界与已知限制

已做：
- 上传文件路径穿越防护、类型/大小/字数限制
- 检索按租户过滤
- 管理端与上传接口可选 API Key
- 会话归属校验（`X-User-Id`）
- 审批状态机原子更新、重复提交防护
- SQL 全部参数化；`echo` 默认关闭

尚未做（生产化清单）：
- **真正的用户体系**：目前用 `X-User-Id` 头模拟，未做 JWT/OAuth2
- **限流与配额**：`.env` 里的 `DAILY_QUOTA` 尚未接入
- **异步任务**：大文件入库、支付网关重试仍应交给队列（Celery / Arq）
- **流式输出**：`scripts/stream_demo.py` 演示了流式，但 HTTP 接口尚未提供 SSE
- **多实例部署**：`_ORDERS` / `_TICKETS` 是进程内数据，需要落库或换成真实服务
- **评测体系**：没有 RAG 命中率/答案质量评测集
- **可观测性**：有结构化日志和 `/health`，但缺少指标、Tracing 默认开启、告警

---

## 11. 后续演进

1. 接入真实订单系统与支付网关，替换演示桩数据。
2. 入库改为后台任务 + 进度查询；上传接口只负责落原始文件。
3. 增加 SSE 流式对话（`astream_events`），并处理流式中的 interrupt。
4. 用户体系与 RBAC：普通用户只能访问自己的会话，管理员才能审批。
5. RAG 增强：混合检索（BM25 + 向量）、重排、按文档/章节元数据过滤。
6. 建立评测：固定问题集 + 命中率/引用准确率/工具调用正确率。
