from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.message import RemoveMessage
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt

import settings
from tools import create_ticket, get_order_status, refund, search_docs

TOOLS = [search_docs, get_order_status, create_ticket, refund]

# 哪些工具、什么条件下必须人工审批
NEED_APPROVAL = {
    "refund": lambda args: args.get("amount", 0) > 1000,
    "create_ticket": lambda args: False,     # 建工单不危险，直接放行
}

SYSTEM = """你是一名企业客服助手。规则：
1. 涉及政策、流程的问题，必须先调 search_docs 查资料，不许编。
2. 资料里没有的，回答"资料中没有提到，建议联系人工客服"。
3. 退款必须确认订单号和金额，两者都齐了才调 refund。
4. 回答控制在 150 字以内。
"""

llm = ChatOpenAI(
    model=settings.MODEL,
    api_key=settings.API_KEY,
    base_url=settings.BASE_URL,
    temperature=0.2,
)
llm_with_tools = llm.bind_tools(TOOLS)


async def agent_node(state: MessagesState):
    messages = [SystemMessage(content=SYSTEM)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


async def review_node(state: MessagesState):
    """闸门：危险操作先停下来，等人点头。"""
    last = state["messages"][-1]
    calls = getattr(last, "tool_calls", None) or []

    risky = [c for c in calls
             if c["name"] in NEED_APPROVAL and NEED_APPROVAL[c["name"]](c["args"])]
    if not risky:
        return {}          # 不危险，放行

    # 停在这里，把要审批的内容交给调用方
    answer = interrupt({
        "type": "approval",
        "actions": [
            {"name": c["name"], "args": c["args"], "id": c["id"]}
            for c in risky
        ],
        "message": "以下操作需要审批：\n" + "\n".join(
            f"- {c['name']}({c['args']})" for c in risky
        ),
    })

    if str(answer).strip().lower() in ("yes", "y", "同意", "批准", "ok"):
        return {}          # 批准，继续去 tools

    # 拒绝：把那条带 tool_calls 的消息删掉，再补一条说明
    return {"messages": [
        RemoveMessage(id=last.id),
        AIMessage(content="操作已取消（未获人工批准）。"),
    ]}


def route_after_review(state: MessagesState):
    """放行就去 tools；被拒绝（最后一条没 tool_calls）就结束。"""
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END


def build_graph(checkpointer):
    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent_node)
    builder.add_node("review", review_node)
    builder.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))

    builder.add_edge(START, "agent")
    # 昨天是 agent → tools，今天中间插一道闸门
    builder.add_conditional_edges("agent", tools_condition, {"tools": "review", END: END})
    builder.add_conditional_edges("review", route_after_review, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer)