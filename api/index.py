import sys
import os

# Add root folder to sys.path so modules like agents, orchestrator, and report_store can be imported
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

# Import the FastAPI application instance
from main import app
