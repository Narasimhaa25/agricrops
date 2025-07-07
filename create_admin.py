from pymongo import MongoClient
from werkzeug.security import generate_password_hash
import urllib.parse

# Encode MongoDB credentials
username = urllib.parse.quote_plus("narasimhayalakarajula")
password = urllib.parse.quote_plus("@Nss1125sl1977")

# Connect to MongoDB Atlas
client = MongoClient(f"mongodb+srv://{username}:{password}@cluster0.rwfdfzy.mongodb.net/?retryWrites=true&w=majority")

# ✅ Target the same database and collection as used in app.py
user_db = client["user"]  # same as in app.py
user_collection = user_db["user"]

# Admin credentials
admin_username = "admin"
admin_password = "admin123"

# Check if admin already exists
existing_user = user_collection.find_one({"username": admin_username})

if existing_user:
    print("⚠️ Admin already exists.")
else:
    # Hash the password using Werkzeug's method
    hashed_password = generate_password_hash(admin_password)
    
    # Insert into collection
    user_document = {
        "username": admin_username,
        "password": hashed_password
    }
    
    user_collection.insert_one(user_document)
    print("✅ Admin user created successfully.")