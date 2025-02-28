#!/usr/bin/env python3
"""
Scheduler for Daily Schedule Scraper

This script runs the daily schedule scraper at specified intervals.
It's an alternative to using cron jobs.

Usage:
    uv run run_scheduler.py
    uv run run_scheduler.py --person "Last,F"  # Monitor assignments for a specific person
    uv run run_scheduler.py --interval 30  # Change the check interval (in minutes)
"""

import time
import logging
import subprocess
import sys
import argparse
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
DEFAULT_INTERVAL_MINUTES = 60  # Run every hour by default
SCRAPER_SCRIPT = "daily_schedule_scraper.py"


def run_scraper(person: str = None, interval_minutes: int = DEFAULT_INTERVAL_MINUTES) -> None:
    """
    Run the daily schedule scraper script.
    
    Args:
        person: Optional name of the person to find assignments for
        interval_minutes: Interval between checks in minutes
    """
    logger.info(f"Running scraper at {datetime.now().isoformat()}")
    
    try:
        # Prepare the command
        command = ["uv", "run", SCRAPER_SCRIPT]
        
        # Add the person flag if specified
        if person:
            command.extend(["--person", person])
        
        # Use subprocess to run the scraper script
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Log the output
        if result.stdout:
            # If monitoring a specific person, print the output to the console
            if person:
                print(result.stdout)
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


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Daily Schedule Scraper Scheduler')
    parser.add_argument('--person', type=str, help='Name of the person to monitor assignments for (e.g., "Last,F")')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL_MINUTES, 
                        help=f'Interval between checks in minutes (default: {DEFAULT_INTERVAL_MINUTES})')
    return parser.parse_args()


def main() -> None:
    """Main function to run the scheduler."""
    # Parse command line arguments
    args = parse_arguments()
    
    interval_minutes = args.interval
    person = args.person
    
    if person:
        logger.info(f"Starting scheduler for person '{person}', will run every {interval_minutes} minutes")
        print(f"Monitoring schedule for '{person}', checking every {interval_minutes} minutes. Press Ctrl+C to stop.")
    else:
        logger.info(f"Starting scheduler, will run every {interval_minutes} minutes")
    
    try:
        # Run immediately on startup
        run_scraper(person, interval_minutes)
        
        # Then run at specified intervals
        while True:
            if person:
                print(f"\nWaiting {interval_minutes} minutes before next check...")
            logger.info(f"Sleeping for {interval_minutes} minutes")
            time.sleep(interval_minutes * 60)
            run_scraper(person, interval_minutes)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        print("\nScheduler stopped. Goodbye!")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


if __name__ == "__main__":
    main() 