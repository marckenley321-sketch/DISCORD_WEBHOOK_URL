import json
import os
import re
import request

README_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/main/README.md"
CACHE_FILE = "seen_ids.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

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
                    {"name": "Application Link", "value": f"[Apply Here]({link})", "inline": False}
                ],
                "footer": {"text": "SimplifyJobs Tracker Alert"}
            }
        ]
    }
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json=payload)

def parse_markdown_table(md_text):
    jobs = []
    row_pattern = re.compile(r"^\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|", re.MULTILINE)
    link_pattern = re.compile(r"\[.*?\]\((https?://[^\)]+)\)")

    for match in row_pattern.finditer(md_text):
        company_raw, role_raw, loc_raw, link_col = match.groups()

        company = re.sub(r"\[.*?\]\(.*?\)|\*|_|`", "", company_raw).strip()
        role = re.sub(r"\[.*?\]\(.*?\)|\*|_|`", "", role_raw).strip()
        location = re.sub(r"<br\s*/?>", ", ", loc_raw).strip()

        if "Company" in company or "---" in company or not company:
            continue

        links = link_pattern.findall(link_col)
        job_url = links[0] if links else ""
        if not job_url:
            raw_url = re.search(r"https?://[^\s\|]+", link_col)
            job_url = raw_url.group(0) if raw_url else ""

        job_id = f"{company.lower()}-{role.lower()}"

        if job_id and job_url:
            jobs.append({
                "id": job_id,
                "company": company,
                "role": role,
                "location": location,
                "url": job_url
            })
    return jobs

def main():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try:
                seen_ids = set(json.load(f))
            except Exception:
                seen_ids = set()
    else:
        seen_ids = set()

    response = requests.get(README_URL)
    if response.status_code != 200:
        print(f"Failed to fetch README: {response.status_code}")
        return

    jobs = parse_markdown_table(response.text)
    print(f"Parsed {len(jobs)} total jobs from Simplify README.")

    new_seen_ids = set(seen_ids)
    new_jobs_found = 0
    first_run = len(seen_ids) == 0

    for job in jobs:
        job_id = job["id"]
        role_lower = job["role"].lower()

        if job_id not in seen_ids:
            if not first_run and any(kw in role_lower for kw in TARGET_KEYWORDS):
                send_discord_notification(job["company"], job["role"], job["location"], job["url"])
                new_jobs_found += 1
            new_seen_ids.add(job_id)

    if first_run:
        print(f"Initial run: cached {len(new_seen_ids)} existing postings without spamming Discord.")
    else:
        print(f"Dispatched {new_jobs_found} new alerts.")

    with open(CACHE_FILE, "w") as f:
        json.dump(list(new_seen_ids), f)

if __name__ == "__main__":
    main()
