import streamlit as st
import requests
import pandas as pd
import json

API_BASE_URL = "http://localhost:8080/api/v1"

st.set_page_config(page_title="ScholarForge_AI Dashboard", layout="wide", page_icon="🎓")

st.title("🎓 ScholarForge_AI")
st.subheader("Production RAG System with Evaluation Dashboard")

tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Evaluation Dashboard", "📄 Document Ingestion"])

with tab1:
    st.header("Research Assistant")
    
    if "session_id" not in st.session_state:
        import uuid
        st.session_state.session_id = str(uuid.uuid4())
        
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question about your academic papers..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            message_id = None
            
            try:
                # Call the real streaming API
                response = requests.post(
                    f"{API_BASE_URL}/chat/stream",
                    json={"session_id": st.session_state.session_id, "message": prompt, "stream": True},
                    stream=True
                )
                
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            data = json.loads(decoded_line[6:])
                            if "delta" in data:
                                full_response += data["delta"]
                                message_placeholder.markdown(full_response + "▌")
                            elif "metadata" in data:
                                # We could capture the message_id here if the backend sent it
                                pass
                            elif "error" in data:
                                st.error(data["error"])
                                
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Failed to connect to Chat API: {e}")

        # Human Feedback Buttons
        # Note: Since the backend streams the response, we might need a way to get the message_id back. 
        # For this MVP UI, we'll assume the user just gives general feedback for now or we leave it as a conceptual UI button.
        col1, col2 = st.columns([1, 15])
        with col1:
            if st.button("👍", key=f"up_{len(st.session_state.messages)}"):
                st.toast("Feedback recorded! (Upvote)")
        with col2:
            if st.button("👎", key=f"down_{len(st.session_state.messages)}"):
                st.toast("Feedback recorded! (Downvote)")

with tab2:
    st.header("System Evaluation & Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Fetch metrics from the API
    try:
        res = requests.get(f"{API_BASE_URL}/metrics/dashboard").json()
        
        col1.metric("Documents Indexed", res['inventory']['documents_indexed'])
        col2.metric("Avg Faithfulness", f"{res['quality']['avg_faithfulness'] * 100:.1f}%")
        col3.metric("Avg Answer Relevance", f"{res['quality']['avg_answer_relevance'] * 100:.1f}%")
        col4.metric("P95 Latency", f"{res['performance']['p95_latency_ms']} ms")
        
        st.divider()
        st.subheader("Recent Evaluations (RAGAS)")
        
        evals_res = requests.get(f"{API_BASE_URL}/metrics/").json()
        if evals_res:
            df = pd.DataFrame(evals_res)
            # Reorder and format columns
            df = df[['created_at', 'faithfulness', 'answer_relevance', 'context_recall', 'latency_ms']]
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
            st.dataframe(df, use_container_width=True)
            
            # Trend Chart
            st.subheader("Evaluation Trends")
            trend_df = df.sort_values('created_at').reset_index(drop=True)
            st.line_chart(trend_df[['faithfulness', 'answer_relevance', 'context_recall']])
        else:
            st.info("No evaluations recorded yet. Chat with the assistant to generate metrics.")
            
    except Exception as e:
        st.error(f"Could not load metrics. Ensure the API is running. Error: {e}")

with tab3:
    st.header("Document Ingestion")
    uploaded_files = st.file_uploader("Upload Academic Papers (PDF, HTML, MD, TXT)", accept_multiple_files=True)
    
    if st.button("Index Documents") and uploaded_files:
        with st.spinner('Uploading, Parsing, Chunking, and Embedding...'):
            files_data = [('files', (f.name, f.getvalue(), f.type)) for f in uploaded_files]
            response = requests.post(f"{API_BASE_URL}/documents/bulk", files=files_data)
            
            if response.status_code == 200:
                st.success(f"Successfully queued {len(uploaded_files)} documents for indexing!")
            else:
                st.error("Failed to upload documents.")
