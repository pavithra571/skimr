"""
app.py — Streamlit UI
=====================
Pure Python front end. No HTML/JS. Streamlit reruns this whole script top to
bottom on every interaction, so persistent things (chat history, paper list)
live in st.session_state, which survives reruns.

RUN:  streamlit run app.py
"""
import os
import tempfile

import streamlit as st
import rag_graph   # our RAG brain
import auth        # login/signup gate

st.set_page_config(page_title="skimr — paper chat", page_icon="📄", layout="wide")

# ---------- require login before anything else ----------
# This halts the script and shows login/signup until the user is authenticated.
authenticator, name, username = auth.require_login()

# ---------- session state (survives reruns) ----------
# Reset the on-screen chat whenever the logged-in user changes, so one user
# never sees another's conversation left over in the same browser session.
if st.session_state.get("active_user") != username:
    st.session_state.active_user = username
    st.session_state.messages = []

if "messages" not in st.session_state:
    st.session_state.messages = []      # list of {role, content, sources}

# ---------- sidebar: upload + paper shelf ----------
with st.sidebar:
    st.title("📄 skimr")
    st.caption(f"Signed in as **{name}**")
    authenticator.logout("Log out", location="sidebar")
    st.divider()
    st.caption("Upload papers, then ask, explain, or quiz.")

    uploaded = st.file_uploader(
        "Add a PDF", type="pdf", accept_multiple_files=True
    )
    if uploaded:
        for uf in uploaded:
            # skip ones we've already ingested this session
            key = f"ingested_{uf.name}"
            if st.session_state.get(key):
                continue
            with st.spinner(f"Indexing {uf.name}…"):
                # Streamlit gives bytes; write to a temp file for PyPDFLoader.
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uf.getvalue())
                    tmp_path = tmp.name
                try:
                    n = rag_graph.ingest_pdf(tmp_path, uf.name, owner=username)
                    st.session_state[key] = True
                    st.success(f"{uf.name}: {n} chunks indexed")
                except Exception as e:
                    st.error(f"{uf.name}: {e}")
                finally:
                    os.unlink(tmp_path)

    st.divider()
    st.subheader("On the shelf")
    papers = rag_graph.list_papers(owner=username)
    if not papers:
        st.write("_No papers yet._")
        chosen = []
    else:
        # let the user scope questions to a subset (default: all)
        chosen = st.multiselect("Search which papers?", papers, default=papers)

    mode_label = st.radio(
        "Mode", ["Ask", "Explain simply", "Quiz me"], horizontal=False
    )
    MODE_MAP = {"Ask": "qa", "Explain simply": "explain", "Quiz me": "quiz"}
    mode = MODE_MAP[mode_label]

# ---------- main: chat ----------
st.title("Ask your papers")

# replay history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("sources"):
            st.caption("Sources: " + ", ".join(m["sources"]))

# input box pinned to the bottom
question = st.chat_input("e.g. What does this paper claim, and how is it tested?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Reading the relevant pages…"):
            try:
                answer, used = rag_graph.ask(question, owner=username, mode=mode, sources=chosen)
            except Exception as e:
                answer, used = f"Something went wrong: {e}", []
        st.markdown(answer)
        if used:
            st.caption("Sources: " + ", ".join(used))

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": used}
    )
