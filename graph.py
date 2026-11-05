"""LangGraph 客服 Agent：工具调用 + 审批闸门 + 上下文裁剪。

演进轨迹：
  Day9   agent -> tools 循环
  Day10  agent -> review -> tools，compile 改成 build_graph(cp)
  Day11  agent_node 开始裁剪历史（本文件为完整版，可整份替换）
"""

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, trim_messages
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.message import RemoveMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt
from tools import check_approval, get_order_status, search_docs, submit_refund
import settings

# ---------------- 常量 ----------------
TOOLS = [search_docs, get_order_status, submit_refund, check_approval]

# 哪些工具、什么条件下必须人工审批
NEED_APPROVAL = {
    "refund": lambda args: args.get("amount", 0) > 1000,
    "create_ticket": lambda args: False,
}

SYSTEM = """你是一名企业客服助手。规则：
1. 涉及政策、流程的问题，必须先调 search_docs 查资料，不许编。
2. 资料里没有的，回答"资料中没有提到，建议联系人工客服"。
3. 退款必须确认订单号和金额，两者都齐了才调 refund。
4. 回答控制在 150 字以内。
"""

MAX_HISTORY_TOKENS = 1200      # 送进模型的历史预算（不含 system prompt）

# ---------------- 模型 ----------------
llm = ChatOpenAI(
    model=settings.MODEL,
    api_key=settings.API_KEY,
    base_url=settings.BASE_URL,
    temperature=0.2,
)
llm_with_tools = llm.bind_tools(TOOLS)


# ---------------- 中文 token 估算 ----------------
def rough_tokens(messages: list[BaseMessage]) -> int:
    """中文 1 字按 1.5 token 算，其余按 4 字符 1 token。
    trim_messages 要求 token_counter 收一个消息列表、返回整数。
    官方 approximate 是按"字符数 / 4"算的，对中文低估约 5 倍，所以自己写这个。
    """
    total = 0
    for m in messages:
        text = str(m.content or "")
        cn = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        total += int(cn * 1.5) + (len(text) - cn) // 4 + 4
    return total

# ---------------- 节点 ----------------
async def agent_node(state: MessagesState):
    # 这里裁的是"送进模型的副本"，state 里的 messages 一条都不会少
    history = trim_messages(
        state["messages"],
        max_tokens=MAX_HISTORY_TOKENS,
        token_counter=rough_tokens,
        strategy="last",          # 从最新往回留
        start_on="human",         # 切点必须落在人类消息上，否则会切出孤立 tool 消息
        include_system=False,     # system 由下面自己加，避免重复
    )
    messages = [SystemMessage(content=SYSTEM)] + history
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}

async def review_node(state: MessagesState):
    """闸门：危险操作先停下来，等人点头。"""
    last = state["messages"][-1]
    calls = getattr(last, "tool_calls", None) or []
    risky = [c for c in calls
             if c["name"] in NEED_APPROVAL and NEED_APPROVAL[c["name"]](c["args"])]
    if not risky:
        return {}             # 不危险，放行
    answer = interrupt({
        "type": "approval",
        "action": risky[0]["name"],
        "args": risky[0]["args"],
        "message": f"即将执行 {risky[0]['name']}，参数 {risky[0]['args']}，是否批准？",
    })
    if str(answer).strip().lower() in ("yes", "y", "同意", "批准", "ok"):
        return {}             # 批准，继续去 tools
    # 拒绝：删掉那条带 tool_calls 的 AI 消息，否则下一轮会 400
    return {"messages": [
        RemoveMessage(id=last.id),
        AIMessage(content="操作已取消（未获人工批准）。"),
    ]}

def route_after_review(state: MessagesState):
    """放行就去 tools；被拒绝（最后一条没有 tool_calls）就结束。"""
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END

# ---------------- 装配 ----------------
def build_graph(checkpointer):
    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent_node)
    builder.add_node("review", review_node)
    builder.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, {"tools": "review", END: END})
    builder.add_conditional_edges("review", route_after_review, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer)