from rag_construct import create_rag_tool

search = create_rag_tool()

test_queries = [
    "梅林有哪些技能",
    "术呆毛的技能效果",
    "奥伯龙宝具效果",
    "孔明充能技能",
    "杀狐技能",
    "暴击威力提升的levels"
]

for q in test_queries:
    print(f"\n{'='*60}")
    print(f"查询：{q}")
    print(f"{'='*60}")
    result = search(q)
    print(result.get("output", "无结果"))
