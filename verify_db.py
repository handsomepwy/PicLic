import sqlite3

def verify_db(db_path="piclic.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- Images ---")
    cursor.execute("SELECT * FROM images")
    images = cursor.fetchall()
    for row in images:
        print(row)
    
    print("\n--- Files ---")
    cursor.execute("SELECT * FROM files")
    files = cursor.fetchall()
    for row in files:
        print(row)
        
    print("\n--- Scan Status ---")
    cursor.execute("SELECT * FROM scan_status")
    status = cursor.fetchone()
    print(status)
    
    conn.close()

if __name__ == "__main__":
    verify_db()
