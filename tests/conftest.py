import os

# 测试不调用真实模型，但在导入 app.agent.graph 时会构造 ChatOpenAI。
# 必须在任何 app 模块被导入之前设置一个占位 key。
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
