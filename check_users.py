from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT id, username, full_name, phone, role, is_active, created_at FROM users ORDER BY id'))
    rows = result.fetchall()
    print(f'Tong so nguoi dung: {len(rows)}')
    print('-' * 100)
    for row in rows:
        print(f'ID: {row[0]} | Username: {row[1]} | Ten: {row[2]} | SĐT: {row[3]} | Role: {row[4]} | Active: {row[5]}')
