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
- Extracts and displays detailed assignment information for a specific person
- Continuous monitoring of assignments with customizable intervals
- Push notifications to your iPhone when your schedule changes

## Requirements

- Python 3.10+
- `requests` library for HTTP requests
- `beautifulsoup4` library for HTML parsing
- Pushover app on your iPhone (optional, for push notifications)

## Setup

1. Clone the repository:

```bash
git clone https://github.com/kb1900/daily-schedule.git
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

5. (Optional) For push notifications:
   - Install the [Pushover app](https://pushover.net/) on your iPhone
   - Create an application token on the [Pushover website](https://pushover.net/apps/build):
     - Go to https://pushover.net/apps/build
     - Fill in the application details (Name: "Daily Schedule Monitor", Type: "Application")
     - Click "Create Application"
     - Save the API Token/Key that is generated (this is your application token)

## Usage

### Running the Scraper Once

Run the script:

```bash
uv run daily_schedule_scraper.py
```

### Finding Your Assignments

To find assignments for a specific person, use the `--person` flag followed by the person's name as it appears in the schedule (typically "Last,F" format):

```bash
uv run daily_schedule_scraper.py --person "Smith,J"
```

This will display:
- Your personnel information (group, rotation, assignment)
- Your room assignment
- All cases you're assigned to, including:
  - Time
  - Team members
  - Patient age
  - Procedure description
  - Anesthesia type
  - Surgeon

### Continuous Monitoring

The scheduler can run the scraper at regular intervals and optionally monitor a specific person's assignments:

```bash
# Basic scheduler (checks every hour)
uv run run_scheduler.py

# Monitor a specific person's assignments
uv run run_scheduler.py --person "Smith,J"

# Change the check interval (e.g., every 30 minutes)
uv run run_scheduler.py --interval 30

# Monitor a specific person with custom interval
uv run run_scheduler.py --person "Smith,J" --interval 15
```

When monitoring a specific person, the scheduler will:
- Display their assignments each time it checks
- Notify you of any changes to their schedule
- Continue running until stopped (Ctrl+C)

### Push Notifications

To receive push notifications on your iPhone when your schedule changes:

1. Install the Pushover app on your iPhone
2. Create an application on the [Pushover website](https://pushover.net/apps/build):
   - Go to https://pushover.net/apps/build
   - Fill in the application details:
     - Name: Daily Schedule Monitor
     - Type: Application
     - Description: Monitors changes to my daily schedule
   - Click "Create Application"
   - Save the API Token/Key that is generated (this is your application token)

3. Run the scheduler with the `--pushover-token` flag:

```bash
uv run run_scheduler.py --person "Smith,J" --pushover-token "YOUR_APP_TOKEN"
```

⚠️ **Important**: The `--pushover-token` parameter requires your application token (from step 2), NOT your user key. Your user key is already configured in the script.

You will receive notifications when:
- Monitoring starts
- Your schedule changes
- Errors occur
- Monitoring stops

The notifications include:
- A title indicating what happened
- A brief message with details
- Different priority levels for different events
- Different sounds for different notification types

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
├── html/                                # Raw HTML files
├── json/                                # Parsed JSON data
├── last_content_hash.txt                # Hash of the last processed content
└── last_schedule_hash_Smith_J.txt       # Hash of the last schedule for a person
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

# Run every hour and check a specific person's assignments
0 * * * * cd /path/to/daily-schedule && /path/to/uv run daily_schedule_scraper.py --person "Smith,J" > ~/my_schedule.txt

# Run every hour with push notifications
0 * * * * cd /path/to/daily-schedule && /path/to/uv run run_scheduler.py --person "Smith,J" --pushover-token "YOUR_APP_TOKEN" --interval 60
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

## Troubleshooting

### Pushover Notifications Not Working

If you're not receiving Pushover notifications:

1. **Check your application token**: Make sure you're using the application token from the Pushover website, not your user key. They are different!
2. **Verify your device name**: The default device name is set to "KBPHONE". If your device has a different name, update the `PUSHOVER_DEVICE` constant in the script.
3. **Check the logs**: Look at the `scheduler.log` file for any error messages related to Pushover.
4. **Test Pushover directly**: You can test your Pushover setup using curl:
   ```bash
   curl -s \
     --form-string "token=YOUR_APP_TOKEN" \
     --form-string "user=YOUR_USER_KEY" \
     --form-string "message=Test message" \
     https://api.pushover.net/1/messages.json
   ```

## License

This project is for internal use only. 