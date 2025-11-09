"""
Simple script to run the Streamlit UI
"""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    # Get the path to the streamlit app
    app_path = Path(__file__).parent / "src" / "fintrid_backend" / "streamlit_app.py"
    
    # Run streamlit
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", 
        str(app_path),
        "--server.port", "8501",
        "--server.address", "localhost"
    ])
