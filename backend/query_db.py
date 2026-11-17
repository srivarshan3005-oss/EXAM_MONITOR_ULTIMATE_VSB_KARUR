"""Query the production SQLite database to find test register numbers."""
import sqlite3, os, json

db_path = os.path.join(os.path.dirname(__file__), "exam_monitor.db")
if not os.path.exists(db_path):
    print("DB not found:", db_path); raise SystemExit(1)

con = sqlite3.connect(db_path)
cur = con.cursor()

print("=== STUDENTS (top 10) ===")
cur.execute("SELECT register_number, full_name, department, year, active FROM students ORDER BY id LIMIT 10")
students = cur.fetchall()
for row in students:
    print(row)

print("\n=== PUBLISHED EXAMS ===")
cur.execute("SELECT id, title, subject_code, exam_date, status FROM exams WHERE status='published' ORDER BY id LIMIT 10")
exams = cur.fetchall()
for row in exams:
    print(row)

print("\n=== ALLOTMENTS (sample) ===")
cur.execute("""
SELECT a.id, s.register_number, s.full_name, e.title, e.status, a.hall, a.seat
FROM allotments a
JOIN students s ON s.id=a.student_id
JOIN exams e ON e.id=a.exam_id
ORDER BY a.id LIMIT 10
""")
for row in cur.fetchall():
    print(row)

print("\n=== VSB PUBLISHED RECORDS (sample) ===")
try:
    cur.execute("""
    SELECT r.register_number, r.hall, r.seat, r.review_status, r.published, b.status, b.exam_name
    FROM vsb_alloc_records r
    JOIN vsb_alloc_batches b ON b.id=r.batch_id
    WHERE r.review_status='approved' AND r.published=1 AND b.status='published'
    LIMIT 5
    """)
    for row in cur.fetchall():
        print(row)
except Exception as ex:
    print("VSB table error:", ex)

con.close()
