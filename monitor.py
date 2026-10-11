import json
import os
import requests

LISTINGS_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"
CACHE_FILE = "seen_ids.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

TARGET_CATEGORIES = {"Software", "Software Engineering", "AI/ML/Data", "Data Science, AI & Machine Learning"}
TARGET_KEYWORDS = ["software", "engineer", "quant", "developer", "data", "ai", "machine learning"]


def send_discord_notification(company, role, location, link):
    payload = {
        "username": "Simplify Internship Tracker",
        "embeds": [
            {
                "title": f"🚨 New Role: {company} - {role}",
                "url": link,
                "color": 3447003,
                "fields": [
                    {"name": "Company", "value": company, "inline": True},
                    {"name": "Role", "value": role, "inline": True},
                    {"name": "Location", "value": location or "Not Listed", "inline": True},
                    {"name": "Application Link", "value": f"[Apply Here]({link})", "inline": False},
                ],
                "footer": {"text": "SimplifyJobs Tracker Alert"},
            }
        ],
    }
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json=payload, timeout=15)


def matches(job):
    title = (job.get("title") or "").lower()
    category = job.get("category") or ""
    if category in TARGET_CATEGORIES:
        return True
    return any(kw in title for kw in TARGET_KEYWORDS)


def main():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try:
                seen_ids = set(json.load(f))
            except Exception:
                seen_ids = set()
    else:
        seen_ids = set()

    try:
        response = requests.get(LISTINGS_URL, timeout=30)
        response.raise_for_status()
        listings = response.json()
    except Exception as e:
        print(f"Failed to fetch listings feed: {e}")
        return

    jobs = []
    for item in listings:
        if not item.get("active", True) or not item.get("is_visible", True):
            continue
        company = (item.get("company_name") or "").strip()
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not company or not title:
            continue
        job_id = item.get("id") or f"{company.lower()}|{title.lower()}"
        location = ", ".join(item.get("locations") or [])
        jobs.append({"id": job_id, "company": company, "role": title, "location": location, "url": url, "job": item})

    print(f"Parsed {len(jobs)} active listings from Simplify feed.")

    new_seen_ids = set(seen_ids)
    new_jobs_found = 0
    first_run = len(seen_ids) == 0

    for job in jobs:
        job_id = job["id"]
        if job_id not in seen_ids:
            if not first_run and matches(job["job"]):
                send_discord_notification(job["company"], job["role"], job["location"], job["url"])
                new_jobs_found += 1
            new_seen_ids.add(job_id)

    if first_run:
        print(f"Initial run: cached {len(new_seen_ids)} existing postings without spamming Discord.")
    else:
        print(f"Dispatched {new_jobs_found} new alerts.")

    with open(CACHE_FILE, "w") as f:
        json.dump(sorted(new_seen_ids), f)


if __name__ == "__main__":
    main()
