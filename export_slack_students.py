import os
import sys
import csv
from slack_bolt import App
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Slack API credentials
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

if not SLACK_BOT_TOKEN or not SLACK_SIGNING_SECRET:
    print("ERROR: Slack API credentials not found. Please set SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET in .env file.")
    sys.exit(1)

# Initialize Slack app
try:
    app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
    print("Slack app initialized successfully")
except Exception as e:
    print(f"ERROR initializing Slack app: {type(e).__name__} - {str(e)}")
    sys.exit(1)


def get_channels_with_prefix(prefix="alex-"):
    """Get all channels that start with the given prefix"""
    channels = []
    try:
        print(f"Fetching channels with prefix '{prefix}'...")

        # Initial call with cursor=None
        cursor = None
        while True:
            params = {"exclude_archived": True, "limit": 1000}
            if cursor:
                params["cursor"] = cursor

            # Get public channels
            response = app.client.conversations_list(**params)

            if not response["ok"]:
                print(f"ERROR getting channels list: {response.get('error', 'Unknown error')}")
                break

            for channel in response["channels"]:
                if channel["name"].startswith(prefix.lower()):
                    channels.append({
                        "id": channel["id"],
                        "name": channel["name"]
                    })
                    print(f"Found channel: {channel['name']}")

            # Check if we need to continue pagination
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        print(f"Found {len(channels)} channels with prefix '{prefix}'")

    except Exception as e:
        print(f"ERROR fetching channels: {type(e).__name__} - {str(e)}")

    return channels


def get_channel_members(channel_id):
    """Get all members of a specific channel"""
    members = []
    try:
        print(f"Fetching members for channel {channel_id}...")

        # Initial call with cursor=None
        cursor = None
        while True:
            params = {"channel": channel_id, "limit": 1000}
            if cursor:
                params["cursor"] = cursor

            response = app.client.conversations_members(**params)

            if not response["ok"]:
                print(f"ERROR getting channel members: {response.get('error', 'Unknown error')}")
                break

            members.extend(response["members"])

            # Check if we need to continue pagination
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        print(f"Found {len(members)} members in channel {channel_id}")

    except Exception as e:
        print(f"ERROR fetching channel members: {type(e).__name__} - {str(e)}")

    return members


def get_user_info(user_id):
    """Get detailed information about a specific user"""
    try:
        response = app.client.users_info(user=user_id)

        if not response["ok"]:
            print(f"ERROR getting user info: {response.get('error', 'Unknown error')}")
            return None

        user = response["user"]

        # Skip bots, deactivated accounts, etc.
        if (
                user.get("is_bot") or
                user.get("deleted") or
                user.get("is_app_user") or
                user.get("id") == "USLACKBOT"
        ):
            return None

        profile = user.get("profile", {})
        return {
            "name": profile.get("real_name", ""),
            "email": profile.get("email", ""),
            "slack_id": user["id"]
        }
    except Exception as e:
        print(f"ERROR fetching user info: {type(e).__name__} - {str(e)}")
        return None


def save_to_csv(students, filename="students.csv"):
    """Save student information to a CSV file"""
    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "email", "slack_id"])
            writer.writeheader()
            for student in students:
                writer.writerow(student)
        print(f"Successfully saved {len(students)} students to {filename}")
    except Exception as e:
        print(f"ERROR saving to CSV: {type(e).__name__} - {str(e)}")


def main():
    print("=== Starting Slack Channel Member Export ===")

    # Get all channels with prefix "alex-"
    channels = get_channels_with_prefix("alex-cloud-")

    if not channels:
        print("No channels found with prefix 'alex-'. Exiting.")
        return

    # Collect all unique member IDs from these channels
    all_members = set()
    for channel in channels:
        channel_members = get_channel_members(channel["id"])
        print(f"Channel '{channel['name']}' has {len(channel_members)} members")
        all_members.update(channel_members)

    print(f"Found {len(all_members)} unique members across all alex-* channels")

    # Get detailed information for each member
    students = []
    for member_id in all_members:
        user_info = get_user_info(member_id)
        if user_info and user_info["email"]:  # Only include users with email addresses
            students.append(user_info)

    print(f"Collected information for {len(students)} valid users")

    # Save to CSV
    save_to_csv(students)

    print("=== Export completed ===")


if __name__ == "__main__":
    main()