"""
ScholarForge_AI — Streamlit Frontend.

Provides a unified UI for:
  - Chat with the RAG-powered research assistant (SSE streaming)
  - Evaluation Dashboard with RAGAS metrics and trends
  - Document Ingestion with real-time indexing status polling
  - Document Library showing all indexed documents

Configuration:
  API_BASE_URL is read from the environment variable, making this
  deployment-friendly (Docker, Kubernetes, etc.).
"""
import os
import uuid
import json
import time

import streamlit as st
import requests
import pandas as pd

# --- Configuration ---
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")

# --- Page Config ---
st.set_page_config(
    page_title="ScholarForge AI — Research Assistant",
    layout="wide",
    page_icon="🎓",
    initial_sidebar_state="collapsed",
)

# --- Custom Styling ---
st.markdown("""
<style>
    /* Global font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0;
    }
    .sub-header {
        color: #6b7280;
        font-size: 1.1rem;
        margin-top: -10px;
        margin-bottom: 20px;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8f9ff 0%, #f0f4ff 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    [data-testid="stMetricValue"] {
        font-weight: 700;
        color: #1e293b;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 500;
    }

    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    .status-connected { background: #dcfce7; color: #166534; }
    .status-error { background: #fee2e2; color: #991b1b; }

    /* Document status badges */
    .doc-status {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .doc-indexed { background: #dcfce7; color: #166534; }
    .doc-indexing { background: #fef3c7; color: #92400e; }
    .doc-pending { background: #e0e7ff; color: #3730a3; }
    .doc-failed { background: #fee2e2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown('<p class="main-header">🎓 ScholarForge AI</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Production RAG System with Evaluation Dashboard</p>',
    unsafe_allow_html=True,
)

# --- API Health Check ---
try:
    health = requests.get(
        f"{API_BASE_URL.rsplit('/api/v1', 1)[0]}/health", timeout=3
    ).json()
    if health.get("status") == "healthy":
        st.markdown(
            '<span class="status-badge status-connected">● Connected to API</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-badge status-error">● API Unhealthy</span>',
            unsafe_allow_html=True,
        )
except Exception:
    st.markdown(
        f'<span class="status-badge status-error">'
        f"● Cannot reach API at {API_BASE_URL}</span>",
        unsafe_allow_html=True,
    )

st.divider()

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["💬 Chat", "📊 Evaluation Dashboard", "📄 Document Ingestion", "📚 Document Library"]
)


# ──────────────────────────────────────────────────────────────────────
# HELPER: Poll document statuses
# ──────────────────────────────────────────────────────────────────────
def _get_status_badge(status: str) -> str:
    """Returns an HTML badge for a document status."""
    css_class = {
        "INDEXED": "doc-indexed",
        "INDEXING": "doc-indexing",
        "PENDING": "doc-pending",
        "FAILED": "doc-failed",
    }.get(status, "doc-pending")
    emoji = {
        "INDEXED": "✅",
        "INDEXING": "⏳",
        "PENDING": "🕐",
        "FAILED": "❌",
    }.get(status, "❓")
    return f'<span class="doc-status {css_class}">{emoji} {status}</span>'


def _poll_indexing_status(job_ids: list[str], placeholder):
    """
    Polls the API for document indexing status until all documents
    are either INDEXED or FAILED. Shows real-time progress.
    """
    max_polls = 120  # Max 10 minutes at 5-second intervals
    poll_count = 0

    while poll_count < max_polls:
        try:
            statuses = requests.post(
                f"{API_BASE_URL}/documents/status/bulk",
                json=job_ids,
                timeout=5,
            ).json()
        except Exception as e:
            placeholder.warning(f"⚠️ Status check failed: {e}")
            time.sleep(5)
            poll_count += 1
            continue

        # Count statuses
        indexed = sum(1 for s in statuses if s["status"] == "INDEXED")
        failed = sum(1 for s in statuses if s["status"] == "FAILED")
        indexing = sum(1 for s in statuses if s["status"] == "INDEXING")
        pending = sum(1 for s in statuses if s["status"] == "PENDING")
        total = len(statuses)

        # Build status display
        with placeholder.container():
            # Progress bar
            completed = indexed + failed
            progress_pct = completed / total if total > 0 else 0
            st.progress(progress_pct, text=f"Indexing: {completed}/{total} complete")

            # Per-document status table
            for s in statuses:
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"📄 **{s['filename']}**")
                cols[1].markdown(
                    _get_status_badge(s["status"]), unsafe_allow_html=True
                )
                cols[2].markdown(
                    f"`{s.get('chunk_count', 0)} chunks`"
                    if s["status"] == "INDEXED"
                    else ""
                )

        # All done?
        if completed >= total:
            if failed > 0:
                st.warning(
                    f"⚠️ Indexing complete: {indexed} succeeded, {failed} failed"
                )
            else:
                st.success(
                    f"✅ All {indexed} document(s) indexed successfully!"
                )
                st.balloons()
            return

        time.sleep(5)
        poll_count += 1

    st.warning("⏱️ Status polling timed out after 10 minutes. Check the Document Library for final status.")


# ──────────────────────────────────────────────────────────────────────
# TAB 1: Chat
# ──────────────────────────────────────────────────────────────────────
with tab1:
    st.header("Research Assistant")

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display message history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask a question about your academic papers..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""

            try:
                response = requests.post(
                    f"{API_BASE_URL}/chat/stream",
                    json={
                        "session_id": st.session_state.session_id,
                        "message": prompt,
                        "stream": True,
                    },
                    stream=True,
                    timeout=120,
                )
                response.raise_for_status()

                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode("utf-8")
                        if decoded_line.startswith("data: "):
                            try:
                                data = json.loads(decoded_line[6:])
                                if "delta" in data:
                                    full_response += data["delta"]
                                    message_placeholder.markdown(
                                        full_response + "▌"
                                    )
                                elif "error" in data:
                                    st.error(f"⚠️ {data['error']}")
                                elif "metadata" in data:
                                    meta = data["metadata"]
                                    if meta.get("cache_hit"):
                                        st.caption("⚡ Served from semantic cache")
                                    else:
                                        st.caption(
                                            f"📊 Latency: {meta.get('latency_ms', '?')}ms | "
                                            f"Sources: {len(meta.get('context_chunks', []))}"
                                        )
                            except json.JSONDecodeError:
                                continue

                message_placeholder.markdown(full_response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )

            except requests.ConnectionError:
                st.error(
                    f"❌ Cannot connect to the API at `{API_BASE_URL}`. "
                    "Is the FastAPI server running?"
                )
            except requests.Timeout:
                st.error("⏱️ Request timed out after 120 seconds.")
            except requests.HTTPError as e:
                st.error(
                    f"❌ API error: {e.response.status_code} — {e.response.text}"
                )
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")

        # Human Feedback Buttons
        if full_response:
            col1, col2, _ = st.columns([1, 1, 14])
            with col1:
                if st.button("👍", key=f"up_{len(st.session_state.messages)}"):
                    st.toast("✅ Positive feedback recorded!")
            with col2:
                if st.button("👎", key=f"down_{len(st.session_state.messages)}"):
                    st.toast("📝 Negative feedback recorded!")


# ──────────────────────────────────────────────────────────────────────
# TAB 2: Evaluation Dashboard
# ──────────────────────────────────────────────────────────────────────
with tab2:
    st.header("System Evaluation & Metrics")

    col1, col2, col3, col4 = st.columns(4)

    try:
        res = requests.get(f"{API_BASE_URL}/metrics/dashboard", timeout=5).json()

        col1.metric("📚 Documents Indexed", res["inventory"]["documents_indexed"])
        col2.metric(
            "🎯 Avg Faithfulness",
            f"{res['quality']['avg_faithfulness'] * 100:.1f}%",
        )
        col3.metric(
            "📈 Avg Answer Relevance",
            f"{res['quality']['avg_answer_relevance'] * 100:.1f}%",
        )
        col4.metric(
            "⚡ P95 Chat Latency",
            f"{res['performance']['p95_chat_latency_ms']} ms",
            help="End-to-end user-facing response time",
        )
        
        with st.expander("⏱️ Detailed Pipeline Latencies (P95)"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Chat (Total)", f"{res['performance']['p95_chat_latency_ms']} ms")
            c2.metric("Retrieval", f"{res['performance']['p95_retrieval_latency_ms']} ms")
            c3.metric("LLM Gen", f"{res['performance']['p95_llm_latency_ms']} ms")
            c4.metric("RAGAS Eval (Async)", f"{res['performance']['p95_eval_latency_ms']} ms", help="Runs in background, does not block chat")

        st.divider()
        st.subheader("Recent Evaluations (RAGAS)")

        evals_res = requests.get(f"{API_BASE_URL}/metrics/", timeout=5).json()
        if evals_res:
            df = pd.DataFrame(evals_res)
            display_cols = [
                "created_at",
                "faithfulness",
                "answer_relevance",
                "context_recall",
                "chat_latency_ms",
                "eval_latency_ms",
            ]
            display_cols = [c for c in display_cols if c in df.columns]
            df = df[display_cols]
            if "created_at" in df.columns:
                df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            st.dataframe(df, use_container_width=True, hide_index=True)

            numeric_cols = [
                c
                for c in ["faithfulness", "answer_relevance", "context_recall"]
                if c in df.columns
            ]
            if numeric_cols:
                st.subheader("Evaluation Trends")
                trend_df = df.sort_values("created_at").reset_index(drop=True)
                st.line_chart(trend_df[numeric_cols])
        else:
            st.info(
                "📊 No evaluations recorded yet. Chat with the assistant to generate metrics."
            )

    except requests.ConnectionError:
        st.error(f"❌ Cannot connect to API at `{API_BASE_URL}`.")
    except Exception as e:
        st.error(f"Could not load metrics: {e}")


# ──────────────────────────────────────────────────────────────────────
# TAB 3: Document Ingestion
# ──────────────────────────────────────────────────────────────────────
with tab3:
    st.header("Document Ingestion")
    st.markdown(
        "Upload academic papers to index them for RAG retrieval. "
        "Supported formats: **PDF**, **TXT**, **MD**, **HTML**."
    )

    uploaded_files = st.file_uploader(
        "Upload Academic Papers",
        accept_multiple_files=True,
        type=["pdf", "txt", "md", "html"],
    )

    if st.button("🚀 Index Documents", disabled=not uploaded_files):
        if uploaded_files:
            files_data = [
                ("files", (f.name, f.getvalue(), f.type)) for f in uploaded_files
            ]

            try:
                response = requests.post(
                    f"{API_BASE_URL}/documents/bulk",
                    files=files_data,
                    timeout=60,
                )
                response.raise_for_status()
                result = response.json()
                job_ids = result.get("job_ids", [])
                skipped = result.get("skipped", [])

                if skipped:
                    for s in skipped:
                        st.warning(
                            f"⚠️ Skipped `{s['filename']}`: {s['reason']}"
                        )

                if job_ids:
                    st.info(
                        f"📤 Queued **{len(job_ids)}** document(s) for indexing. "
                        "Tracking progress below..."
                    )

                    # Real-time status polling
                    status_placeholder = st.empty()
                    _poll_indexing_status(job_ids, status_placeholder)
                else:
                    st.warning("No new documents to index (all duplicates or skipped).")

            except requests.ConnectionError:
                st.error(f"❌ Cannot connect to API at `{API_BASE_URL}`.")
            except requests.HTTPError as e:
                st.error(
                    f"❌ Upload failed: {e.response.status_code} — {e.response.text}"
                )
            except Exception as e:
                st.error(f"❌ Failed to upload documents: {e}")


# ──────────────────────────────────────────────────────────────────────
# TAB 4: Document Library
# ──────────────────────────────────────────────────────────────────────
with tab4:
    st.header("Document Library")
    st.markdown("All documents that have been uploaded and their indexing status.")

    if st.button("🔄 Refresh"):
        st.rerun()

    try:
        docs = requests.get(f"{API_BASE_URL}/documents/", timeout=5).json()

        if not docs:
            st.info("📭 No documents uploaded yet. Go to the Document Ingestion tab to get started.")
        else:
            # Summary metrics
            total = len(docs)
            indexed = sum(1 for d in docs if d.get("status") == "INDEXED")
            pending = sum(1 for d in docs if d.get("status") in ("PENDING", "INDEXING"))
            failed = sum(1 for d in docs if d.get("status") == "FAILED")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Documents", total)
            col2.metric("✅ Indexed", indexed)
            col3.metric("⏳ In Progress", pending)
            col4.metric("❌ Failed", failed)

            st.divider()

            # Document table
            for doc in docs:
                cols = st.columns([4, 2, 2, 1])
                cols[0].markdown(f"📄 **{doc.get('filename', 'Unknown')}**")
                cols[1].markdown(
                    _get_status_badge(doc.get("status", "UNKNOWN")),
                    unsafe_allow_html=True,
                )
                created = doc.get("created_at", "")
                if created:
                    cols[2].caption(created[:19])
                else:
                    cols[2].caption("—")

                # Delete button
                if cols[3].button("🗑️", key=f"del_{doc.get('id', '')}"):
                    try:
                        del_resp = requests.delete(
                            f"{API_BASE_URL}/documents/{doc['id']}", timeout=5
                        )
                        if del_resp.status_code == 200:
                            st.toast(f"🗑️ Deleted {doc.get('filename')}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f"Failed to delete: {del_resp.text}")
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

    except requests.ConnectionError:
        st.error(f"❌ Cannot connect to API at `{API_BASE_URL}`.")
    except Exception as e:
        st.error(f"Failed to load document library: {e}")
