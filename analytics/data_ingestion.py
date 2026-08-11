import os
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datasets import load_dataset

HF_DATASET_NAME = "McAuley-Lab/Amazon-Reviews-2023"

# List of the 33 Hugging Face configurations corresponding to the categories
CATEGORIES = [
    "All_Beauty", "Amazon_Fashion", "Appliances", "Arts_Crafts_and_Sewing", "Automotive",
    "Baby_Products", "Beauty_and_Personal_Care", "Books", "CDs_and_Vinyl", "Cell_Phones_and_Accessories",
    "Clothing_Shoes_and_Jewelry", "Digital_Music", "Electronics", "Gift_Cards", "Grocery_and_Gourmet_Food",
    "Handmade_Products", "Health_and_Household", "Health_and_Personal_Care", "Home_and_Kitchen", "Industrial_and_Scientific",
    "Kindle_Store", "Magazine_Subscriptions", "Movies_and_TV", "Musical_Instruments", "Office_Products",
    "Patio_Lawn_and_Garden", "Pet_Supplies", "Software", "Sports_and_Outdoors", "Subscription_Boxes",
    "Tools_and_Home_Improvement", "Toys_and_Games", "Video_Games"
]

def clean_brand(store):
    if not store or store.lower() in ["unknown", "generic", "none"]:
        return "Generic"
    # Clean author notes or extra formatting from store field
    cleaned = store.split("(Author)")[0].split("Format:")[0].strip()
    return cleaned if cleaned else "Generic"

def fetch_category_data(category_name, limit_meta=65, limit_reviews=100):
    """
    Connects to HF, streams metadata and reviews for a single category, and yields list of dicts.
    """
    meta_config = f"raw_meta_{category_name}"
    review_config = f"raw_review_{category_name}"
    
    meta_items = []
    reviews = []
    
    # 1. Fetch metadata
    try:
        meta_ds = load_dataset(
            HF_DATASET_NAME,
            meta_config,
            split="full",
            streaming=True,
            trust_remote_code=True
        )
        for item in meta_ds.take(limit_meta):
            # Parse price field
            price_raw = item.get("price")
            price = None
            if price_raw and price_raw != "None":
                try:
                    # Clean currency symbols and spaces
                    price_cleaned = "".join(c for c in str(price_raw) if c.isdigit() or c == ".")
                    price = float(price_cleaned)
                except ValueError:
                    price = None

            # Get description
            desc_list = item.get("description", [])
            description = " ".join(desc_list) if isinstance(desc_list, list) else str(desc_list)
            
            meta_items.append({
                "parent_asin": item.get("parent_asin"),
                "title": item.get("title", "No Title"),
                "brand": clean_brand(item.get("store")),
                "description": description[:300],
                "price": price,
                "category": category_name
            })
    except Exception as e:
        print(f"[Warning] Failed to fetch metadata for {category_name}: {e}")

    # 2. Fetch reviews
    try:
        review_ds = load_dataset(
            HF_DATASET_NAME,
            review_config,
            split="full",
            streaming=True,
            trust_remote_code=True
        )
        for rev in review_ds.take(limit_reviews):
            reviews.append({
                "parent_asin": rev.get("parent_asin"),
                "rating": float(rev.get("rating", 5.0)),
                "title": rev.get("title", ""),
                "text": rev.get("text", ""),
                "user_id": rev.get("user_id", "anonymous_user"),
                "timestamp": rev.get("timestamp"),
                "category": category_name
            })
    except Exception as e:
        print(f"[Warning] Failed to fetch reviews for {category_name}: {e}")

    return category_name, meta_items, reviews

def get_amazon_data(cache_dir, limit_meta=65, limit_reviews=100):
    """
    Retrieves metadata and reviews from cache or streams from Hugging Face concurrently.
    """
    cache_path = os.path.join(cache_dir, "amazon_ingest_cache.json")
    
    if os.path.exists(cache_path):
        print(f"Loading Amazon Reviews 2023 from local cache: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    print("No local cache found. Initiating concurrent Hugging Face datasets streaming...")
    start_time = time.time()
    
    all_products = []
    all_reviews = []
    
    # Run concurrent threads for faster network performance
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(
            lambda cat: fetch_category_data(cat, limit_meta, limit_reviews),
            CATEGORIES
        )
        
    for cat_name, meta_items, reviews in results:
        all_products.extend(meta_items)
        all_reviews.extend(reviews)
        print(f" -> Category {cat_name}: fetched {len(meta_items)} products, {len(reviews)} reviews")
        
    data = {
        "products": all_products,
        "reviews": all_reviews
    }
    
    # Save cache
    os.makedirs(cache_dir, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully cached {len(all_products)} products and {len(all_reviews)} reviews.")
    print(f"Total ingestion time: {time.time() - start_time:.2f} seconds.")
    
    return data
