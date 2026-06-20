"""
rag_graph.py — the RAG "brain"
==============================
Responsibilities:
  1. Ingest a PDF: load -> split into chunks -> embed -> store in Chroma.
  2. Define a LangGraph pipeline: retrieve -> generate.
The Streamlit app (app.py) imports and calls these; it holds no RAG logic itself.

Pieces and why:
  - PyPDFLoader (LangChain): reads a PDF into Document objects, one per page.
  - RecursiveCharacterTextSplitter: smart chunking that tries to break on
    paragraph/sentence boundaries before resorting to mid-word cuts.
  - HuggingFaceEmbeddings (all-MiniLM-L6-v2): local, free meaning-vectors.
  - Chroma: the vector store; persists to ./chroma_db so it survives restarts.
  - ChatGroq: the free LLM that writes the final answer.
  - StateGraph (LangGraph): models the flow as nodes passing a shared State dict.
"""
from typing import List, TypedDict

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

# ---------- shared, created once ----------
PERSIST_DIR = "./chroma_db"

# Local embedding model. First call downloads ~90MB, then cached.
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# One persistent Chroma collection for all uploaded papers.
vectorstore = Chroma(
    collection_name="papers",
    embedding_function=embeddings,
    persist_directory=PERSIST_DIR,
)

# Groq LLM. Reads GROQ_API_KEY from the environment. 70B open model, free tier.
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# Prompt templates per study mode. {context} and {question} get filled in.
PROMPTS = {
    "qa": "Answer the question using ONLY the context. Cite the source "
          "filename in brackets for each claim. If the answer isn't in the "
          "context, say so plainly.",
    "explain": "Explain the relevant idea from the context simply, as if "
               "teaching someone new to the field. Cite sources.",
    "quiz": "Using the context, write 4 short quiz questions that test "
            "understanding, then give the answers below. Cite sources.",
}


# ---------- 1. Ingestion ----------
def ingest_pdf(path: str, filename: str, owner: str) -> int:
    """Load -> split -> embed -> store. Returns number of chunks added.
    `owner` is the logged-in username; every chunk is tagged with it so each
    user only ever sees and searches their own papers."""
    pages = PyPDFLoader(path).load()                      # list[Document], one per page
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150
    )
    chunks = splitter.split_documents(pages)
    for c in chunks:
        c.metadata["source"] = filename   # human-readable name, for citations
        c.metadata["owner"] = owner        # who uploaded it, for isolation
    vectorstore.add_documents(chunks)
    return len(chunks)


def list_papers(owner: str) -> List[str]:
    """Distinct source filenames belonging to this user only."""
    got = vectorstore.get(where={"owner": owner}, include=["metadatas"])
    return sorted({m.get("source", "?") for m in got["metadatas"]})


# ---------- 2. The LangGraph pipeline ----------
class State(TypedDict):
    question: str
    mode: str
    owner: str                  # logged-in user; restricts search to their papers
    sources: List[str]          # optional filter: only search these papers
    context: List[Document]
    answer: str


def retrieve(state: State) -> dict:
    """Node 1: find the chunks most relevant to the question, restricted to
    the current user's papers (and optionally a chosen subset of them)."""
    # Always filter by owner so users never see each other's papers.
    conditions = [{"owner": state["owner"]}]
    if state.get("sources"):
        conditions.append({"source": {"$in": state["sources"]}})
    # Chroma needs $and when combining more than one condition.
    where = conditions[0] if len(conditions) == 1 else {"$and": conditions}

    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 5, "filter": where}
    )
    docs = retriever.invoke(state["question"])
    return {"context": docs}


def generate(state: State) -> dict:
    """Node 2: hand retrieved chunks + question to the LLM for a grounded answer."""
    context_text = "\n\n---\n\n".join(
        f"[{d.metadata.get('source','?')}]\n{d.page_content}"
        for d in state["context"]
    )
    system = PROMPTS.get(state.get("mode", "qa"), PROMPTS["qa"])
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ])
    chain = prompt | llm
    resp = chain.invoke({"context": context_text, "question": state["question"]})
    return {"answer": resp.content}


def build_graph():
    """Wire the two nodes into a runnable graph: START -> retrieve -> generate -> END."""
    g = StateGraph(State)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()


# compiled once and reused
rag_app = build_graph()


def ask(question: str, owner: str, mode: str = "qa",
        sources: List[str] | None = None):
    """Run the full pipeline, restricted to `owner`'s papers.
    Returns (answer_text, list_of_source_filenames)."""
    result = rag_app.invoke({
        "question": question,
        "owner": owner,
        "mode": mode,
        "sources": sources or [],
    })
    used = sorted({d.metadata.get("source", "?") for d in result["context"]})
    return result["answer"], used
