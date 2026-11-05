from pathlib import Path
from fastapi import  File, UploadFile, FastAPI, HTTPException, Request
from ingest import ingest_text
from parsers import ALLOWED_SUFFIX, extract_text
from contextlib import asynccontextmanager
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy import text
from checkpointer import PG_URI
from db import SessionLocal, engine
from graph import build_graph
from models import Conversation, Message
"""FastAPI 入口：RAG + Agent + 会话记忆。

读这个文件的顺序（很重要）：
  1. lifespan  —— 创建 checkpointer、编译图、挂到 app.state.graph
  2. app = FastAPI(lifespan=lifespan)   ← 必须在任何 @app.post 之前
  3. 路由      —— 请求到来时从 request.app.state.graph 取图
"""

# ============ 1. 生命周期 ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    # checkpointer 是异步上下文管理器，只能在事件循环里开、在这里关
    async with AsyncPostgresSaver.from_conn_string(PG_URI) as cp:
        await cp.setup()                    # 建 4 张表，幂等，每次启动都安全
        app.state.graph = build_graph(cp)   # ← app.state.graph 就是这一行挂上去的
        yield                               # 服务运行期间，cp 一直开着
    # 先退出上面的 with（关掉 checkpointer 连接），再释放数据库连接池
    await engine.dispose()

MAX_BYTES = 2 * 1024 * 1024          # 2MB

# ============ 2. 创建 app（必须在路由之前）============
app = FastAPI(title="AI Lab", lifespan=lifespan)

# ============ 3. 请求体 ============
class ChatIn(BaseModel):
    message: str
    thread_id: str | None = None      # 不传 = 新开一个会话

class ApproveIn(BaseModel):
    thread_id: str
    decision: str = "yes"             # yes 批准 / no 拒绝


# ============ 4. 两个小工具函数 ============
def conv_id_from_thread(thread_id: str | None) -> int | None:
    """thread_id 形如 conv-12，反解出 conversations.id。"""
    if not thread_id or not thread_id.startswith("conv-"):
        return None
    try:
        return int(thread_id[5:])
    except ValueError:
        return None


async def save_turn(conv_id: int, user_text: str, answer: str) -> None:
    """一轮问答落业务表，方便做会话列表、历史检索。"""
    async with SessionLocal() as s:
        s.add(Message(conversation_id=conv_id, role="user", content=user_text))
        s.add(Message(conversation_id=conv_id, role="assistant", content=answer))
        await s.commit()


# ============ 5. 对话 ============
@app.post("/agent")
async def agent_chat(body: ChatIn, request: Request):
    graph = request.app.state.graph       # 就是 lifespan 里挂上去的那张图

    # --- 事务一：只碰数据库，拿到 conv_id ---
    conv_id = conv_id_from_thread(body.thread_id)
    async with SessionLocal() as s:
        conv = None
        if conv_id:
            conv = await s.get(Conversation, conv_id)
        if conv is None:                  # 没传、或者 id 不存在，就新建
            conv = Conversation(user_id=1, title=body.message[:30])
            s.add(conv)
            await s.flush()               # flush 之后 conv.id 才有值
        conv_id = conv.id
        await s.commit()

    thread_id = f"conv-{conv_id}"         # thread_id 从业务 id 派生，两套系统天然对齐
    cfg = {"configurable": {"thread_id": thread_id}}

    # --- 事务外调图：可能要好几秒，别占着数据库连接 ---
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=body.message)]}, cfg
    )

    # --- 被审批闸门拦住 ---
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        await save_turn(conv_id, body.message, f"[待审批] {payload['message']}")
        return {"thread_id": thread_id, "status": "pending_approval",
                "approval": payload}

    answer = str(result["messages"][-1].content)
    await save_turn(conv_id, body.message, answer)
    return {"thread_id": thread_id, "status": "done", "answer": answer}

# ============ 6. 审批 ============
@app.post("/agent/approve")
async def agent_approve(body: ApproveIn, request: Request):
    graph = request.app.state.graph
    cfg = {"configurable": {"thread_id": body.thread_id}}
    st = await graph.aget_state(cfg)
    if not st.next:                       # 没有 pending 的节点，说明没有被拦住
        raise HTTPException(409, "该会话没有待审批的操作（可能已处理，或被新消息覆盖）")
    result = await graph.ainvoke(Command(resume=body.decision), cfg)
    answer = str(result["messages"][-1].content)
    conv_id = conv_id_from_thread(body.thread_id)
    if conv_id:
        await save_turn(conv_id, f"[审批] {body.decision}", answer)
    return {"thread_id": body.thread_id, "status": "done", "answer": answer}

# ============ 7. 会话列表 ============
@app.get("/conversations")
async def list_conversations():
    """列出所有会话，用来验证记忆确实按 thread_id 分开。"""
    sql = text("""
        SELECT thread_id, count(*) AS steps
        FROM checkpoints
        WHERE checkpoint_ns = ''
        GROUP BY thread_id
        ORDER BY steps DESC
        LIMIT 50
    """)
    async with engine.connect() as conn:
        rows = (await conn.execute(sql)).mappings().all()
    return [dict(r) for r in rows]



@app.get("/")
def read_root():
    return {"msg": "hello, ai-lab"}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # 1. 文件名清洗：只取最后一段，防 ../../etc/passwd 这类路径穿越
    safe_name = Path(file.filename or "untitled.txt").name

    # 2. 类型白名单
    if Path(safe_name).suffix.lower() not in ALLOWED_SUFFIX:
        raise HTTPException(400, "只支持 txt / md / pdf / docx")

    # 3. 大小限制
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(400, "文件不能超过 2MB")
    if not raw:
        raise HTTPException(400, "文件是空的")

    # 4. 解析成纯文本（PDF / Word / 纯文本统一入口）
    try:
        text = extract_text(safe_name, raw)
    except ValueError as e:
        raise HTTPException(400, str(e))


    # 5. 入库
    try:
        doc_id, n = await ingest_text(safe_name, text)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "document_id": doc_id,
        "filename": safe_name,
        "chunks": n,
        "chars": len(text),
    }
