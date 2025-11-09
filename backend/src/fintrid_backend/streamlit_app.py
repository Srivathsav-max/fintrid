import streamlit as st
import requests
from datetime import datetime, date
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page configuration
st.set_page_config(
    page_title="Fintrid - Financial Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)


def check_api_health():
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def main():
    st.title("💰 Fintrid - Financial Tracker")
    
    if not check_api_health():
        st.error("API is not running! Please start the FastAPI server first.")
        st.code("uv run fintrid-api", language="bash")
        st.stop()
    
    st.success("Connected to API")
    
if __name__ == "__main__":
    main()
