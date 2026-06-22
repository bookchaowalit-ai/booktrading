"""
Pytest configuration for test discovery.
"""
import sys
from pathlib import Path

# Add /app to sys.path so imports like `from app.polymarket...` work
sys.path.insert(0, str(Path(__file__).parent.parent))
