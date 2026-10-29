import os, json, requests

url = "https://api.adzuna.com/v1/api/jobs/in/search/1"
params = {
    "app_id": os.environ["ADZUNA_APP_ID"],
    "app_key": os.environ["ADZUNA_APP_KEY"],
    "what": "data analyst",
    "where": "delhi",
    "results_per_page": 50,
    "content-type": "application/json",
}

r = requests.get(url, params=params, timeout=15)
print("status:", r.status_code)

if r.status_code == 200:
    data = r.json()
    print("total matches:", data.get("count"))
    print("returned now:", len(data["results"]))
    with open("adzuna_cache.json", "w") as f:
        json.dump(data, f)
    for j in data["results"][:3]:
        print("-", j["title"], "|", j["company"]["display_name"], "|", j["location"]["display_name"])
else:
    print(r.text[:200])
