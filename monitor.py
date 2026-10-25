import hashlib
import json
import os
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse
import requests

CACHE_FILE = "seen_ids.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

TARGET_CATEGORIES = {
    "Software", "Software Engineering", "AI/ML/Data", 
    "Data Science, AI & Machine Learning", "Security", "IT"
}

TARGET_KEYWORDS = [
    "software", "engineer", "quant", "developer", "technology", 
    "data", "ai", "machine learning", "security", "support", "systems", "development"
]

SOURCES = [
    {
        "name": "SimplifyJobs",
        "url": "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json",
        "parser": "simplify_json",
    },
    {
        "name": "SpeedyApply",
        "url": "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md",
        "parser": "markdown_table",
    },
    {
        "name": "DreamworkHQ",
        "url": "https://raw.githubusercontent.com/dreamworkhq/Tech-Internships-2027/main/README.md",
        "parser": "markdown_table",
    },
    {
        "name": "LandedJobs",
        "url": "https://raw.githubusercontent.com/landedjobs/tech-internships/main/README.md",
        "parser": "markdown_table",
    },
]

# ----------------  ---------------- #

COMPANY_SUFFIXES = [
    r"\binc\b", r"\bllc\b", r"\bcorp\b", r"\bcorporation\b", 
    r"\btechnologies\b", r"\btechnology\b", r"\btech\b", 
    r"\bgroup\b", r"\blabs\b", r"\bsoftware\b", r"\bsystems\b"
]

ROLE_NOISE = [
    r"\bsummer\b", r"\b202[678]\b", r"\bintern\b", r"\binternship\b", 
    r"\bco-op\b", r"\bcoop\b", r"\buniversity\b", r"\bundergraduate\b",
    r"\bgraduate\b", r"\brole\b", r"\bposition\b"
]

def clean_company_name(name: str) -> str:
    cleaned = name.lower()
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    for suffix in COMPANY_SUFFIXES:
        cleaned = re.sub(suffix, "", cleaned)
    return re.sub(r"[^a-z0-9]", "", cleaned)

def clean_role_name(role: str) -> str:
    cleaned = role.lower()
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    
    cleaned = re.sub(r"\bswe\b", "software engineer", cleaned)
    cleaned = re.sub(r"\bml\b", "machine learning", cleaned)
    cleaned = re.sub(r"\bds\b", "data science", cleaned)
    cleaned = re.sub(r"\bai\b", "artificial intelligence", cleaned)
    
    for noise in ROLE_NOISE:
        cleaned = re.sub(noise, "", cleaned)
    return re.sub(r"[^a-z0-9]", "", cleaned)

def generate_fingerprint_id(company: str, role: str) -> str:
    """Generates a stable hash based on normalized company and role name."""
    comp_clean = clean_company_name(company)
    role_clean = clean_role_name(role)
    raw_key = f"fp:{comp_clean}:{role_clean}"
    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

# ----------------  ---------------- #

def send_discord_notification(source, company, role, location, link, posted_time):
    time_str = "Not Listed"
    if posted_time:
        if isinstance(posted_time, (int, float)):
            time_str = f"<t:{int(posted_time)}:f>"
        else:
            time_str = str(posted_time)

    payload = {
        "username": "Universal Internship Tracker",
        "embeds": [
            {
                "title": f"🚨 New Role: {company} - {role}",
                "url": link,
                "color": 3447003,
                "fields": [
                    {"name": "🏢 Company", "value": company, "inline": True},
                    {"name": "💼 Role", "value": role, "inline": True},
                    {"name": "📍 Location", "value": location or "Not Listed", "inline": True},
                    {"name": "🕒 Date Posted", "value": time_str, "inline": True},
                    {"name": "📡 Source", "value": f"`{source}`", "inline": True},
                    {"name": "🔗 Application Link", "value": f"[:link: Apply Here]({link})", "inline": False},
                ],
                "footer": {"text": "Multi-Repo Deduplicated Alert 🚀"},
            }
        ],
    }
    if WEBHOOK_URL:
        try:
            res = requests.post(WEBHOOK_URL, json=payload, timeout=15)
            res.raise_for_status()
        except Exception as e:
            print(f"Failed to post to Discord: {e}")

# ----------------  ---------------- #

def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return text.strip()

def matches_target(role_title: str, category: str = "") -> bool:
    if category in TARGET_CATEGORIES:
        return True
    title_lower = role_title.lower()
    return any(kw in title_lower for kw in TARGET_KEYWORDS)

