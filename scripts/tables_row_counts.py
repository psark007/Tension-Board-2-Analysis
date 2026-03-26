import sqlite3

# Update path to your database file
db_path = "../data/tb2.db"

connection = sqlite3.connect(db_path)
cursor = connection.cursor()

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [row[0] for row in cursor.fetchall()]

# Count rows for each table
results = []
for table in tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
        count = cursor.fetchone()[0]
        results.append((table, count))
    except Exception as e:
        results.append((table, f"Error: {e}"))

# Sort by row count descending
results.sort(key=lambda x: x[1] if isinstance(x[1], int) else -1, reverse=True)

# Print results
print(f"{'table_name':<30} | {'rows':>10}")
print("-" * 45)
for table, count in results:
    print(f"{table:<30} | {count:>10}")

connection.close()
