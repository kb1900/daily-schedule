#!/usr/bin/env python3
"""
Setup Data Directories

This script creates the necessary data directory structure for the Daily Schedule Scraper.
Run this script after cloning the repository to ensure the data directories exist.

Usage:
    uv run setup_data_dirs.py
"""

import os
from pathlib import Path

# Define the directories to create
DATA_DIR = Path("data")
HTML_DIR = DATA_DIR / "html"
JSON_DIR = DATA_DIR / "json"

def main():
    """Create the necessary data directories if they don't exist."""
    print("Setting up data directories...")
    
    # Create the directories
    for directory in [DATA_DIR, HTML_DIR, JSON_DIR]:
        directory.mkdir(exist_ok=True, parents=True)
        print(f"Created directory: {directory}")
    
    print("Data directory setup complete!")

if __name__ == "__main__":
    main() 