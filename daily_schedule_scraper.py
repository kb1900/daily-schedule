#!/usr/bin/env python3
"""
Daily Schedule Scraper

This script scrapes the daily assignments schedule from a specified URL,
parses the content, and stores it locally. It only saves new content
when changes are detected.

Usage:
    uv run daily_schedule_scraper.py
    uv run daily_schedule_scraper.py --person "Last,F"  # Extract assignments for a specific person
"""

import os
import sys
import time
import hashlib
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('daily_schedule_scraper.log')
    ]
)
logger = logging.getLogger('daily_schedule_scraper')

# Constants
URL = "https://anesweb02.mountsinai.org/shared/viewdoc.php?A=daily_assignments_rescrna"
DATA_DIR = Path("data")
HTML_DIR = DATA_DIR / "html"
JSON_DIR = DATA_DIR / "json"
HASH_FILE = DATA_DIR / "last_content_hash.txt"
REQUEST_TIMEOUT = 30  # seconds


def setup_directories() -> None:
    """Create necessary directories if they don't exist."""
    for directory in [DATA_DIR, HTML_DIR, JSON_DIR]:
        directory.mkdir(exist_ok=True, parents=True)
    logger.info(f"Directories set up: {DATA_DIR}, {HTML_DIR}, {JSON_DIR}")


def get_page_content(url: str) -> Optional[str]:
    """
    Fetch the content from the specified URL.
    
    Args:
        url: The URL to fetch content from
        
    Returns:
        The page content as a string, or None if the request failed
    """
    try:
        logger.info(f"Fetching content from {url}")
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching content: {e}")
        return None


def calculate_content_hash(content: str) -> str:
    """
    Calculate a hash of the content to detect changes.
    
    Args:
        content: The content to hash
        
    Returns:
        The SHA-256 hash of the content
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def has_content_changed(content: str) -> bool:
    """
    Check if the content has changed since the last run.
    
    Args:
        content: The current content
        
    Returns:
        True if the content has changed, False otherwise
    """
    current_hash = calculate_content_hash(content)
    
    if not HASH_FILE.exists():
        logger.info("No previous hash found, considering content as new")
        return True
    
    with open(HASH_FILE, 'r') as f:
        previous_hash = f.read().strip()
    
    has_changed = current_hash != previous_hash
    if has_changed:
        logger.info("Content has changed since last run")
    else:
        logger.info("No changes detected in content")
    
    return has_changed


def save_content_hash(content: str) -> None:
    """
    Save the hash of the current content.
    
    Args:
        content: The content to hash and save
    """
    current_hash = calculate_content_hash(content)
    with open(HASH_FILE, 'w') as f:
        f.write(current_hash)
    logger.info(f"Saved new content hash: {current_hash[:8]}...")


def save_html_content(content: str) -> Path:
    """
    Save the raw HTML content to a file.
    
    Args:
        content: The HTML content to save
        
    Returns:
        The path to the saved file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"schedule_{timestamp}.html"
    file_path = HTML_DIR / filename
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"Saved HTML content to {file_path}")
    return file_path


