import os
import io
import requests
import csv
import sys
from datetime import datetime, timedelta, UTC
from slack_bolt import App
from dotenv import load_dotenv


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


# Start logging
log("Script starting...")

# Load from .env file if exists (for local development)
load_dotenv()

# Get environment variables from GitHub secrets
CALENDLY_TOKEN = os.environ.get("CALENDLY_TOKEN")
CALENDLY_USER_URI = os.environ.get("CALENDLY_USER_URI")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

# Check if required environment variables are set (without printing their values)
if not CALENDLY_TOKEN:
    log("ERROR: CALENDLY_TOKEN is not set")
    sys.exit(1)
if not CALENDLY_USER_URI:
    log("ERROR: CALENDLY_USER_URI is not set")
    sys.exit(1)
if not SLACK_BOT_TOKEN:
    log("ERROR: SLACK_BOT_TOKEN is not set")
    sys.exit(1)
if not SLACK_SIGNING_SECRET:
    log("ERROR: SLACK_SIGNING_SECRET is not set")
    sys.exit(1)

log("All required environment variables are set")

CALENDLY_API = "https://api.calendly.com"
HEADERS = {"Authorization": f"Bearer {CALENDLY_TOKEN}"}

try:
    log("Initializing Slack app...")
    app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
    log("Slack app initialized successfully")
except Exception as e:
    log(f"ERROR initializing Slack app: {type(e).__name__} - {str(e)}")
    sys.exit(1)


def load_students():
    students = {}
    csv_data = os.environ.get("STUDENTS_DATA", "").replace("\\n", "\n")
    log("Raw STUDENTS_DATA preview:")
    print(csv_data)

    if not csv_data:
        log("ERROR: STUDENTS_DATA environment variable is not set")
        return {}

    try:
        log(f"Parsing student data (length: {len(csv_data)} characters)")
        csv_file = io.StringIO(csv_data.replace("\\n", "\n"))
        reader = csv.DictReader(csv_file)

        student_count = 0
        for row in reader:
            student_count += 1
            # Don't log actual student data, just count
            students[row["name"]] = {
                "email": row["email"].strip().lower(),
                "slack_id": row["slack_id"].strip() if "slack_id" in row else None
            }

        log(f"Successfully loaded {student_count} students")
    except Exception as e:
        log(f"ERROR loading students: {type(e).__name__} - {str(e)}")

    return students


STUDENTS = load_students()
if not STUDENTS:
    log("ERROR: No students were loaded. Check STUDENTS_DATA format")
    sys.exit(1)


def get_scheduled_students():
    api_calls = 0
    today = datetime.now(UTC)
    # Monday
    start_of_week = today - timedelta(days=today.weekday())
    # Friday
    end_of_week = start_of_week + timedelta(days=4)

    min_time = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
    max_time = end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat() + "Z"

    log(f"Checking schedules from {start_of_week:%Y-%m-%d} to {end_of_week:%Y-%m-%d}")

    url = f"{CALENDLY_API}/scheduled_events?user={CALENDLY_USER_URI}&min_start_time={min_time}&max_start_time={max_time}"
    try:
        log("Making API call to Calendly for scheduled events")
        response = requests.get(url, headers=HEADERS)
        api_calls += 1

        if response.status_code != 200:
            log(f"ERROR fetching events: {response.status_code} - {response.text}")
            return set(), api_calls

        events = response.json()["collection"]
        log(f"Found {len(events)} scheduled events")

        scheduled_emails = set()

        for event in events:
            event_uuid = event["uri"].split("/")[-1]
            invitees_url = f"{CALENDLY_API}/scheduled_events/{event_uuid}/invitees"

            log(f"Fetching invitees for event {event_uuid}")
            invitees_response = requests.get(invitees_url, headers=HEADERS)
            api_calls += 1

            if invitees_response.status_code != 200:
                log(f"ERROR fetching invitees for event {event_uuid}: {invitees_response.text}")
                continue

            invitees = invitees_response.json()["collection"]
            log(f"Found {len(invitees)} invitees for event {event_uuid}")

            for invitee in invitees:
                scheduled_emails.add(invitee["email"].lower())

        log(f"Total of {len(scheduled_emails)} unique scheduled emails found")
        return scheduled_emails, api_calls

    except Exception as e:
        log(f"ERROR during API calls: {type(e).__name__} - {str(e)}")
        return set(), api_calls


def notify_missing_students():
    log("Starting notification process...")

    scheduled_emails, api_calls = get_scheduled_students()
    log(f"API calls made this run: {api_calls}")

    notifications_sent = 0
    students_already_scheduled = 0

    for student_name, info in STUDENTS.items():
        log(f"Processing student: {student_name}")

        if info["email"] not in scheduled_emails:
            if not info["slack_id"]:
                log(f"Skipping {student_name} (no Slack ID found)")
                continue

            message = f"Hey {student_name}, I noticed you haven't scheduled a meeting with me for this week. Please book a slot here: https://calendly.com/romanibanez-alex"
            try:
                log(f"Sending Slack message to {student_name}")
                response = app.client.chat_postMessage(channel=info["slack_id"], text=message)

                if response["ok"]:
                    log(f"Successfully sent DM to {student_name}")
                    notifications_sent += 1
                else:
                    log(f"Failed to send DM to {student_name}: {response['error']}")
            except Exception as e:
                log(f"ERROR sending DM to {student_name}: {type(e).__name__} - {str(e)}")
        else:
            log(f"{student_name} already has a scheduled meeting this week")
            students_already_scheduled += 1

    log(f"Notification process complete. Sent {notifications_sent} notifications. {students_already_scheduled} students already scheduled.")


if __name__ == "__main__":
    log("=== Running notification check ===")
    try:
        notify_missing_students()
        log("Script completed successfully")
    except Exception as e:
        log(f"ERROR in main execution: {type(e).__name__} - {str(e)}")
        sys.exit(1)