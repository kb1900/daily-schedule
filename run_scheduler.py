#!/usr/bin/env python3
"""
Scheduler for Daily Schedule Scraper

This script runs the daily schedule scraper at specified intervals.
It's an alternative to using cron jobs.

Usage:
    uv run run_scheduler.py
    uv run run_scheduler.py --person "Last,F"  # Monitor assignments for a specific person
    uv run run_scheduler.py --interval 30  # Change the check interval (in minutes)
    uv run run_scheduler.py --person "Last,F" --pushover-token "APP_TOKEN"  # With push notifications
"""

import time
import logging
import subprocess
import sys
import argparse
import json
import requests
import hashlib
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Any

# Try to import dotenv for environment variables
try:
    from dotenv import load_dotenv
    # Load environment variables from .env file
    load_dotenv()
    ENV_LOADED = True
except ImportError:
    ENV_LOADED = False
    print("python-dotenv not installed. Environment variables will not be loaded from .env file.")
    print("To install: uv add python-dotenv")

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
DEFAULT_INTERVAL_MINUTES = int(os.getenv('DEFAULT_INTERVAL', '60'))  # Run every hour by default
SCRAPER_SCRIPT = "daily_schedule_scraper.py"

# Pushover configuration
PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
# Your Pushover user key (identifies you as the recipient)
PUSHOVER_USER_KEY = os.getenv('PUSHOVER_USER_KEY', 'uxnmijx7ej1d879sfud8aeqwg5mg1f')
# Application token (identifies your app as the sender) - will be set via command line argument or env var
PUSHOVER_APP_TOKEN = os.getenv('PUSHOVER_APP_TOKEN', None)
# Your device name
PUSHOVER_DEVICE = os.getenv('PUSHOVER_DEVICE', 'KBPHONE')
# Default person to monitor
DEFAULT_PERSON = os.getenv('DEFAULT_PERSON', None)
# Debug mode
DEBUG = os.getenv('DEBUG', 'false').lower() in ('true', '1', 't', 'yes', 'y')


def send_pushover_notification(title, message, priority=0, html=1):
    """
    Send a push notification via Pushover.
    
    Args:
        title: The notification title
        message: The notification message
        priority: Message priority (-2 to 2, with 2 being emergency)
        html: Whether to enable HTML formatting (1 for yes, 0 for no)
        
    Returns:
        True if the notification was sent successfully, False otherwise
    """
    if not PUSHOVER_APP_TOKEN:
        logger.warning("Pushover app token not set. Notifications disabled.")
        return False
    
    try:
        payload = {
            "token": PUSHOVER_APP_TOKEN,  # Application token (from Pushover website)
            "user": PUSHOVER_USER_KEY,    # User key (from your Pushover account)
            "device": PUSHOVER_DEVICE,
            "title": title,
            "message": message,
            "priority": priority,
            "sound": "pushover",  # Default sound
            "html": html          # Enable HTML formatting
        }
        
        logger.info(f"Sending Pushover notification: {title}")
        if DEBUG:
            logger.debug(f"Notification message: {message}")
            
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
            hash_value = f.read().strip()
            logger.debug(f"Read hash value from file: {hash_value[:8]}...")
            return hash_value
    logger.info(f"No previous hash found for {person}")
    return None


def save_schedule_hash(person, schedule_text):
    """
    Save the hash of the current schedule for a person.
    
    Args:
        person: The person's name
        schedule_text: The schedule text to hash
        
    Returns:
        The hash value
    """
    # Extract only the schedule part from the output (remove log messages)
    schedule_match = re.search(r'=== Assignment for .+? ===.*?(?=\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}|\Z)', 
                              schedule_text, re.DOTALL)
    
    if schedule_match:
        schedule_content = schedule_match.group(0).strip()
    else:
        schedule_content = schedule_text.strip()
    
    hash_value = hashlib.sha256(schedule_content.encode('utf-8')).hexdigest()
    logger.debug(f"Generated hash value: {hash_value[:8]}...")
    
    hash_file = Path(f"data/last_schedule_hash_{person.replace(',', '_').replace(' ', '_')}.txt")
    
    # Create the data directory if it doesn't exist
    hash_file.parent.mkdir(exist_ok=True, parents=True)
    
    with open(hash_file, 'w') as f:
        f.write(hash_value)
    
    logger.debug(f"Saved hash value to file: {hash_value[:8]}...")
    return hash_value


