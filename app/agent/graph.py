"""LangGraph 客服 Agent：工具调用 + 审批闸门 + 上下文裁剪。

图的结构：
    START → agent → (有 tool_calls?) → review → tools → agent → ... → END
                          └──────────→ END

审批分两层：
  1. review 节点：会话内的人工确认（interrupt），拦住金额 > 1000 的退款；
  2. approvals 表：提交后的后台人工审核，由 /admin 接口处理。
"""

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, trim_messages
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.message import RemoveMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt

from app.agent.tools import (
    check_approval,
    create_ticket,
    get_order_status,
    list_my_approvals,
    search_docs,
    submit_refund,
)
from app.core import config

# ---------------- 常量 ----------------
TOOLS = [
    search_docs,
    get_order_status,
    submit_refund,
    check_approval,
    create_ticket,
    list_my_approvals,
]

APPROVE_WORDS = {"yes", "y", "ok", "1", "true", "同意", "批准"}

#: 哪些工具在什么条件下必须人工审批。
#: 注意：键必须是注册进 TOOLS 的工具名，否则规则永远不会命中。
NEED_APPROVAL = {
    "submit_refund": lambda args: _as_int(args.get("amount")) > 1000,
}


def _as_int(value) -> int:
    """把模型给的参数安全转成 int；解析不了就当成危险值。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 10**9


def needs_approval(call: dict) -> bool:
    rule = NEED_APPROVAL.get(call.get("name", ""))
    if rule is None:
        return False
    try:
        return bool(rule(call.get("args") or {}))
    except Exception:
        return True          # 参数异常时宁可多问一次，也不放行


SYSTEM = """你是一名企业客服助手。规则：
1. 涉及政策、流程的问题，必须先调 search_docs 查资料，不许编。
2. 资料里没有的，回答"资料中没有提到，建议联系人工客服"。
3. 退款必须确认订单号和金额，两者都齐了才调 submit_refund。
4. 用户问退款进度又没给单号时，调 list_my_approvals。
5. 用户要求转人工、投诉，或问题无法解决时，调 create_ticket。
6. 回答控制在 150 字以内。
"""

MAX_HISTORY_TOKENS = 1200      # 送进模型的历史预算（不含 system prompt）

# ---------------- 模型 ----------------
llm = ChatOpenAI(
    model=config.MODEL,
    api_key=config.API_KEY,
    base_url=config.BASE_URL,
    temperature=0.2,
    timeout=config.LLM_TIMEOUT,
    max_retries=2,
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
        cn = sum(1 for ch in text if "一" <= ch <= "鿿")
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
    """闸门：危险操作先停下来，等人点头。

    一条 AI 消息里可能有多个 tool_calls，必须逐个确认——否则批准第一个之后，
    ToolNode 会把同一条消息里的所有调用都执行掉。
    """
    last = state["messages"][-1]
    calls = getattr(last, "tool_calls", None) or []
    risky = [c for c in calls if needs_approval(c)]
    if not risky:
        return {}             # 不危险，放行

    for call in risky:
        answer = interrupt({
            "type": "approval",
            "action": call["name"],
            "args": call.get("args", {}),
            "message": f"即将执行 {call['name']}，参数 {call.get('args', {})}，是否批准？",
        })
        if str(answer).strip().lower() not in APPROVE_WORDS:
            # 拒绝：删掉那条带 tool_calls 的 AI 消息，否则下一轮会 400
            return {"messages": [
                RemoveMessage(id=last.id),
                AIMessage(content="操作已取消（未获人工批准）。"),
            ]}
    return {}                 # 全部批准，继续去 tools


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
