"""
Pytest configuration and shared fixtures for A.L.F.R.E.D. tests
"""

import os
import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables for testing
os.environ["TESTING"] = "1"
os.environ["NO_ANSI"] = "1"  # Disable ANSI colors in tests
