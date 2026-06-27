import requests
from bs4 import BeautifulSoup
import json
import time

base_url = "https://stockanalysis.com/list/indonesia-stock-exchange/"

headers = {
    "User-Agent": "Mozilla/5.0"
}

tickers = []

# Loop page 1 dan page 2
for page in range(1, 3):
    if page == 1:
        url = base_url
    else:
        url = f"{base_url}?page={page}"

    print(f"Scraping page {page}...")

    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = soup.select("table tbody tr")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) > 1:
            code = cols[1].text.strip()
            tickers.append(code + ".JK")

    time.sleep(1)  # delay biar tidak dianggap bot

# Remove duplicate & sort
tickers = sorted(list(set(tickers)))

# Simpan dalam format ["AALI.JK","ABBA.JK",...]
with open("idx_all_tickers.json", "w") as f:
    json.dump(tickers, f)

print(f"Total tickers: {len(tickers)}")
print("Saved as idx_all_tickers.json")