def parse_simplify_json(data, source_name):
    jobs = []
    for item in data:
        if not item.get("active", True) or not item.get("is_visible", True):
            continue

        raw_company = clean_text(item.get("company_name") or "")
        raw_role = clean_text(item.get("title") or "")
        url = (item.get("url") or "").strip()
        category = item.get("category") or ""
        posted_time = item.get("date_posted") or item.get("date_updated") or item.get("date")
        location = ", ".join(item.get("locations") or [])
        simplify_uuid = (item.get("id") or "").strip()

        if not raw_company or not raw_role or not url:
            continue
        if not matches_target(raw_role, category):
            continue

        jobs.append({
            "source": source_name,
            "raw_id": simplify_uuid,
            "fingerprint": generate_fingerprint_id(raw_company, raw_role),
            "company": raw_company,
            "role": raw_role,
            "location": location,
            "url": url,
            "posted_time": posted_time,
        })
    return jobs

def parse_markdown_table(content, source_name):
    jobs = []
    lines = content.splitlines()

    for line in lines:
        if not line.startswith("|") or "---" in line:
            continue

        cols = [col.strip() for col in line.split("|")[1:-1]]
        if len(cols) < 3:
            continue

        if any(header in cols[0].lower() for header in ["company", "organization"]):
            continue

        raw_company = clean_text(cols[0])
        raw_role = clean_text(cols[1])
        location = clean_text(cols[2]) if len(cols) > 2 else "Not Listed"

        link_match = re.search(r'href="([^"]+)"', line) or re.search(r"\((https?://[^\)]+)\)", line)
        url = link_match.group(1) if link_match else ""
        date_posted = clean_text(cols[4]) if len(cols) > 4 else "Not Listed"

        if not raw_company or not raw_role or not url:
            continue
        if not matches_target(raw_role):
            continue

        jobs.append({
            "source": source_name,
            "raw_id": None,
            "fingerprint": generate_fingerprint_id(raw_company, raw_role),
            "company": raw_company,
            "role": raw_role,
            "location": location,
            "url": url,
            "posted_time": date_posted,
        })
    return jobs

# ----------------  ---------------- #

def main():
    seen_ids = set()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try:
                seen_ids = set(json.load(f))
            except Exception:
                seen_ids = set()

    all_scraped_jobs = []

    for source in SOURCES:
        try:
            res = requests.get(source["url"], timeout=30)
            res.raise_for_status()

            if source["parser"] == "simplify_json":
                parsed = parse_simplify_json(res.json(), source["name"])
            elif source["parser"] == "markdown_table":
                parsed = parse_markdown_table(res.text, source["name"])
            else:
                parsed = []

            print(f"[{source['name']}] Found {len(parsed)} matched listings.")
            all_scraped_jobs.extend(parsed)

        except Exception as e:
            print(f"Failed to fetch {source['name']}: {e}")

    # First run check: if seen_ids is completely empty
    first_run = len(seen_ids) == 0
    new_seen_ids = set(seen_ids)
    new_jobs_found = 0

    # Build an in-memory set of fingerprints seen across this specific run
    current_batch_fingerprints = set()

    for job in all_scraped_jobs:
        fp = job["fingerprint"]
        raw_id = job["raw_id"]

        # Check if matched against legacy Simplify UUIDs or cross-repo fingerprints
        is_already_seen = (
            (raw_id and raw_id in seen_ids) or 
            (fp in seen_ids) or 
            (fp in current_batch_fingerprints)
        )

        if not is_already_seen:
            if not first_run:
                send_discord_notification(
                    source=job["source"],
                    company=job["company"],
                    role=job["role"],
                    location=job["location"],
                    link=job["url"],
                    posted_time=job["posted_time"],
                )
                new_jobs_found += 1
            
            # Register for deduplication in both current run and persistent cache
            current_batch_fingerprints.add(fp)
            new_seen_ids.add(fp)
            if raw_id:
                new_seen_ids.add(raw_id)
        else:
            # Backfill the fingerprint for Simplify listings that previously only had a UUID
            new_seen_ids.add(fp)
            if raw_id:
                new_seen_ids.add(raw_id)

    if first_run:
        print(f"Initial run completed: cached {len(new_seen_ids)} keys.")
    else:
        print(f"Run completed: Dispatched {new_jobs_found} unique new alerts.")

    with open(CACHE_FILE, "w") as f:
        json.dump(sorted(new_seen_ids), f, indent=2)

if __name__ == "__main__":
    main()