def parse_personnel_schedule(soup: BeautifulSoup) -> Dict:
    """
    Parse the personnel schedule (residents/CRNAs) from the HTML.
    
    Args:
        soup: BeautifulSoup object of the HTML content
        
    Returns:
        A dictionary containing the parsed personnel schedule data
    """
    logger.info("Parsing personnel schedule")
    
    # Extract schedule entries
    schedule_data = {}
    
    # Find all subgroup titles (CA-0, CA-1, etc.)
    subgroups = soup.select('.subgroup_title')
    
    for subgroup in subgroups:
        group_name = subgroup.text.strip()
        schedule_data[group_name] = []
        
        # Get all schedule entries for this subgroup
        current_element = subgroup.next_sibling
        
        while current_element and not (hasattr(current_element, 'name') and 
                                      current_element.name == 'div' and 
                                      'subgroup_title' in current_element.get('class', [])):
            if hasattr(current_element, 'name') and current_element.name == 'div' and 'schedule_entry' in current_element.get('class', []):
                entry = {}
                
                # Extract person name
                person_span = current_element.select_one('.person')
                if person_span:
                    entry['person'] = person_span.text.strip()
                
                # Extract rotation
                rotation_span = current_element.select_one('.rotation')
                if rotation_span:
                    # Remove parentheses from rotation text
                    rotation_text = rotation_span.text.strip()
                    entry['rotation'] = rotation_text.strip('()')
                
                # Extract assignment
                assignment_div = current_element.select_one('.assignment')
                if assignment_div:
                    entry['assignment'] = assignment_div.text.strip()
                
                # Extract comment if present
                comment_div = current_element.select_one('.comment')
                if comment_div:
                    entry['comment'] = comment_div.text.strip()
                
                schedule_data[group_name].append(entry)
            
            # Move to the next element
            if hasattr(current_element, 'next_sibling'):
                current_element = current_element.next_sibling
            else:
                break
    
    logger.info(f"Parsed personnel schedule with {sum(len(entries) for entries in schedule_data.values())} entries")
    return schedule_data


def parse_procedure_schedule(soup: BeautifulSoup) -> Dict:
    """
    Parse the procedure schedule by room from the HTML.
    
    Args:
        soup: BeautifulSoup object of the HTML content
        
    Returns:
        A dictionary containing the parsed procedure schedule data
    """
    logger.info("Parsing procedure schedule")
    
    procedure_data = {}
    
    # Find all table rows with room data
    room_rows = soup.select('tr[data-orwatch-room]')
    
    for row in room_rows:
        # Get the room name
        room_name = row.get('data-orwatch-room')
        
        if room_name not in procedure_data:
            procedure_data[room_name] = []
        
        # Create a procedure entry
        procedure = {}
        
        # Extract time
        time_span = row.select_one('.time')
        if time_span:
            procedure['time'] = time_span.text.strip()
        
        # Extract personnel
        personnel_td = row.select('td')[2] if len(row.select('td')) > 2 else None
        if personnel_td:
            personnel = []
            for person_span in personnel_td.select('.person'):
                personnel.append(person_span.text.strip())
            
            if personnel:
                procedure['personnel'] = personnel
        
        # Extract patient age if available
        age_td = row.select('td')[3] if len(row.select('td')) > 3 else None
        if age_td and age_td.text.strip():
            procedure['patient_age'] = age_td.text.strip()
        
        # Extract procedure description
        desc_td = row.select('td')[-1] if row.select('td') else None
        if desc_td:
            small_tags = desc_td.select('small')
            if len(small_tags) > 0:
                # First small tag contains procedure description
                desc_text = small_tags[0].text.strip()
                
                # Extract CPT codes if present
                cpt_codes = []
                cpt_links = small_tags[0].select('a.intranet')
                for link in cpt_links:
                    href = link.get('href', '')
                    if 'cpt=' in href:
                        cpt_code = href.split('cpt=')[1].split('&')[0] if '&' in href else href.split('cpt=')[1]
                        cpt_codes.append(cpt_code)
                
                # Extract anesthesia type if present
                anesthesia_type = None
                if '(' in desc_text and ')' in desc_text:
                    last_paren = desc_text.rfind('(')
                    if last_paren != -1 and last_paren < desc_text.rfind(')'):
                        anesthesia_type = desc_text[last_paren+1:desc_text.rfind(')')].strip()
                
                procedure['description'] = desc_text
                if cpt_codes:
                    procedure['cpt_codes'] = cpt_codes
                if anesthesia_type:
                    procedure['anesthesia_type'] = anesthesia_type
            
            # Second small tag contains surgeon name
            if len(small_tags) > 1:
                surgeon_span = small_tags[1].select_one('span')
                if surgeon_span:
                    procedure['surgeon'] = surgeon_span.text.strip()
        
        # Only add non-empty procedures
        if procedure:
            procedure_data[room_name].append(procedure)
    
    # Remove empty rooms
    procedure_data = {k: v for k, v in procedure_data.items() if v}
    
    logger.info(f"Parsed procedure schedule with {sum(len(procedures) for procedures in procedure_data.values())} procedures across {len(procedure_data)} rooms")
    return procedure_data


