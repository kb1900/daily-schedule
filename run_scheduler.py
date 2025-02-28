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
# Your Pushover user key (identifies you as the recipient)
PUSHOVER_USER_KEY = "uxnmijx7ej1d879sfud8aeqwg5mg1f"  
# Application token (identifies your app as the sender) - will be set via command line argument
PUSHOVER_APP_TOKEN = None  
# Your device name
PUSHOVER_DEVICE = "KBPHONE"  


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
            
            # Procedure (shortened)
            if 'Procedure' in case:
                proc = case['Procedure']
                # Shorten the procedure description if it's too long
                if len(proc) > 100:
                    proc = proc[:97] + "..."
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
                    
                    # Extract schedule details
                    schedule_details = extract_schedule_details(result.stdout)
                    
                    if last_hash is None:
                        # First run, send initial notification with full details
                        notification_message = format_schedule_notification(schedule_details)
                        send_pushover_notification(
                            f"📅 Schedule for {person}",
                            notification_message,
                            priority=0,
                            html=1
                        )
                    elif last_hash != current_hash:
                        # Schedule has changed, send notification with full details
                        notification_message = format_schedule_notification(schedule_details)
                        send_pushover_notification(
                            f"🔄 Schedule Updated for {person}",
                            notification_message,
                            priority=1,  # Higher priority for changes
                            html=1
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
    parser.add_argument('--person', type=str, help='Name of the person to monitor assignments for (e.g., "Last,F")')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL_MINUTES, 
                        help=f'Interval between checks in minutes (default: {DEFAULT_INTERVAL_MINUTES})')
    parser.add_argument('--pushover-token', type=str, 
                        help='Pushover APPLICATION TOKEN (not your user key) for sending notifications')
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
                f"<b>Now monitoring schedule for {person}.</b>\n\nYou'll receive detailed notifications when your schedule changes.",
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