def extract_schedule_details(output_text):
    """
    Extract detailed schedule information from the scraper output.
    
    Args:
        output_text: The text output from the scraper
        
    Returns:
        A dictionary containing the extracted schedule details
    """
    details = {
        'date': None,
        'personnel_info': {},
        'room_assignment': None,
        'cases': []
    }
    
    # Extract date
    date_match = re.search(r'=== Assignment for .+ on (.+) ===', output_text)
    if date_match:
        details['date'] = date_match.group(1)
    
    # Extract personnel info
    personnel_section = re.search(r'Personnel Information:(.*?)(?:\n\n|\n\w)', output_text, re.DOTALL)
    if personnel_section:
        personnel_text = personnel_section.group(1)
        for line in personnel_text.strip().split('\n'):
            if ':' in line:
                key, value = line.strip().split(':', 1)
                details['personnel_info'][key.strip()] = value.strip()
    
    # Extract room assignment
    room_match = re.search(r'Room Assignment: (.+)', output_text)
    if room_match:
        details['room_assignment'] = room_match.group(1)
    
    # Extract cases
    cases_section = re.search(r'Cases:(.*?)(?:\n\n\d|$)', output_text, re.DOTALL)
    if cases_section:
        cases_text = cases_section.group(1)
        case_blocks = re.findall(r'Case \d+:(.*?)(?=\n  Case \d+:|\n\d|\Z)', cases_text, re.DOTALL)
        
        for case_block in case_blocks:
            case = {}
            for line in case_block.strip().split('\n'):
                if ':' in line:
                    key, value = line.strip().split(':', 1)
                    case[key.strip()] = value.strip()
            if case:
                details['cases'].append(case)
    
    return details


def format_procedure_description(procedure: str) -> str:
    """
    Format a procedure description to be more readable in a notification.
    
    Args:
        procedure: The raw procedure description
        
    Returns:
        A formatted procedure description
    """
    # Remove CPT codes section if present
    if '[(cpt)' in procedure:
        procedure = procedure.split('[(cpt)')[0].strip()
    
    # Remove anesthesia type if present at the end in parentheses
    if procedure.endswith(')'):
        last_open_paren = procedure.rfind('(')
        if last_open_paren != -1:
            procedure = procedure[:last_open_paren].strip()
    
    # Clean up any extra whitespace or newlines
    procedure = re.sub(r'\s+', ' ', procedure).strip()
    
    return procedure


def format_schedule_notification(details):
    """
    Format the schedule details into a professional notification message.
    
    Args:
        details: The extracted schedule details
        
    Returns:
        A formatted HTML message for the notification
    """
    message = f"<b>📅 Schedule for {details['date']}</b>\n\n"
    
    # Add personnel info
    if details['personnel_info']:
        message += "<b>👤 Your Information:</b>\n"
        for key, value in details['personnel_info'].items():
            message += f"• <b>{key}:</b> {value}\n"
        message += "\n"
    
    # Add room assignment
    if details['room_assignment']:
        message += f"<b>🏥 Room Assignment:</b> {details['room_assignment']}\n\n"
    
    # Add cases
    if details['cases']:
        message += f"<b>📋 Cases ({len(details['cases'])}):</b>\n"
        for i, case in enumerate(details['cases'], 1):
            message += f"<b>Case {i}:</b>\n"
            
            # Time
            if 'Time' in case:
                # Try to format the time more nicely
                try:
                    time_obj = datetime.strptime(case['Time'], "%Y-%m-%d %H:%M:%S")
                    formatted_time = time_obj.strftime("%I:%M %p")
                    message += f"• <b>Time:</b> {formatted_time}\n"
                except:
                    message += f"• <b>Time:</b> {case['Time']}\n"
            
            # Team
            if 'Team' in case:
                message += f"• <b>Team:</b> {case['Team']}\n"
            
            # Patient Age
            if 'Patient Age' in case:
                message += f"• <b>Patient:</b> {case['Patient Age']}\n"
            
            # Procedure (properly formatted)
            if 'Procedure' in case:
                proc = format_procedure_description(case['Procedure'])
                message += f"• <b>Procedure:</b> {proc}\n"
            
            # Anesthesia
            if 'Anesthesia' in case:
                message += f"• <b>Anesthesia:</b> {case['Anesthesia']}\n"
            
            # Surgeon
            if 'Surgeon' in case:
                message += f"• <b>Surgeon:</b> {case['Surgeon']}\n"
            
            message += "\n"
    else:
        message += "<b>No specific cases found for this assignment.</b>\n"
    
    # Add footer
    message += "\n<i>Updated at " + datetime.now().strftime("%I:%M %p on %A, %B %d, %Y") + "</i>"
    
    return message


