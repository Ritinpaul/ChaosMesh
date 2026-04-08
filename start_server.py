#!/usr/bin/env python3
"""
ChaosMesh Arena - Server Startup Script
========================================

This script starts the ChaosMesh Arena server with all necessary checks.

Usage:
    python start_server.py

Environment:
    Reads configuration from .env file in the same directory.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def check_python_version():
    """Ensure Python 3.10+ is being used."""
    print_info("Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print_error(f"Python 3.10+ required, but found {version.major}.{version.minor}")
        sys.exit(1)
    print_success(f"Python {version.major}.{version.minor}.{version.micro}")

def check_env_file():
    """Check if .env file exists."""
    print_info("Checking for .env file...")
    if not Path(".env").exists():
        print_warning(".env file not found!")
        print_info("Creating .env from .env.example...")
        
        if Path(".env.example").exists():
            import shutil
            shutil.copy(".env.example", ".env")
            print_success("Created .env file")
            print_warning("Please review .env and update API keys if needed")
        else:
            print_error(".env.example not found!")
            sys.exit(1)
    else:
        print_success(".env file exists")

def check_dependencies():
    """Check if required packages are installed."""
    print_info("Checking dependencies...")
    try:
        import fastapi
        import gradio
        import httpx
        import structlog
        print_success("Core dependencies installed")
    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Installing dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
        print_success("Dependencies installed")

def check_port(port=8000):
    """Check if port is available."""
    print_info(f"Checking if port {port} is available...")
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    
    if result == 0:
        print_warning(f"Port {port} is already in use!")
        print_info("This might be a previous instance. Attempting to continue...")
        return False
    else:
        print_success(f"Port {port} is available")
        return True

def start_server():
    """Start the FastAPI server."""
    print_header("Starting ChaosMesh Arena Server")
    
    # Pre-flight checks
    check_python_version()
    check_env_file()
    check_dependencies()
    port_available = check_port()
    
    print_info("\nServer configuration:")
    print(f"  • Host: 0.0.0.0")
    print(f"  • Port: 8000")
    print(f"  • Dashboard: http://localhost:8000/dashboard")
    print(f"  • API Docs: http://localhost:8000/docs")
    print(f"  • Health Check: http://localhost:8000/health")
    
    print_header("Starting Uvicorn Server")
    
    try:
        # Start the server
        os.environ['PYTHONUNBUFFERED'] = '1'
        
        print_success("Server starting...")
        print_info("Press Ctrl+C to stop the server\n")
        
        # Use uvicorn programmatically
        import uvicorn
        uvicorn.run(
            "server.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info",
            access_log=True
        )
        
    except KeyboardInterrupt:
        print_info("\n\nShutting down gracefully...")
        print_success("Server stopped")
    except Exception as e:
        print_error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_server()
