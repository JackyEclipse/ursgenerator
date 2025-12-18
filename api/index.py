"""
Vercel Serverless Function Entry Point
Wraps the FastAPI app for Vercel deployment
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from main import app

# Vercel expects 'app' or 'handler'
handler = app