def extract_schedule_from_output(output_text):
    """
    Extract just the schedule part from the scraper output, removing log messages.
    
    Args:
        output_text: The full output text from the scraper
        
    Returns:
        The extracted schedule text
    """
    # Find the schedule section (from "=== Assignment for" to the end or next log message)
    schedule_match = re.search(r'=== Assignment for .+? ===.*?(?=\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}|\Z)', 
                              output_text, re.DOTALL)
    
    if schedule_match:
        return schedule_match.group(0).strip()
    
    return ""


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
                    # Extract just the schedule part from the output
                    schedule_text = extract_schedule_from_output(result.stdout)
                    
                    if not schedule_text:
                        logger.warning("Could not extract schedule from output")
                        return
                    
                    # Clean up the schedule text to ensure consistent hashing
                    # Remove any timestamps or variable data that might change between runs
                    # Focus only on the core schedule information
                    clean_schedule = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}', '', schedule_text)
                    
                    # Get the previous hash
                    last_hash = get_last_schedule_hash(person)
                    
                    # Calculate the current hash
                    current_hash = hashlib.sha256(clean_schedule.encode('utf-8')).hexdigest()
                    
                    # Debug logging
                    if last_hash:
                        logger.debug(f"Previous hash: {last_hash[:8]}...")
                    logger.debug(f"Current hash: {current_hash[:8]}...")
                    
                    # Save the current hash
                    hash_file = Path(f"data/last_schedule_hash_{person.replace(',', '_').replace(' ', '_')}.txt")
                    hash_file.parent.mkdir(exist_ok=True, parents=True)
                    with open(hash_file, 'w') as f:
                        f.write(current_hash)
                    
                    # Extract schedule details
                    schedule_details = extract_schedule_details(result.stdout)
                    
                    # Only send notifications if this is the first run or if the schedule has changed
                    if last_hash is None:
                        # First run, send initial notification with full details
                        notification_message = format_schedule_notification(schedule_details)
                        send_pushover_notification(
                            f"📅 Schedule for {person}",
                            notification_message,
                            priority=0,
                            html=1
                        )
                        logger.info(f"Sent initial schedule notification for {person}")
                    elif last_hash != current_hash:
                        # Schedule has changed, send notification with full details
                        notification_message = format_schedule_notification(schedule_details)
                        send_pushover_notification(
                            f"🔄 Schedule Updated for {person}",
                            notification_message,
                            priority=1,  # Higher priority for changes
                            html=1
                        )
                        logger.info(f"Sent schedule update notification for {person} - hash changed from {last_hash[:8]}... to {current_hash[:8]}...")
                    else:
                        logger.info(f"No changes to {person}'s schedule, skipping notification (hash: {current_hash[:8]}...)")
                
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
                "⚠️ Schedule Scraper Error",
                f"<b>Error checking schedule for {person}.</b>\n\nPlease check the logs for more details.",
                priority=1,
                html=1
            )
    except Exception as e:
        logger.error(f"Error running scraper: {e}")
        
        # Send notification about the error
        if PUSHOVER_APP_TOKEN and person:
            send_pushover_notification(
                "⚠️ Schedule Scraper Error",
                f"<b>Unexpected error:</b>\n{str(e)}",
                priority=1,
                html=1
            )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Daily Schedule Scraper Scheduler')
    parser.add_argument('--person', type=str, default=DEFAULT_PERSON,
                        help=f'Name of the person to monitor assignments for (e.g., "Last,F"). Default: {DEFAULT_PERSON or "None"}')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL_MINUTES, 
                        help=f'Interval between checks in minutes (default: {DEFAULT_INTERVAL_MINUTES})')
    parser.add_argument('--pushover-token', type=str, default=PUSHOVER_APP_TOKEN,
                        help='Pushover APPLICATION TOKEN (not your user key) for sending notifications')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    return parser.parse_args()


def main() -> None:
    """Main function to run the scheduler."""
    # Parse command line arguments
    args = parse_arguments()
    
    interval_minutes = args.interval
    person = args.person
    
    # Set debug mode if requested
    global DEBUG
    if args.debug:
        DEBUG = True
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Set the Pushover app token if provided
    global PUSHOVER_APP_TOKEN
    if args.pushover_token:
        PUSHOVER_APP_TOKEN = args.pushover_token
    
    if PUSHOVER_APP_TOKEN:
        logger.info("Pushover notifications enabled")
        print("Pushover notifications enabled")
        
        # Verify the token format
        if PUSHOVER_APP_TOKEN == PUSHOVER_USER_KEY:
            logger.warning("WARNING: The Pushover token provided appears to be your user key, not an application token.")
            print("\n⚠️  WARNING: The Pushover token provided appears to be your user key, not an application token.")
            print("   You need to create an application at https://pushover.net/apps/build")
            print("   and use the application token/key provided there.\n")
        
        if person:
            # Send a test notification
            success = send_pushover_notification(
                "🔔 Schedule Monitoring Started",
                f"<b>Now monitoring schedule for {person}.</b>\n\nYou'll receive notifications when your schedule changes.",
                priority=0,
                html=1
            )
            
            if not success:
                print("\n⚠️  Failed to send test notification. Please check your Pushover configuration.")
                print("   Make sure you've created an application at https://pushover.net/apps/build")
                print("   and are using the correct application token.\n")
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
                "🛑 Schedule Monitoring Stopped",
                f"<b>Monitoring for {person} has been stopped.</b>",
                priority=0,
                html=1
            )
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        
        # Send notification about the error
        if PUSHOVER_APP_TOKEN and person:
            send_pushover_notification(
                "⚠️ Schedule Monitoring Error",
                f"<b>Scheduler encountered an error:</b>\n{str(e)}",
                priority=1,
                html=1
            )


if __name__ == "__main__":
    main() 