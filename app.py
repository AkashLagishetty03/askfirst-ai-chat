import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="AI Chat App", page_icon="🤖")

st.title("🤖 AI Chat App with Universal Memory")

# Initialize session state for active thread
if "active_thread_id" not in st.session_state:
    st.session_state.active_thread_id = None

# --- Sidebar ---
with st.sidebar:
    st.header("Chat Threads")
    
    # New Thread Button
    with st.form(key="new_thread_form"):
        new_thread_title = st.text_input("New Thread Title", placeholder="Enter title...")
        submit_button = st.form_submit_button(label="Create New Thread")
        
    if submit_button and new_thread_title:
        res = requests.post(f"{API_URL}/threads", json={"title": new_thread_title})
        if res.status_code == 200:
            st.session_state.active_thread_id = res.json()["id"]
            st.rerun()

    st.divider()

    # List Existing Threads
    try:
        threads_res = requests.get(f"{API_URL}/threads")
        if threads_res.status_code == 200:
            threads = threads_res.json()
            for thread in threads:
                # Highlight active thread
                button_type = "primary" if thread["id"] == st.session_state.active_thread_id else "secondary"
                if st.button(f"{thread['title']} (ID: {thread['id']})", key=f"thread_{thread['id']}", type=button_type):
                    st.session_state.active_thread_id = thread["id"]
                    st.rerun()
    except requests.exceptions.ConnectionError:
        st.error("Backend is not running. Please start FastAPI.")

# --- Main Chat Area ---
if st.session_state.active_thread_id is not None:
    thread_id = st.session_state.active_thread_id
    
    # Fetch messages for active thread
    messages_res = requests.get(f"{API_URL}/threads/{thread_id}/messages")
    if messages_res.status_code == 200:
        messages = messages_res.json()
        for msg in messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Chat Input
    if prompt := st.chat_input("Type your message here..."):
        # Display user message immediately
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Send to backend
        with st.spinner("AI is thinking..."):
            post_res = requests.post(f"{API_URL}/threads/{thread_id}/messages", json={"content": prompt})
            
        if post_res.status_code == 200:
            st.rerun()
        else:
            st.error(f"Error: {post_res.text}")

else:
    st.info("Please select or create a thread from the sidebar to start chatting.")
