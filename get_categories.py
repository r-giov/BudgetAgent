#!/usr/bin/env python3
from dotenv import load_dotenv
import os, requests
load_dotenv()

r = requests.get(
    "https://api.ynab.com/v1/budgets/" + os.environ["YNAB_BUDGET_ID"] + "/categories",
    headers={"Authorization": "Bearer " + os.environ["YNAB_TOKEN"]}
)
for g in r.json()["data"]["category_groups"]:
    print(f"\n{g['name']}")
    for c in g["categories"]:
        if not c["deleted"]:
            print(f"  {c['id']}  {c['name']}")
