import os
import sys
import subprocess
from curl_cffi import requests

TARGET_DIR = r"i:\Softs\Antigravity\CaoTruyen\chivi_repos"
os.makedirs(TARGET_DIR, exist_ok=True)

print(f"Target directory: {TARGET_DIR}")

# Fetch repos list
r = requests.get('https://api.github.com/orgs/chi-vi/repos?per_page=100', impersonate='chrome120', timeout=20)
if r.status_code != 200:
    print(f"Error fetching repos: {r.status_code}")
    sys.exit(1)

repos = r.json()
print(f"Total repositories found: {len(repos)}\n")

success_count = 0
failed_count = 0

for idx, repo in enumerate(repos, 1):
    name = repo['name']
    clone_url = repo['clone_url']
    dest = os.path.join(TARGET_DIR, name)
    
    if os.path.exists(dest) and os.listdir(dest):
        print(f"[{idx}/{len(repos)}] '{name}' already exists. Skipping.")
        success_count += 1
        continue
        
    print(f"[{idx}/{len(repos)}] Cloning {name} from {clone_url} ...", flush=True)
    try:
        # Clone with depth 1 for maximum speed and minimum storage
        cmd = ["git", "clone", "--depth", "1", clone_url, dest]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0:
            print(f"  -> SUCCESS: {name}")
            success_count += 1
        else:
            print(f"  -> FAILED ({name}): {res.stderr.strip()[:200]}")
            failed_count += 1
    except Exception as e:
        print(f"  -> ERROR ({name}): {e}")
        failed_count += 1

print("\n" + "=" * 50)
print(f"Finished cloning: {success_count} success, {failed_count} failed.")
print(f"Saved to: {TARGET_DIR}")
