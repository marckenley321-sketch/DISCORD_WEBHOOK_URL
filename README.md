# 🚀 SimplifyJobs Discord Tracker

A Python-based monitoring tool that tracks the SimplifyJobs Summer 2027 Internships list and automatically sends formatted Discord alerts whenever new Software Engineering, Data Science, or AI/ML roles are posted. 

### ✨ Key Features
* 🤖 **Automated Tracking:** Fetches live data directly from the Simplify raw JSON feed.
* 🎯 **Smart Filtering:** Only alerts you to relevant technical roles using customizable keyword and category filters.
* 💬 **Rich Discord Embeds:** Delivers clean notifications featuring the company name, role, location, posting time, and a direct application link.
* 🛡️ **Duplicate Prevention:** Uses a local cache (`seen_ids.json`) to remember previously processed listings and prevent spamming your Discord channel.

### 🛠️ Prerequisites
* 🐍 Python 3.x
* 📦 `requests` library
* 👾 A Discord server with Webhook integration enabled

### 📥 Installation & Setup

Clone the repository:

Bash
git clone https://github.com/marckenley321-sketch/DISCORD_WEBHOOK_URL.git
cd DISCORD_WEBHOOK_URL
Install dependencies:

Bash
pip install requests
Configure your Webhook:
Create a webhook in your Discord server settings (Integrations > Webhooks) and set it as an environment variable.

On Mac/Linux:

Bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
On Windows (Command Prompt):

DOS
set DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
Usage

Run the script manually or set it up on a cron job/task scheduler to run at regular intervals (e.g., every hour):

Bash
python monitor.py
