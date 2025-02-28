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
import json
import requests
import hashlib
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

# Pushover configuration
PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_USER_KEY = "uxnmijx7ej1d879sfud8aeqwg5mg1f"  # Your Pushover user key
PUSHOVER_APP_TOKEN = None  # Will be set via command line argument
PUSHOVER_DEVICE = "KBPHONE"  # Your device name


def send_pushover_notification(title, message, priority=0):
    """
    Send a push notification via Pushover.
    
    Args:
        title: The notification title
        message: The notification message
        priority: Message priority (-2 to 2, with 2 being emergency)
        
    Returns:
        True if the notification was sent successfully, False otherwise
    """
    if not PUSHOVER_APP_TOKEN:
        logger.warning("Pushover app token not set. Notifications disabled.")
        return False
    
    try:
        payload = {
            "token": PUSHOVER_APP_TOKEN,
            "user": PUSHOVER_USER_KEY,
            "device": PUSHOVER_DEVICE,
            "title": title,
            "message": message,
            "priority": priority,
            "sound": "pushover"  # Default sound
        }
        
        response = requests.post(PUSHOVER_API_URL, data=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get("status") == 1:
            logger.info(f"Pushover notification sent successfully: {title}")
            return True
        else:
            logger.error(f"Pushover notification failed: {result.get('errors', ['Unknown error'])}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Error sending Pushover notification: {e}")
        return False


def get_last_schedule_hash(person):
    """
    Get the hash of the last schedule for a person.
    
    Args:
        person: The person's name
        
    Returns:
        The hash of the last schedule, or None if not available
    """
    hash_file = Path(f"data/last_schedule_hash_{person.replace(',', '_').replace(' ', '_')}.txt")
    if hash_file.exists():
        with open(hash_file, 'r') as f:
            return f.read().strip()
    return None


def save_schedule_hash(person, schedule_text):
    """
    Save the hash of the current schedule for a person.
    
    Args:
        person: The person's name
        schedule_text: The schedule text to hash
    """
    hash_value = hashlib.sha256(schedule_text.encode('utf-8')).hexdigest()
    hash_file = Path(f"data/last_schedule_hash_{person.replace(',', '_').replace(' ', '_')}.txt")
    
    # Create the data directory if it doesn't exist
    hash_file.parent.mkdir(exist_ok=True, parents=True)
    
    with open(hash_file, 'w') as f:
        f.write(hash_value)
    
    return hash_value


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
                
                # Check if the schedule has changed
                if PUSHOVER_APP_TOKEN:
                    last_hash = get_last_schedule_hash(person)
                    current_hash = save_schedule_hash(person, result.stdout)
                    
                    if last_hash is None:
                        # First run, send initial notification
                        send_pushover_notification(
                            f"Schedule for {person}",
                            f"Initial schedule loaded. Check the console for details.",
                            priority=0
                        )
                    elif last_hash != current_hash:
                        # Schedule has changed, send notification
                        send_pushover_notification(
                            f"Schedule Change for {person}",
                            f"Your schedule has been updated. Check the console for details.",
                            priority=1  # Higher priority for changes
                        )
                
            logger.info(f"Scraper output: {result.stdout}")
        
        logger.info("Scraper completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Scraper failed with exit code {e.returncode}")
        if e.stdout:
            logger.error(f"Stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"Stderr: {e.stderr}")
            
        # Send notification about the error
        if PUSHOVER_APP_TOKEN and person:
            send_pushover_notification(
                "Schedule Scraper Error",
                f"Error checking schedule for {person}. Please check the logs.",
                priority=1
            )
    except Exception as e:
        logger.error(f"Error running scraper: {e}")
        
        # Send notification about the error
        if PUSHOVER_APP_TOKEN and person:
            send_pushover_notification(
                "Schedule Scraper Error",
                f"Unexpected error: {str(e)}",
                priority=1
            )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Daily Schedule Scraper Scheduler')
    parser.add_argument('--person', type=str, help='Name of the person to monitor assignments for (e.g., "Last,F")')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL_MINUTES, 
                        help=f'Interval between checks in minutes (default: {DEFAULT_INTERVAL_MINUTES})')
    parser.add_argument('--pushover-token', type=str, help='Pushover application token for sending notifications')
    return parser.parse_args()


def main() -> None:
    """Main function to run the scheduler."""
    # Parse command line arguments
    args = parse_arguments()
    
    interval_minutes = args.interval
    person = args.person
    
    # Set the Pushover app token if provided
    global PUSHOVER_APP_TOKEN
    PUSHOVER_APP_TOKEN = args.pushover_token
    
    if PUSHOVER_APP_TOKEN:
        logger.info("Pushover notifications enabled")
        if person:
            # Send a test notification
            send_pushover_notification(
                "Schedule Monitoring Started",
                f"Now monitoring schedule for {person}. You'll be notified of any changes.",
                priority=0
            )
    else:
        logger.info("Pushover notifications disabled (no app token provided)")
    
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
        
        # Send notification that monitoring has stopped
        if PUSHOVER_APP_TOKEN and person:
            send_pushover_notification(
                "Schedule Monitoring Stopped",
                f"Monitoring for {person} has been stopped.",
                priority=0
            )
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        
        # Send notification about the error
        if PUSHOVER_APP_TOKEN and person:
            send_pushover_notification(
                "Schedule Monitoring Error",
                f"Scheduler encountered an error: {str(e)}",
                priority=1
            )


if __name__ == "__main__":
    main() 