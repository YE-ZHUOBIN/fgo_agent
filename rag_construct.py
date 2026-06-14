import os
import glob
import json
from typing import List, Optional
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters  import RecursiveCharacterTextSplitter

DEFAULT_PERSIST_DIR = "./fgo_rag"
DEFAULT_EMBEDDING_MODEL = "moka-ai/m3e-small"
DEFAULT_CRAWL_DIR = "./rag_crawl_data"
DEFAULT_SAMPLE_DOCS = [
    "梅林的三技能是英雄的陪练，己方全体暴击率提升3T，星获得量提升3T。",
    "术呆毛一技能提升己方蓝卡性能3T，NP获得量提升3T。",
    "奥伯龙宝具能给己方全体加攻，并且赋予敌方宝具封印。"
]


def load_rag_texts(crawl_dir: str = DEFAULT_CRAWL_DIR) -> List[str]:
    """Read all JSON files from crawl_dir, extract rag_text fields, and split into chunks."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "；", "，"],
    )
    chunks = []
    for fpath in glob.glob(os.path.join(crawl_dir, "fgo_*.json")):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                records = json.load(f)
            if not isinstance(records, list):
                continue
            for rec in records:
                text = rec.get("rag_text")
                if text:
                    chunks.extend(text_splitter.split_text(text))
        except Exception as e:
            print(f"跳过 {fpath}: {e}")
    if not chunks:
        print(f"在 {crawl_dir} 中未找到含 rag_text 的 JSON 文件，回退到样本数据")
    return chunks


def build_rag_from_crawl_dir(
    crawl_dir: str = DEFAULT_CRAWL_DIR,
    persist_directory: str = DEFAULT_PERSIST_DIR,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
):
    """Build/rebuild vector DB from crawled rag text files."""
    embedding = HuggingFaceEmbeddings(model_name=embedding_model)
    texts = load_rag_texts(crawl_dir)
    if not texts:
        texts = DEFAULT_SAMPLE_DOCS
    os.makedirs(persist_directory, exist_ok=True)
    db = Chroma.from_texts(
        texts=texts,
        embedding=embedding,
        persist_directory=persist_directory,
    )
    print(f"向量库构建完成：{len(texts)} 个文本块 → {persist_directory}")
    return db


def build_rag_db(
    persist_directory: str = DEFAULT_PERSIST_DIR,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    sample_docs: Optional[List[str]] = None,
) -> Chroma:
    """Initialize or load a local RAG vector store."""
    embedding = HuggingFaceEmbeddings(model_name=embedding_model)

    if sample_docs is None:
        sample_docs = DEFAULT_SAMPLE_DOCS

    if not os.path.exists(persist_directory) or not os.listdir(persist_directory):
        os.makedirs(persist_directory, exist_ok=True)
        return Chroma.from_texts(
            texts=sample_docs,
            embedding=embedding,
            persist_directory=persist_directory,
        )

    return Chroma(
        persist_directory=persist_directory,
        embedding_function=embedding,
    )


def create_rag_tool(
    persist_directory: str = DEFAULT_PERSIST_DIR,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    sample_docs: Optional[List[str]] = None,
):
    """Create a RAG search function."""
    db = build_rag_db(
        persist_directory=persist_directory,
        embedding_model=embedding_model,
        sample_docs=sample_docs,
    )
    
    def search_knowledge_base(query: str) -> dict:
        """Search and retrieve relevant documents from knowledge base."""
        docs = db.similarity_search(query, k=4)
        if not docs:
            return {"output": "未找到相关信息"}
        return {"output": "\n".join([doc.page_content for doc in docs])}
    
    return search_knowledge_base


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="构建 FGO RAG 向量库")
    parser.add_argument("--crawl-dir", default=DEFAULT_CRAWL_DIR, help="爬取数据目录")
    parser.add_argument("--persist-dir", default=DEFAULT_PERSIST_DIR, help="向量库持久化目录")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="嵌入模型")
    args = parser.parse_args()

    build_rag_from_crawl_dir(
        crawl_dir=args.crawl_dir,
        persist_directory=args.persist_dir,
        embedding_model=args.embedding_model,
    )
