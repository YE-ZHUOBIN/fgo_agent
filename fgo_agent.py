from langchain_openai import ChatOpenAI
# from langchain.agents import initialize_agent, AgentExecutor, AgentType
from langchain_core.tools import tool
from rag_construct import create_rag_tool
import os
# from dotenv import load_dotenv

# load_dotenv()
# ======================
# 1. 环境变量配置
# ======================
RAG_MODEL_NAME = os.getenv("RAG_MODEL_NAME", "glm-4.7-flash")
RAG_API_KEY = os.getenv("OPENAI_API_KEY")  # 或 os.getenv("GLM_API_KEY")
RAG_API_BASE = os.getenv("OPENAI_API_BASE")  # GLM API 基础 URL
RAG_PERSIST_DIR = os.getenv("RAG_PERSIST_DIR", "./fgo_rag")
RAG_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "moka-ai/m3e-small")
RAG_TEMPERATURE = float(os.getenv("RAG_TEMPERATURE", "0.1"))
RAG_MAX_TOKENS = int(os.getenv("RAG_MAX_TOKENS", "1024"))

if not RAG_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY environment variable. Please set it first.")

# ======================
# 2. GLM 模型初始化（新 Responses API，使用 input 作为输入）
# ======================
llm = ChatOpenAI(
    model_name=RAG_MODEL_NAME,
    api_key=RAG_API_KEY,
    base_url=RAG_API_BASE,
    temperature=RAG_TEMPERATURE,
    max_tokens=RAG_MAX_TOKENS,
    verbose=False,
)

# ======================
# 3. RAG 检索工具（Mooncell 知识库）
# ======================
search_knowledge_base = create_rag_tool(
    persist_directory=RAG_PERSIST_DIR,
    embedding_model=RAG_EMBEDDING_MODEL,
)

# ======================
# 4. 自定义FGO工具
# ======================
@tool
def fgo_team_recommend(question: str) -> str:
    """用于FGO周回、副本配队、3T攻略推荐。"""
    return f"针对问题【{question}】，推荐：C呆+梅林+奥伯龙，标准蓝卡3T队。"

@tool
def query_fgo_info(question: str) -> str:
    """查询FGO从者、技能、宝具、副本信息。"""
    result = search_knowledge_base(question)
    if isinstance(result, dict):
        return result.get("output", "未找到相关信息")
    return str(result)

tools = [fgo_team_recommend, query_fgo_info]

# 系统提示词
system_prompt = """你是一个FGO游戏专家。你拥有关于从者、技能、宝具、副本的丰富知识。
使用提供的工具来帮助用户查询FGO信息和推荐配队方案。
请用中文回答用户的问题。"""

# 创建 Agent（使用 initialize_agent）
# agent = initialize_agent(tools, llm, agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION, verbose=True)
# agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)
llm_with_tools = llm.bind_tools(tools)

# ======================
# 6. 测试对话
# ======================
if __name__ == "__main__":
    print("FGO砖家Agent已启动，输入 exit 退出")
    while True:
        q = input("你：")
        if q in ["exit", "quit", "q"]:
            break
        try:
            # res = agent_executor.invoke({"input": q})
            # output = res.get("output", str(res))
            result = llm_with_tools.invoke(q)
            print("\nFGO砖家：", result, "\n")
        except Exception as e:
            print(f"Error: {e}\n")
