print("1. Starting import config...")
try:
    import config
    print("2. config imported successfully")
except Exception as e:
    print(f"2. Exception: {e}")
print("3. Done")
