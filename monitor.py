import hashlib
import json
import os
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests

CACHE_FILE = "seen_jobs.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

TARGET_CATEGORIES = {
    "Software", "Software Engineering", "AI/ML/Data", 
    "Data Science, AI & Machine Learning", "Security", "IT"
}

TARGET_KEYWORDS = [
    "software", "engineer", "quant", "developer", "design", "technology",
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

# ----------------- #

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
    
    # Common abbreviation replacements
    cleaned = re.sub(r"\bswe\b", "software engineer", cleaned)
    cleaned = re.sub(r"\bml\b", "machine learning", cleaned)
    cleaned = re.sub(r"\bds\b", "data science", cleaned)
    cleaned = re.sub(r"\bai\b", "artificial intelligence", cleaned)
    
    for noise in ROLE_NOISE:
        cleaned = re.sub(noise, "", cleaned)
    return re.sub(r"[^a-z0-9]", "", cleaned)

def clean_url(raw_url: str) -> str:
    """Strips query parameters like tracking IDs (utm_*, ref, etc.)."""
    try:
        parsed = urlparse(raw_url.strip())
        # Drop UTM, tracking query strings, and trailing slashes
        clean_path = parsed.path.rstrip("/")
        return f"{parsed.netloc}{clean_path}".lower()
    except Exception:
        return raw_url.strip().lower()

def is_duplicate(new_job, seen_records):
    """
    Checks if a job is already present using:
    1. Direct URL match (after stripping query params)
    2. Normalized Company + Normalized Role fingerprint
    3. High-confidence fuzzy match for the same company
    """
    new_comp = new_job["norm_company"]
    new_role = new_job["norm_role"]
    new_url = new_job["clean_url"]

    for record in seen_records:
        # Check 1: Matching application URL
        if new_url and record.get("clean_url") and new_url == record["clean_url"]:
            return True, f"Matched existing application URL: {record['clean_url']}"

        # Check 2: Exact match on normalized Company + normalized Role
        if new_comp and new_comp == record.get("norm_company"):
            if new_role == record.get("norm_role"):
                return True, f"Matched company ({new_comp}) and normalized role ({new_role})"

            # Check 3: Fuzzy role match for the same company (>= 85% similarity)
            if new_role and record.get("norm_role"):
                similarity = SequenceMatcher(None, new_role, record["norm_role"]).ratio()
                if similarity >= 0.85:
                    return True, f"Fuzzy matched ({int(similarity*100)}%) with {record['raw_role']}"

    return False, ""

# ---------------- #

def send_discord_notification(source, company, role, location, link, posted_time):
    time_str = "Not Listed"
    if posted_time:
        if isinstance(posted_time, (int, float)):
            time_str = f"<t:{int(posted_time)}:f>"
        else:
            time_str = str(posted_time)

    payload = {
        "username": "Internship Aggregator",
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
                    {"name": "📡 Discovered Via", "value": f"`{source}`", "inline": True},
                    {"name": "🔗 Application Link", "value": f"[:link: Apply Here]({link})", "inline": False},
                ],
                "footer": {"text": "Deduplicated Multi-Repo Alert 🚀"},
            }
        ],
    }
    if WEBHOOK_URL:
        try:
            res = requests.post(WEBHOOK_URL, json=payload, timeout=15)
            res.raise_for_status()
        except Exception as e:
            print(f"Failed to post to Discord webhook: {e}")

# ---------------- #

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

        if not raw_company or not raw_role or not url:
            continue
        if not matches_target(raw_role, category):
            continue

        jobs.append({
            "source": source_name,
            "raw_company": raw_company,
            "raw_role": raw_role,
            "norm_company": clean_company_name(raw_company),
            "norm_role": clean_role_name(raw_role),
            "location": location,
            "url": url,
            "clean_url": clean_url(url),
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
            "raw_company": raw_company,
            "raw_role": raw_role,
            "norm_company": clean_company_name(raw_company),
            "norm_role": clean_role_name(raw_role),
            "location": location,
            "url": url,
            "clean_url": clean_url(url),
            "posted_time": date_posted,
        })
    return jobs

# ---------------- #

def main():
    seen_records = []
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try:
                seen_records = json.load(f)
            except Exception:
                seen_records = []

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

    first_run = len(seen_records) == 0
    new_jobs_found = 0

    for job in all_scraped_jobs:
        duplicate, reason = is_duplicate(job, seen_records)
        if not duplicate:
            if not first_run:
                send_discord_notification(
                    source=job["source"],
                    company=job["raw_company"],
                    role=job["raw_role"],
                    location=job["location"],
                    link=job["url"],
                    posted_time=job["posted_time"],
                )
                new_jobs_found += 1
            
            # Store structured identity record
            seen_records.append({
                "norm_company": job["norm_company"],
                "norm_role": job["norm_role"],
                "raw_company": job["raw_company"],
                "raw_role": job["raw_role"],
                "clean_url": job["clean_url"],
            })

    if first_run:
        print(f"Initial run completed: {len(seen_records)} jobs indexed across all 4 repos (Discord quiet mode).")
    else:
        print(f"Run completed: {new_jobs_found} unique new roles notified.")

    with open(CACHE_FILE, "w") as f:
        json.dump(seen_records, f, indent=2)

if __name__ == "__main__":
    main()
