from app.database import SessionLocal
from app import models, doc_models

db = SessionLocal()
try:
    users = db.query(models.User).all()
    print("Users:", [(u.id, u.username, u.role) for u in users])
    students = db.query(models.Student).all()
    print(f"Students count: {len(students)}")
    for s in students[:5]:
        print("  Student:", s.id, s.register_number, s.full_name, s.department, s.year)
    exams = db.query(models.Exam).all()
    print(f"Exams count: {len(exams)}")
    for e in exams:
        print("  Exam:", e.id, e.title, e.subject_code, e.exam_date, e.start_time, e.status)
    allotments = db.query(models.Allotment).all()
    print(f"Allotments count: {len(allotments)}")
    for a in allotments[:5]:
        print("  Allotment:", a.id, a.student_id, a.exam_id, a.hall, a.seat)
    batches = db.query(doc_models.VsbAllocBatch).all()
    print(f"VSB Alloc Batches count: {len(batches)}")
    for b in batches:
        print("  Batch:", b.id, b.exam_name, b.exam_date, b.session, b.status)
    records = db.query(doc_models.VsbAllocRecord).all()
    print(f"VSB Alloc Records count: {len(records)}")
    for r in records[:5]:
        print("  Record:", r.id, r.register_number, r.hall, r.seat, r.review_status, r.published)
finally:
    db.close()
