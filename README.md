# Daily Schedule Scraper

A Python script that scrapes the daily assignments schedule from Mount Sinai's internal website, parses the content, and stores it locally. The script only saves new content when changes are detected.

## Features

- Fetches schedule data from the specified URL
- Parses HTML content into structured JSON format with two main components:
  - Personnel schedule (residents/CRNAs assignments)
  - Procedure schedule by room (including times, personnel, patient ages, procedure descriptions, CPT codes, and surgeons)
- Saves raw HTML and parsed JSON data
- Only saves new data when changes are detected (using content hashing)
- Comprehensive logging

## Requirements

- Python 3.10+
- `requests` library for HTTP requests
- `beautifulsoup4` library for HTML parsing

## Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/daily-schedule.git
cd daily-schedule
```

2. Make sure you're connected to the Mount Sinai VPN

3. Install dependencies:

```bash
uv add -r requirements.txt
```

4. Set up the data directories:

```bash
uv run setup_data_dirs.py
```

## Usage

### Running the Scraper Once

Run the script:

```bash
uv run daily_schedule_scraper.py
```

### Running the Scheduler

The scheduler will run the scraper at regular intervals (default: every hour):

```bash
uv run run_scheduler.py
```

### Setting Up as a Systemd Service

To run the scheduler as a systemd service:

1. Copy the service file to the systemd directory:

```bash
sudo cp daily-schedule-scraper.service /etc/systemd/system/
```

2. Reload systemd:

```bash
sudo systemctl daemon-reload
```

3. Enable and start the service:

```bash
sudo systemctl enable daily-schedule-scraper.service
sudo systemctl start daily-schedule-scraper.service
```

4. Check the status:

```bash
sudo systemctl status daily-schedule-scraper.service
```

## Data Storage

The script creates the following directory structure:

```
data/
├── html/           # Raw HTML files
├── json/           # Parsed JSON data
└── last_content_hash.txt  # Hash of the last processed content
```

Each file is timestamped with the date and time it was created.

### JSON Structure

The JSON output has the following structure:

```json
{
  "date": "2025-03-03 00:00:00",
  "formatted_date": "Monday, March 03, 2025",
  "global_comments": "...",
  "personnel_schedule": {
    "CA-0": [
      {
        "person": "Name",
        "rotation": "Department",
        "assignment": "Location"
      },
      ...
    ],
    ...
  },
  "procedure_schedule": {
    "ROOM-1": [
      {
        "time": "2025-03-03 07:30:00",
        "personnel": ["Name1", "Name2"],
        "patient_age": "74",
        "description": "Procedure description",
        "cpt_codes": ["12345", "67890"],
        "anesthesia_type": "General",
        "surgeon": "Surgeon Name"
      },
      ...
    ],
    ...
  },
  "parsed_at": "2025-02-28T16:05:03.338453"
}
```

## Automation

### Using Cron

To run this script automatically on a schedule using cron:

```bash
# Run every hour
0 * * * * cd /path/to/daily-schedule && /path/to/uv run daily_schedule_scraper.py
```

### Using Systemd Timer

Alternatively, you can use a systemd timer instead of the scheduler script:

1. Create a timer file `daily-schedule-scraper.timer`:

```
[Unit]
Description=Run Daily Schedule Scraper hourly

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
```

2. Install and enable the timer:

```bash
sudo cp daily-schedule-scraper.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable daily-schedule-scraper.timer
sudo systemctl start daily-schedule-scraper.timer
```

## License

This project is for internal use only. 