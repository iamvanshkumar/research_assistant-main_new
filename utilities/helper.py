# utilities/helper.py
import streamlit as st
import base64

def encode_pdf(file_content):
    return base64.b64encode(file_content).decode("utf-8")

def init_session_state():
    defaults = {
        "messages": [],
        "pdf_content": None,
        "notes": None,
        "selected_model": None,
        "model": None,
        "start_analysis": False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
