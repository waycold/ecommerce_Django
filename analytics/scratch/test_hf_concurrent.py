import time
from concurrent.futures import ThreadPoolExecutor
from datasets import load_dataset

categories = [
    "raw_meta_All_Beauty",
    "raw_meta_Appliances",
    "raw_meta_Automotive",
    "raw_meta_Books",
    "raw_meta_Electronics"
]

def load_category_data(cat):
    print(f"Starting connection for {cat}...")
    ds = load_dataset(
        "McAuley-Lab/Amazon-Reviews-2023",
        cat,
        split="full",
        streaming=True,
        trust_remote_code=True
    )
    items = list(ds.take(5))
    return cat, items

start_time = time.time()
with ThreadPoolExecutor(max_workers=5) as executor:
    results = executor.map(load_category_data, categories)

for cat, items in results:
    print(f"\n--- {cat} ---")
    for item in items:
        print(f" - {item.get('title')[:50]} (Brand: {item.get('store')})")

print(f"\nTotal concurrent time elapsed: {time.time() - start_time:.2f} seconds")
