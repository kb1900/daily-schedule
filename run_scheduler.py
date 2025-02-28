#!/usr/bin/env python3
"""
Scheduler for Daily Schedule Scraper

This script runs the daily schedule scraper at specified intervals.
It's an alternative to using cron jobs.

Usage:
    uv run run_scheduler.py
"""

import time
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scheduler.log')
    ]
)
logger = logging.getLogger('scheduler')

# Constants
INTERVAL_MINUTES = 60  # Run every hour by default
SCRAPER_SCRIPT = "daily_schedule_scraper.py"


def run_scraper() -> None:
    """Run the daily schedule scraper script."""
    logger.info(f"Running scraper at {datetime.now().isoformat()}")
    
    try:
        # Use subprocess to run the scraper script
        result = subprocess.run(
            ["uv", "run", SCRAPER_SCRIPT],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Log the output
        if result.stdout:
            logger.info(f"Scraper output: {result.stdout}")
        
        logger.info("Scraper completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Scraper failed with exit code {e.returncode}")
        if e.stdout:
            logger.error(f"Stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"Stderr: {e.stderr}")
    except Exception as e:
        logger.error(f"Error running scraper: {e}")


def main() -> None:
    """Main function to run the scheduler."""
    logger.info(f"Starting scheduler, will run every {INTERVAL_MINUTES} minutes")
    
    try:
        # Run immediately on startup
        run_scraper()
        
        # Then run at specified intervals
        while True:
            logger.info(f"Sleeping for {INTERVAL_MINUTES} minutes")
            time.sleep(INTERVAL_MINUTES * 60)
            run_scraper()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


if __name__ == "__main__":
    main() 