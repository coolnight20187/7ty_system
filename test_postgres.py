import psycopg2

try:
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        database="7ty_vn_db",
        user="7ty_admin",
        password="7ty_password_secure"
    )
    print("Connection successful!")
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print(cur.fetchone())
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