def parse_schedule(html_content: str) -> Dict:
    """
    Parse the schedule HTML content into a structured format.
    
    Args:
        html_content: The HTML content to parse
        
    Returns:
        A dictionary containing the parsed schedule data
    """
    logger.info("Parsing schedule content")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract the date
    date_span = soup.select_one('.date')
    date_str = date_span.text if date_span else "Unknown Date"
    
    # Format the date nicely if it's a valid datetime
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        formatted_date = date_obj.strftime("%A, %B %d, %Y")
    except ValueError:
        formatted_date = date_str
    
    # Extract global comments
    global_comments_div = soup.select_one('.global_comments')
    global_comments = global_comments_div.text.strip() if global_comments_div else ""
    
    # Parse personnel schedule (residents/CRNAs)
    personnel_schedule = parse_personnel_schedule(soup)
    
    # Parse procedure schedule by room
    procedure_schedule = parse_procedure_schedule(soup)
    
    # Create the final structured data
    parsed_data = {
        'date': date_str,
        'formatted_date': formatted_date,
        'global_comments': global_comments,
        'personnel_schedule': personnel_schedule,
        'procedure_schedule': procedure_schedule,
        'parsed_at': datetime.now().isoformat()
    }
    
    return parsed_data


def save_parsed_data(parsed_data: Dict) -> Path:
    """
    Save the parsed data to a JSON file.
    
    Args:
        parsed_data: The parsed schedule data
        
    Returns:
        The path to the saved file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"schedule_{timestamp}.json"
    file_path = JSON_DIR / filename
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(parsed_data, f, indent=2)
    
    logger.info(f"Saved parsed data to {file_path}")
    return file_path


def find_person_assignment(parsed_data: Dict, person_name: str) -> Dict:
    """
    Find the assignment details for a specific person.
    
    Args:
        parsed_data: The parsed schedule data
        person_name: The name of the person to find (e.g., "Last,F")
        
    Returns:
        A dictionary containing the person's assignment details
    """
    logger.info(f"Finding assignment for {person_name}")
    
    # Normalize the person name for case-insensitive comparison
    person_name_lower = person_name.lower()
    
    # Initialize the result
    result = {
        'date': parsed_data['formatted_date'],
        'person': person_name,
        'found': False,
        'personnel_info': None,
        'room_assignment': None,
        'cases': []
    }
    
    # Search for the person in the personnel schedule
    for group, entries in parsed_data['personnel_schedule'].items():
        for entry in entries:
            if 'person' in entry and entry['person'].lower() == person_name_lower:
                result['found'] = True
                result['personnel_info'] = {
                    'group': group,
                    **entry
                }
                break
        if result['found']:
            break
    
    # If the person was found and has an assignment
    if result['found'] and 'assignment' in result['personnel_info']:
        assignment = result['personnel_info']['assignment']
        
        # Check if the assignment corresponds to a room in the procedure schedule
        if assignment in parsed_data['procedure_schedule']:
            result['room_assignment'] = assignment
            result['cases'] = parsed_data['procedure_schedule'][assignment]
        else:
            # Search for the person in all procedure rooms
            for room, procedures in parsed_data['procedure_schedule'].items():
                for procedure in procedures:
                    if 'personnel' in procedure and any(p.lower() == person_name_lower for p in procedure['personnel']):
                        if result['room_assignment'] is None:
                            result['room_assignment'] = room
                        if room not in [case['room'] for case in result['cases']]:
                            for proc in procedures:
                                proc_copy = proc.copy()
                                proc_copy['room'] = room
                                result['cases'].append(proc_copy)
                        break
    
    # If no cases were found but the person was found in the personnel schedule
    if result['found'] and not result['cases']:
        logger.info(f"No specific cases found for {person_name}")
    elif not result['found']:
        logger.info(f"Person {person_name} not found in the schedule")
    else:
        logger.info(f"Found {len(result['cases'])} cases for {person_name}")
    
    return result


def print_person_assignment(assignment: Dict) -> None:
    """
    Print the assignment details for a person in a readable format.
    
    Args:
        assignment: The assignment details dictionary
    """
    if not assignment['found']:
        print(f"\nPerson '{assignment['person']}' not found in the schedule for {assignment['date']}.")
        return
    
    print(f"\n=== Assignment for {assignment['person']} on {assignment['date']} ===\n")
    
    # Print personnel info
    if assignment['personnel_info']:
        print("Personnel Information:")
        print(f"  Group: {assignment['personnel_info']['group']}")
        if 'rotation' in assignment['personnel_info']:
            print(f"  Rotation: {assignment['personnel_info']['rotation']}")
        if 'assignment' in assignment['personnel_info']:
            print(f"  Assignment: {assignment['personnel_info']['assignment']}")
        if 'comment' in assignment['personnel_info']:
            print(f"  Comment: {assignment['personnel_info']['comment']}")
        print()
    
    # Print room assignment
    if assignment['room_assignment']:
        print(f"Room Assignment: {assignment['room_assignment']}")
        print()
    
    # Print cases
    if assignment['cases']:
        print("Cases:")
        for i, case in enumerate(assignment['cases'], 1):
            print(f"  Case {i}:")
            if 'room' in case and case['room'] != assignment['room_assignment']:
                print(f"    Room: {case['room']}")
            if 'time' in case:
                print(f"    Time: {case['time']}")
            if 'personnel' in case:
                print(f"    Team: {', '.join(case['personnel'])}")
            if 'patient_age' in case:
                print(f"    Patient Age: {case['patient_age']}")
            if 'description' in case:
                print(f"    Procedure: {case['description']}")
            if 'anesthesia_type' in case:
                print(f"    Anesthesia: {case['anesthesia_type']}")
            if 'surgeon' in case:
                print(f"    Surgeon: {case['surgeon']}")
            print()
    else:
        print("No specific cases found for this assignment.")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Daily Schedule Scraper')
    parser.add_argument('--person', type=str, help='Name of the person to find assignments for (e.g., "Last,F")')
    return parser.parse_args()


def main() -> None:
    """Main function to run the scraper."""
    # Parse command line arguments
    args = parse_arguments()
    
    logger.info("Starting daily schedule scraper")
    
    # Set up directories
    setup_directories()
    
    # Fetch the content
    content = get_page_content(URL)
    if not content:
        logger.error("Failed to fetch content, exiting")
        return
    
    # Check if content has changed
    content_changed = has_content_changed(content)
    
    # Parse the content
    parsed_data = parse_schedule(content)
    
    # If a specific person was requested, find and print their assignment
    if args.person:
        person_assignment = find_person_assignment(parsed_data, args.person)
        print_person_assignment(person_assignment)
    
    # Only save if content has changed
    if content_changed:
        # Save the raw HTML
        html_path = save_html_content(content)
        
        # Save the parsed data
        json_path = save_parsed_data(parsed_data)
        
        # Save the content hash
        save_content_hash(content)
        
        logger.info(f"Successfully processed and saved schedule data")
        logger.info(f"HTML saved to: {html_path}")
        logger.info(f"JSON saved to: {json_path}")
    else:
        logger.info("No changes detected, skipping save")


if __name__ == "__main__":
    main() 