import json
import os
import requests

# Simplify repository data source
DATA_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/listings.json"
CACHE_FILE = "seen_ids.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Keywords you care about (case-insensitive)
TARGET_KEYWORDS = ["software", "engineer", "quant", "developer", "data", "ai", "machine learning"]

def send_discord_notification(job):
    locations = ", ".join(job.get("locations", [])) or "Remote / Not Listed"
    payload = {
        "username": "Simplify Internship Tracker",
        "embeds": [
            {
                "title": f"🚨 New Role: {job.get('company_name')} - {job.get('title')}",
                "url": job.get("url"),
                "color": 3447003,  # Blue
                "fields": [
                    {"name": "Company", "value": job.get("company_name", "N/A"), "inline": True},
                    {"name": "Location", "value": locations, "inline": True},
                    {"name": "Terms", "value": ", ".join(job.get("terms", [])), "inline": True},
                    {"name": "Application Link", "value": f"[Apply Here]({job.get('url')})", "inline": False}
                ],
                "footer": {"text": "SimplifyJobs Tracker Alert"}
            }
        ]
    }
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json=payload)

def main():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            seen_ids = set(json.load(f))
    else:
        seen_ids = set()

    response = requests.get(DATA_URL)
    if response.status_code != 200:
        print(f"Failed to fetch listings: {response.status_code}")
        return

    listings = response.json()
    new_seen_ids = set(seen_ids)
    new_jobs_found = 0

    for job in listings:
        job_id = job.get("id")
        title = job.get("title", "").lower()
        is_active = job.get("active", True)
        is_visible = job.get("is_visible", True)

        # If it's a new open job matching your keywords
        if job_id and job_id not in seen_ids and is_active and is_visible:
            if any(kw in title for kw in TARGET_KEYWORDS):
                send_discord_notification(job)
                new_jobs_found += 1
            new_seen_ids.add(job_id)

    print(f"Dispatched {new_jobs_found} new alerts.")

    # Save updated cache
    with open(CACHE_FILE, "w") as f:
        json.dump(list(new_seen_ids), f)

if __name__ == "__main__":
    main()
