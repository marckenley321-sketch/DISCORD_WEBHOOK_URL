import json
import os
import requests

# Fallback URLs covering both main and dev branches
URLS = [
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/main/listings.json",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/listings.json"
]

CACHE_FILE = "seen_ids.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

TARGET_KEYWORDS = ["software", "engineer", "quant", "developer", "data", "ai", "machine learning", "intern"]

def send_discord_notification(job):
    locations = ", ".join(job.get("locations", [])) or "Remote / Not Listed"
    payload = {
        "username": "Simplify Internship Tracker",
        "embeds": [
            {
                "title": f"🚨 New Role: {job.get('company_name')} - {job.get('title')}",
                "url": job.get("url"),
                "color": 3447003,
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
            try:
                seen_ids = set(json.load(f))
            except Exception:
                seen_ids = set()
    else:
        seen_ids = set()

    listings = None
    for url in URLS:
        response = requests.get(url)
        if response.status_code == 200:
            try:
                listings = response.json()
                print(f"Successfully fetched listings from {url}")
                break
            except Exception:
                continue

    if listings is None:
        print("Failed to fetch listings from all endpoints. Verify repository branch and file structure.")
        return

    new_seen_ids = set(seen_ids)
    new_jobs_found = 0
    first_run = len(seen_ids) == 0

    for job in listings:
        job_id = job.get("id")
        title = job.get("title", "").lower()
        is_active = job.get("active", True)
        is_visible = job.get("is_visible", True)

        if job_id and job_id not in seen_ids and is_active and is_visible:
            if not first_run and any(kw in title for kw in TARGET_KEYWORDS):
                send_discord_notification(job)
                new_jobs_found += 1
            new_seen_ids.add(job_id)

    if first_run:
        print(f"Initial run: cached {len(new_seen_ids)} existing postings without alerting.")
    else:
        print(f"Dispatched {new_jobs_found} new alerts.")

    with open(CACHE_FILE, "w") as f:
        json.dump(list(new_seen_ids), f)

if __name__ == "__main__":
    main()
