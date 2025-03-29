import os
import io
import requests
import csv
from datetime import datetime, timedelta, UTC
from slack_bolt import App
from dotenv import load_dotenv

load_dotenv()

CALENDLY_TOKEN = os.environ.get("CALENDLY_TOKEN")
CALENDLY_USER_URI = os.environ.get("CALENDLY_USER_URI")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")


CALENDLY_API = "https://api.calendly.com"
HEADERS = {"Authorization": f"Bearer {CALENDLY_TOKEN}"}
app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)


def load_students():
    students = {}
    csv_data = os.environ.get("STUDENTS_DATA")
    if csv_data:
        reader = csv.DictReader(io.StringIO(csv_data))
        for row in reader:
            students[row["name"]] = {
                "email": row["email"].strip().lower(),
                "slack_id": row["slack_id"].strip() if "slack_id" in row else None
            }
    return students


STUDENTS = load_students()


def get_scheduled_students():
    api_calls = 0
    today = datetime.now(UTC)
    # Monday
    start_of_week = today - timedelta(days=today.weekday())
    # Friday
    end_of_week = start_of_week + timedelta(days=4)

    min_time = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
    max_time = end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat() + "Z"

    url = f"{CALENDLY_API}/scheduled_events?user={CALENDLY_USER_URI}&min_start_time={min_time}&max_start_time={max_time}"
    response = requests.get(url, headers=HEADERS)
    api_calls += 1

    if response.status_code != 200:
        print(f"Error fetching events: {response.status_code} - {response.text}")
        return set(), api_calls

    events = response.json()["collection"]
    scheduled_emails = set()

    for event in events:
        event_uuid = event["uri"].split("/")[-1]
        invitees_url = f"{CALENDLY_API}/scheduled_events/{event_uuid}/invitees"
        invitees_response = requests.get(invitees_url, headers=HEADERS)
        api_calls += 1

        if invitees_response.status_code != 200:
            print(f"Error fetching invitees for event {event_uuid}: {invitees_response.text}")
            continue

        invitees = invitees_response.json()["collection"]
        for invitee in invitees:
            scheduled_emails.add(invitee["email"].lower())

    return scheduled_emails, api_calls



def notify_missing_students():
    today = datetime.now(UTC)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=4)
    print(f"Checking schedules for this week (Monday {start_of_week:%Y-%m-%d} to Friday {end_of_week:%Y-%m-%d})...")
    scheduled_emails, api_calls = get_scheduled_students()
    print(f"API calls made this run: {api_calls}")
    print(f"Scheduled emails: {scheduled_emails}")

    for student_name, info in STUDENTS.items():
        print(f"Processing {student_name}: Email={info['email']}, Slack ID={info['slack_id']}")
        if info["email"] not in scheduled_emails:
            if not info["slack_id"]:
                print(f"Skipping {student_name} (no Slack ID found).")
                continue

            message = f"Hey {student_name}, I noticed you haven’t scheduled a meeting with me for this week. Please book a slot here: https://calendly.com/romanibanez-alex"
            try:
                response = app.client.chat_postMessage(channel=info["slack_id"], text=message)
                if response["ok"]:
                    print(f"Sent DM to {student_name} (Slack ID: {info['slack_id']})")
                else:
                    print(f"Failed to send DM to {student_name}: {response['error']}")
            except Exception as e:
                print(f"Error sending DM to {student_name}: {type(e).__name__} - {str(e)}")
        else:
            print(f"{student_name} already has a scheduled meeting this week.")


def test_slack():
    for student_name, info in STUDENTS.items():
        if info["slack_id"]:
            try:
                response = app.client.chat_postMessage(channel=info["slack_id"], text=f"Test message to {student_name}")
                print(f"Test message to {student_name}: {response['ok']}")
            except Exception as e:
                print(f"Test failed for {student_name}: {e}")


if __name__ == "__main__":
    print("\nRunning notification check...")
    notify_missing_students()