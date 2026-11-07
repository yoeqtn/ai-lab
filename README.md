# AI Lab

企业客服 Agent 实验项目：FastAPI + LangGraph + RAG（pgvector）。

包含三块能力：

- **知识库 RAG**：上传 txt / md / pdf / docx → 解析 → 切块 → 向量化 → pgvector 检索
- **客服 Agent**：工具调用（查订单、查政策、提交退款）
- **人工审批 + 会话记忆**：LangGraph interrupt 闸门，checkpoint 持久化到 PostgreSQL

## 目录结构

```
.
├── app/                      # 应用代码（唯一包入口）
│   ├── main.py               # FastAPI 创建、lifespan、路由装配
│   ├── api/                  # HTTP 接口层
│   │   ├── chat.py           # /agent、/agent/approve、/conversations
│   │   ├── knowledge.py      # /、/upload
│   │   └── admin.py          # /admin/approvals...
│   ├── core/
│   │   ├── config.py         # 读取 .env（唯一配置入口）
│   │   └── db.py             # SQLAlchemy 异步引擎 / Session
│   ├── models.py             # ORM 模型
│   ├── crud.py               # 审批工单的原子状态流转
│   ├── services/             # 业务能力（与 Web 框架无关）
│   │   ├── chunking.py       # 文本切块
│   │   ├── parsers.py        # pdf/docx/txt 解析
│   │   ├── embedding.py      # 向量化
│   │   ├── ingest.py         # 切块 → 向量 → 入库
│   │   └── refund_gateway.py # 退款网关（当前为演示桩）
│   └── agent/                # LangGraph Agent
│       ├── graph.py          # 图定义：agent → review → tools
│       ├── tools.py          # 工具集
│       └── checkpointer.py   # PostgreSQL checkpoint 连接串
├── tests/                    # pytest 测试
│   ├── fixtures/             # 测试素材（员工手册.pdf）
│   ├── test_chunk.py
│   └── test_parse.py
├── scripts/                  # 手动运行的学习/演示脚本
│   ├── demo_interrupt.py     # 审批闸门演示
│   ├── demo_memory.py        # 会话记忆隔离演示
│   ├── pause.py / resume.py  # 中断与重启恢复
│   ├── init_checkpoint.py    # 初始化 checkpoint 表
│   ├── tool_demo.py          # 手写 function calling 循环
│   ├── stream_demo.py        # 流式输出与首字延迟
│   ├── check_tools.py        # 工具冒烟
│   └── scratch/              # 零散练习代码
├── alembic/                  # 数据库迁移
├── alembic.ini
├── pyproject.toml
├── .env.example
└── .gitignore
```

## 快速开始

要求：Python 3.12+、PostgreSQL（需启用 `pgvector` 扩展）。

```bash
# 1. 安装依赖
uv sync

# 2. 配置环境变量
cp .env.example .env        # Windows: copy .env.example .env
#   然后填入 DASHSCOPE_API_KEY 等真实值

# 3. 建表
uv run alembic upgrade head

# 4. 启动服务
uv run uvicorn app.main:app --reload
```

启动时会自动调用 `AsyncPostgresSaver.setup()` 建 checkpoint 表（幂等）。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/agent` | 对话（可带 `thread_id` 续聊） |
| POST | `/agent/approve` | 审批被 interrupt 拦住的操作 |
| GET | `/conversations` | 会话列表（按 checkpoint 统计） |
| POST | `/upload` | 上传文档入库（≤2MB） |
| GET | `/admin/approvals?status=pending` | 待审批退款列表 |
| POST | `/admin/approvals/{ticket_no}/decide` | 批准/拒绝 |

## 测试

```bash
uv run pytest
```

## 运行脚本

脚本统一用 `-m` 方式从项目根目录运行，例如：

```bash
uv run python -m scripts.demo_memory
uv run python -m scripts.demo_interrupt
```

## 已知问题 / 待办

- `app/agent/graph.py` 的 `NEED_APPROVAL` 用的是工具名 `"refund"`，但实际注册到
  `TOOLS` 的是 `submit_refund`，所以「金额 > 1000 自动拦截」这条规则目前不会命中
  `submit_refund`。需要确认产品规则后统一工具名。
- `refund`、`create_ticket`、`list_my_approvals` 已实现但未加入 `TOOLS`。
- `.env` 内含真实密钥；若曾分享或提交过项目，请轮换 `DASHSCOPE_API_KEY`、
  `TAVILY_API_KEY`、`LANGSMITH_API_KEY` 等。
- `db.py` 的 `echo=True` 会打印所有 SQL，生产环境应关闭。
