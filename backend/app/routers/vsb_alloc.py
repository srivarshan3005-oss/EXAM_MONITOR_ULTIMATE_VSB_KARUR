"""VSB hall / seat allocation workflow.

parse (PDF -> DRAFT batch) -> administrator correction -> per-record approval -> preview -> publish -> students see their own
confirmed hall and seat. Optional last step: bridge published records into the existing `allotments` (allocation engine rules).

Safety rules enforced here (and covered by tests/test_vsb_alloc_workflow.py):
* A record is visible to a student only when it is approved AND its batch is published.
* Records that carry flags are never bulk-approved; approving one needs a note (and, when the flag is blocking, an explicit
  acknowledgement unless the administrator corrected the record).
* Publishing exposes only approved records and requires a confirmation bound to the previewed data (signature).
* Edits are blocked on a published batch; withdraw it first. Every edit, decision and publication is audited.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, doc_models as dm, models
from ..database import get_db
from ..dbutil import lock_allocation
from ..deps import department_scope, require_roles
from ..services_allocation import check_placement, log_history, session_of
from ..vsb_alloc import service as svc
from ..vsb_alloc.common import norm_hall
from ..vsb_alloc.reconcile import ERROR_FLAGS, WARNING_FLAGS

router = APIRouter(prefix="/api/vsb-allocation", tags=["VSB hall and seat allocation"])
STAFF = ("admin", "staff")
ADMIN = ("admin",)
iso = lambda d: d.isoformat() if d else None  # noqa: E731
_SEAT = re.compile(r"^[A-Za-z0-9\-]{1,30}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _flags(r: dm.VsbAllocRecord) -> list[str]:
    try:
        return list(json.loads(r.flags or "[]"))
    except ValueError:
        return []


def _blocking(flags: list[str]) -> bool:
    return any(f in ERROR_FLAGS for f in flags)


def _batch(db: Session, bid: int) -> dm.VsbAllocBatch:
    b = db.get(dm.VsbAllocBatch, bid)
    if not b:
        raise HTTPException(404, "Batch not found")
    return b


def _record(db: Session, rid: int) -> tuple[dm.VsbAllocRecord, dm.VsbAllocBatch]:
    r = db.get(dm.VsbAllocRecord, rid)
    if not r:
        raise HTTPException(404, "Record not found")
    return r, db.get(dm.VsbAllocBatch, r.batch_id)


def _scope_ok(db: Session, user: models.User, r: dm.VsbAllocRecord) -> bool:
    scope = department_scope(user)
    if not scope:
        return True
    s = db.get(models.Student, r.student_id) if r.student_id else None
    return bool(s and (s.department or "").strip().lower() == scope.lower())


def _rec(db: Session, r: dm.VsbAllocRecord, batch: dm.VsbAllocBatch | None = None, student: models.Student | None = None) -> dict:
    b = batch or db.get(dm.VsbAllocBatch, r.batch_id)
    flags = _flags(r)
    det = json.loads(r.detail or "{}") if r.detail else {}
    return {"id": r.id, "batch_id": r.batch_id, "register_number": r.register_number, "id_kind": r.id_kind,
            "student_known": r.student_id is not None, "department": r.department, "department_source": r.department_source,
            "subject_code": r.subject_code, "subject_title": r.subject_title, "exam_date": iso(b.exam_date), "session": b.session,
            "exam_name": b.exam_name, "hall": r.hall, "seat": r.seat, "sources": r.sources, "flags": flags,
            "blocking": _blocking(flags), "uncertain": any(f in ERROR_FLAGS or f in WARNING_FLAGS for f in flags),
            "confidence": r.confidence, "edited": r.edited, "review_status": r.review_status, "review_note": r.review_note,
            "reviewed_by": r.reviewed_by, "published": r.published, "allotment_id": r.allotment_id,
            "hall_pdf_hall": det.get("hall_pdf_hall"), "seat_pdf_hall": det.get("seat_pdf_hall"),
            "hall_page": None if det.get("hall_page") is None else det["hall_page"] + 1,
            "seat_page": None if det.get("seat_page") is None else det["seat_page"] + 1, "notes": det.get("notes") or []}


def _batch_dict(db: Session, b: dm.VsbAllocBatch, full: bool = False) -> dict:
    counts = dict(db.execute(select(dm.VsbAllocRecord.review_status, func.count()).where(dm.VsbAllocRecord.batch_id == b.id)
                             .group_by(dm.VsbAllocRecord.review_status)).all())
    issues = dict(db.execute(select(dm.VsbAllocIssue.severity, func.count()).where(
        dm.VsbAllocIssue.batch_id == b.id, dm.VsbAllocIssue.status == "open").group_by(dm.VsbAllocIssue.severity)).all())
    docs = {}
    for key, vid in (("hall_pdf", b.hall_version_id), ("seat_pdf", b.seat_version_id)):
        v = db.get(dm.DocumentVersion, vid) if vid else None
        d = db.get(dm.OfficialDocument, v.document_id) if v else None
        docs[key] = None if not v else {"version_id": v.id, "document_id": d.id if d else None, "title": d.title if d else None,
                                        "source_url": d.source_url if d else None, "version_no": v.version_no,
                                        "sha256": v.sha256[:16], "downloaded_at": iso(v.downloaded_at)}
    out = {"id": b.id, "exam_date": iso(b.exam_date), "session": b.session, "exam_name": b.exam_name, "status": b.status,
           "records": {"total": sum(counts.values()), **counts}, "open_issues": issues, "documents": docs,
           "source_changed": svc.source_changed(db, b), "parser_version": b.parser_version, "created_by": b.created_by,
           "created_at": iso(b.created_at), "published_by": b.published_by, "published_at": iso(b.published_at),
           "withdraw_reason": b.withdraw_reason}
    if full:
        out["summary"] = json.loads(b.summary or "{}")
    return out


# ----------------------------------------------------------------------------- build / list
class BuildRequest(BaseModel):
    hall_version_id: int | None = Field(default=None, ge=1)
    seat_version_id: int | None = Field(default=None, ge=1)


@router.get("/candidates")
def candidates(db: Session = Depends(get_db), user: models.User = Depends(require_roles(*STAFF))):
    """Stored hall / seating PDFs that can be turned into a batch (current versions only)."""
    out = []
    for d in db.scalars(select(dm.OfficialDocument).where(dm.OfficialDocument.doc_kind.in_(("hall_allotment", "seating_allotment")))
                        .order_by(dm.OfficialDocument.exam_date.desc(), dm.OfficialDocument.id.desc()).limit(200)).all():
        v = svc.current_version(db, d.id)
        if v:
            out.append({"document_id": d.id, "version_id": v.id, "version_no": v.version_no, "kind": d.doc_kind, "title": d.title,
                        "exam_date": iso(d.exam_date), "session": d.session, "source_url": d.source_url,
                        "processing_status": v.processing_status, "downloaded_at": iso(v.downloaded_at), "status": d.status})
    return out


@router.post("/batches/build", status_code=201)
def build(data: BuildRequest, request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_roles(*STAFF))):
    """Parse the chosen PDFs and stage DRAFT batches. Never publishes, never writes to allotments."""
    try:
        batches = svc.build_batches(db, data.hall_version_id, data.seat_version_id, user.username)
    except svc.BuildError as e:
        db.rollback()
        raise HTTPException(422, str(e))
    audit.record(db, user.username, "vsb_alloc.built", ",".join(str(b.id) for b in batches),
                 {"hall_version": data.hall_version_id, "seat_version": data.seat_version_id}, request, user.role)
    db.commit()
    return [_batch_dict(db, b, True) for b in batches]


@router.get("/batches")
def list_batches(db: Session = Depends(get_db), user: models.User = Depends(require_roles(*STAFF))):
    rows = db.scalars(select(dm.VsbAllocBatch).order_by(dm.VsbAllocBatch.exam_date.desc(), dm.VsbAllocBatch.session,
                                                        dm.VsbAllocBatch.id.desc()).limit(200)).all()
    return [_batch_dict(db, b) for b in rows]


@router.get("/batches/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db), user: models.User = Depends(require_roles(*STAFF))):
    return _batch_dict(db, _batch(db, batch_id), True)


@router.get("/batches/{batch_id}/records")
def list_records(batch_id: int, q: str = Query("", max_length=40), hall: str = Query("", max_length=100),
                 department: str = Query("", max_length=150), subject: str = Query("", max_length=30),
                 status: str = Query("", max_length=10), uncertain: bool = False, limit: int = Query(200, ge=1, le=1000),
                 offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: models.User = Depends(require_roles(*STAFF))):
    b = _batch(db, batch_id)
    stmt = select(dm.VsbAllocRecord).where(dm.VsbAllocRecord.batch_id == b.id)
    if q.strip():
        stmt = stmt.where(dm.VsbAllocRecord.register_number.contains(q.strip().upper(), autoescape=True))
    if hall:
        stmt = stmt.where(func.upper(dm.VsbAllocRecord.hall) == norm_hall(hall))
    if department:
        stmt = stmt.where(dm.VsbAllocRecord.department == department)
    if subject:
        stmt = stmt.where(dm.VsbAllocRecord.subject_code == subject.upper())
    if status:
        stmt = stmt.where(dm.VsbAllocRecord.review_status == status)
    rows = db.scalars(stmt.order_by(dm.VsbAllocRecord.hall, dm.VsbAllocRecord.register_number)).all()
    items = [_rec(db, r, b) for r in rows if _scope_ok(db, user, r)]
    if uncertain:
        items = [i for i in items if i["uncertain"]]
    return {"total": len(items), "records": items[offset:offset + limit]}


@router.get("/batches/{batch_id}/issues")
def list_issues(batch_id: int, status: str = Query("open", max_length=12), db: Session = Depends(get_db),
                user: models.User = Depends(require_roles(*STAFF))):
    _batch(db, batch_id)
    stmt = select(dm.VsbAllocIssue).where(dm.VsbAllocIssue.batch_id == batch_id)
    if status:
        stmt = stmt.where(dm.VsbAllocIssue.status == status)
    order = {"error": 0, "warning": 1, "info": 2}
    rows = sorted(db.scalars(stmt.limit(3000)).all(), key=lambda i: (order.get(i.severity, 3), i.id))
    return [{"id": i.id, "kind": i.kind, "severity": i.severity, "message": i.message, "register_number": i.register_number,
             "hall": i.hall, "subject_code": i.subject_code, "page": None if i.page is None else i.page + 1, "status": i.status,
             "resolved_by": i.resolved_by, "resolution_note": i.resolution_note} for i in rows]


class IssueResolve(BaseModel):
    decision: str = Field(pattern="^(resolved|dismissed|open)$")
    note: str = Field(min_length=3, max_length=300)


@router.post("/issues/{issue_id}/resolve")
def resolve_issue(issue_id: int, data: IssueResolve, request: Request, db: Session = Depends(get_db),
                  user: models.User = Depends(require_roles(*ADMIN))):
    i = db.get(dm.VsbAllocIssue, issue_id)
    if not i:
        raise HTTPException(404, "Issue not found")
    i.status = data.decision
    i.resolved_by, i.resolved_at, i.resolution_note = (None, None, None) if data.decision == "open" else (user.username, _now(), data.note)
    audit.record(db, user.username, "vsb_alloc.issue_" + data.decision, str(i.id), {"kind": i.kind}, request, user.role)
    db.commit()
    return {"id": i.id, "status": i.status}


# ----------------------------------------------------------------------------- correction / approval
class RecordEdit(BaseModel):
    hall: str | None = Field(default=None, max_length=100)
    seat: str | None = Field(default=None, max_length=30)
    subject_code: str | None = Field(default=None, max_length=30)
    department: str | None = Field(default=None, max_length=150)
    reason: str = Field(min_length=3, max_length=300)


@router.patch("/records/{record_id}")
def edit_record(record_id: int, data: RecordEdit, request: Request, db: Session = Depends(get_db),
                user: models.User = Depends(require_roles(*ADMIN))):
    r, b = _record(db, record_id)
    if b.status == "published":
        raise HTTPException(409, "This batch is published. Withdraw it before correcting records.")
    changes = {}
    if data.hall is not None:
        v = norm_hall(data.hall)
        if not v:
            raise HTTPException(422, "Hall cannot be blank")
        changes["hall"] = v
    if data.seat is not None:
        v = data.seat.strip().upper()
        if not _SEAT.match(v):
            raise HTTPException(422, "Seat must be 1-30 letters, digits or hyphens")
        changes["seat"] = v
    if data.subject_code is not None:
        v = data.subject_code.strip().upper()
        if not re.match(r"^[A-Z0-9]{5,12}$", v):
            raise HTTPException(422, "Subject code looks invalid")
        changes["subject_code"] = v
    if data.department is not None:
        changes["department"] = data.department.strip()[:150] or None
    if not changes:
        raise HTTPException(422, "Nothing to change")
    for k, v in changes.items():
        old = getattr(r, k)
        if old != v:
            db.add(dm.VsbAllocEdit(record_id=r.id, field=k, old_value=old, new_value=v, edited_by=user.username[:80], reason=data.reason))
            setattr(r, k, v)
    if "department" in changes:
        r.department_source = "manual"
    r.edited, r.review_status = True, "pending"
    r.reviewed_by = r.reviewed_at = None
    audit.record(db, user.username, "vsb_alloc.record_edited", str(r.id), {"fields": sorted(changes), "reason": data.reason}, request, user.role)
    db.commit()
    return _rec(db, r, b)


class RecordReview(BaseModel):
    decision: str = Field(pattern="^(approve|reject|reset)$")
    note: str = Field(default="", max_length=300)
    acknowledge: bool = False


def _approve_problem(r: dm.VsbAllocRecord, data: RecordReview) -> str | None:
    if not (r.hall and r.seat and r.subject_code):
        return "Hall, seat and subject are required before a record can be approved; correct it first."
    flags = _flags(r)
    if not flags:
        return None
    if len(data.note.strip()) < 3:
        return "This record carries flags; add a note saying how you verified it against the official PDF."
    if _blocking(flags) and not r.edited and not data.acknowledge:
        return "This record has blocking flags. Correct it, or tick 'I verified this against the official PDF'."
    return None


@router.post("/records/{record_id}/review")
def review_record(record_id: int, data: RecordReview, request: Request, db: Session = Depends(get_db),
                  user: models.User = Depends(require_roles(*ADMIN))):
    r, b = _record(db, record_id)
    if b.status == "published":
        raise HTTPException(409, "This batch is published. Withdraw it before changing decisions.")
    if data.decision == "approve":
        problem = _approve_problem(r, data)
        if problem:
            raise HTTPException(422, problem)
        r.review_status = "approved"
    else:
        r.review_status = "rejected" if data.decision == "reject" else "pending"
    r.review_note = data.note.strip()[:300] or None
    r.reviewed_by, r.reviewed_at = (None, None) if data.decision == "reset" else (user.username, _now())
    audit.record(db, user.username, f"vsb_alloc.record_{data.decision}", str(r.id), {"flags": _flags(r)}, request, user.role)
    db.commit()
    return _rec(db, r, b)


@router.post("/batches/{batch_id}/approve-confident")
def approve_confident(batch_id: int, request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_roles(*ADMIN))):
    """Bulk-approve ONLY records that carry no flag at all, have hall + seat + subject and are not yet decided."""
    b = _batch(db, batch_id)
    if b.status != "draft":
        raise HTTPException(409, "Only a draft batch can be approved")
    n = 0
    for r in db.scalars(select(dm.VsbAllocRecord).where(dm.VsbAllocRecord.batch_id == b.id, dm.VsbAllocRecord.review_status == "pending")).all():
        if not _flags(r) and r.hall and r.seat and r.subject_code and r.student_id:
            r.review_status, r.reviewed_by, r.reviewed_at = "approved", user.username, _now()
            n += 1
    audit.record(db, user.username, "vsb_alloc.bulk_approved", str(b.id), {"records": n}, request, user.role)
    db.commit()
    return {"approved": n}


# ----------------------------------------------------------------------------- preview / publish / withdraw
class PublishRequest(BaseModel):
    signature: str = Field(min_length=64, max_length=64)
    confirm: bool
    acknowledge_open_issues: bool = False


def _publish_plan(db: Session, b: dm.VsbAllocBatch) -> dict:
    rows = db.scalars(select(dm.VsbAllocRecord).where(dm.VsbAllocRecord.batch_id == b.id)).all()
    approved = [r for r in rows if r.review_status == "approved"]
    sig = hashlib.sha256(json.dumps([b.id, sorted((r.id, r.register_number, r.hall, r.seat, r.subject_code) for r in approved)]).encode()).hexdigest()
    open_err = db.scalar(select(func.count()).select_from(dm.VsbAllocIssue).where(
        dm.VsbAllocIssue.batch_id == b.id, dm.VsbAllocIssue.status == "open", dm.VsbAllocIssue.severity == "error")) or 0
    return {"batch": _batch_dict(db, b), "will_publish": len(approved), "not_published": len(rows) - len(approved),
            "pending": sum(1 for r in rows if r.review_status == "pending"), "rejected": sum(1 for r in rows if r.review_status == "rejected"),
            "approved_without_student": sum(1 for r in approved if not r.student_id),
            "approved_with_flags": sum(1 for r in approved if _flags(r)), "open_error_issues": open_err, "signature": sig,
            "note": "Only approved records become visible to students. Pending and rejected records stay unpublished."}


@router.post("/batches/{batch_id}/publish/preview")
def publish_preview(batch_id: int, db: Session = Depends(get_db), user: models.User = Depends(require_roles(*STAFF))):
    return _publish_plan(db, _batch(db, batch_id))


@router.post("/batches/{batch_id}/publish")
def publish(batch_id: int, data: PublishRequest, request: Request, db: Session = Depends(get_db),
            user: models.User = Depends(require_roles(*ADMIN))):
    b = _batch(db, batch_id)
    if b.status != "draft":
        raise HTTPException(409, "Only a draft batch can be published")
    if not data.confirm:
        raise HTTPException(422, "Administrator confirmation is required")
    plan = _publish_plan(db, b)
    if plan["signature"] != data.signature:
        raise HTTPException(409, "The records changed since the preview; review the preview again")
    if not plan["will_publish"]:
        raise HTTPException(409, "No approved records to publish")
    if plan["open_error_issues"] and not data.acknowledge_open_issues:
        raise HTTPException(409, f"{plan['open_error_issues']} error issue(s) are still open. Resolve them, or confirm that you reviewed them.")
    if db.scalar(select(func.count()).select_from(dm.VsbAllocRecord).where(
            dm.VsbAllocRecord.batch_id == b.id, dm.VsbAllocRecord.review_status == "approved",
            (dm.VsbAllocRecord.hall.is_(None)) | (dm.VsbAllocRecord.seat.is_(None)))):
        raise HTTPException(409, "An approved record has no hall or seat; this must not be published")
    for old in db.scalars(select(dm.VsbAllocBatch).where(dm.VsbAllocBatch.exam_date == b.exam_date, dm.VsbAllocBatch.session == b.session,
                                                         dm.VsbAllocBatch.status == "published", dm.VsbAllocBatch.id != b.id)).all():
        old.status = "superseded"
        for r in db.scalars(select(dm.VsbAllocRecord).where(dm.VsbAllocRecord.batch_id == old.id)).all():
            r.published = False
    now = _now()
    for r in db.scalars(select(dm.VsbAllocRecord).where(dm.VsbAllocRecord.batch_id == b.id, dm.VsbAllocRecord.review_status == "approved")).all():
        r.published, r.published_at = True, now
    b.status, b.published_by, b.published_at = "published", user.username, now
    audit.record(db, user.username, "vsb_alloc.published", str(b.id),
                 {"records": plan["will_publish"], "with_flags": plan["approved_with_flags"], "open_errors": plan["open_error_issues"]}, request, user.role)
    db.commit()
    return {"published": plan["will_publish"], "batch": _batch_dict(db, b)}


class Withdraw(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


@router.post("/batches/{batch_id}/withdraw")
def withdraw(batch_id: int, data: Withdraw, request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_roles(*ADMIN))):
    b = _batch(db, batch_id)
    if b.status != "published":
        raise HTTPException(409, "Only a published batch can be withdrawn")
    for r in db.scalars(select(dm.VsbAllocRecord).where(dm.VsbAllocRecord.batch_id == b.id)).all():
        r.published = False
    b.status, b.withdrawn_by, b.withdrawn_at, b.withdraw_reason = "withdrawn", user.username, _now(), data.reason
    audit.record(db, user.username, "vsb_alloc.withdrawn", str(b.id), {"reason": data.reason}, request, user.role)
    db.commit()
    return _batch_dict(db, b)


@router.post("/batches/{batch_id}/reopen")
def reopen(batch_id: int, request: Request, db: Session = Depends(get_db), user: models.User = Depends(require_roles(*ADMIN))):
    """Turn a withdrawn batch back into a draft so it can be corrected and published again (decisions are kept)."""
    b = _batch(db, batch_id)
    if b.status != "withdrawn":
        raise HTTPException(409, "Only a withdrawn batch can be reopened")
    b.status = "draft"
    audit.record(db, user.username, "vsb_alloc.reopened", str(b.id), None, request, user.role)
    db.commit()
    return _batch_dict(db, b)


# ----------------------------------------------------------------------------- bridge into the allocation engine
class BridgeRequest(BaseModel):
    signature: str = Field(min_length=64, max_length=64)
    confirm: bool
    skip_blocked: bool = False


def _bridge_plan(db: Session, b: dm.VsbAllocBatch) -> dict:
    items, ready = [], []
    date_s = b.exam_date.isoformat()
    rows = db.scalars(select(dm.VsbAllocRecord).where(dm.VsbAllocRecord.batch_id == b.id, dm.VsbAllocRecord.published == True,  # noqa: E712
                                                      dm.VsbAllocRecord.review_status == "approved")
                      .order_by(dm.VsbAllocRecord.hall, dm.VsbAllocRecord.register_number)).all()
    exams: dict[str, list[models.Exam]] = {}
    for r in rows:
        reasons, state, exam = [], "ready", None
        if r.allotment_id:
            items.append({"record_id": r.id, "register_number": r.register_number, "hall": r.hall, "seat": r.seat,
                          "subject_code": r.subject_code, "state": "done", "reasons": ["already bridged"]})
            continue
        s = db.get(models.Student, r.student_id) if r.student_id else None
        if not s:
            reasons.append("no student with this register number in the student database")
        found = exams.get(r.subject_code)
        if found is None:
            found = exams[r.subject_code] = list(db.scalars(select(models.Exam).where(
                models.Exam.exam_date == date_s, models.Exam.subject_code == r.subject_code)).all())
        if len(found) != 1:
            reasons.append("no examination with this subject on this date; import the timetable first" if not found
                           else "several examinations match this subject and date")
        else:
            exam = found[0]
            if session_of(exam.start_time) != b.session:
                reasons.append(f"the examination starts at {exam.start_time}, which is not a {b.session} session")
        if s and exam and not reasons:
            have = db.scalar(select(models.Allotment).where(models.Allotment.exam_id == exam.id, models.Allotment.student_id == s.id))
            if have:
                same = have.hall.upper() == (r.hall or "").upper() and have.seat.upper() == (r.seat or "").upper()
                reasons.append("already allotted the same seat" if same else f"conflicts with existing allotment {have.hall}/{have.seat}")
            else:
                try:
                    check_placement(db, exam, s, r.hall or "", r.seat or "")
                except HTTPException as ex:
                    reasons.append(str(ex.detail) if isinstance(ex.detail, str) else json.dumps(ex.detail)[:200])
        if reasons:
            state = "blocked"
        items.append({"record_id": r.id, "register_number": r.register_number, "hall": r.hall, "seat": r.seat,
                      "subject_code": r.subject_code, "exam_id": exam.id if exam else None, "state": state, "reasons": reasons})
        if state == "ready":
            ready.append((r.id, exam.id, r.hall, r.seat))
    sig = hashlib.sha256(json.dumps([b.id, ready]).encode()).hexdigest()
    summary = {k: sum(1 for i in items if i["state"] == k) for k in ("ready", "blocked", "done")}
    return {"batch_id": b.id, "summary": summary, "signature": sig, "items": items[:1000]}


@router.post("/batches/{batch_id}/bridge/preview")
def bridge_preview(batch_id: int, db: Session = Depends(get_db), user: models.User = Depends(require_roles(*ADMIN))):
    b = _batch(db, batch_id)
    if b.status != "published":
        raise HTTPException(409, "Publish the batch first; only published, approved records can be bridged")
    return _bridge_plan(db, b)


@router.post("/batches/{batch_id}/bridge", status_code=201)
def bridge(batch_id: int, data: BridgeRequest, request: Request, db: Session = Depends(get_db),
           user: models.User = Depends(require_roles(*ADMIN))):
    """Create `allotments` rows (source 'vsb') for published, approved records using the normal placement rules."""
    lock_allocation(db)
    b = _batch(db, batch_id)
    if b.status != "published":
        raise HTTPException(409, "Publish the batch first")
    if not data.confirm:
        raise HTTPException(422, "Administrator confirmation is required")
    plan = _bridge_plan(db, b)
    if plan["signature"] != data.signature:
        raise HTTPException(409, "The data changed since the preview; review it again")
    if plan["summary"]["blocked"] and not data.skip_blocked:
        raise HTTPException(409, "Some records are blocked; fix them or choose to skip them")
    ready = {i["record_id"]: i["exam_id"] for i in plan["items"] if i["state"] == "ready"}
    if not ready:
        raise HTTPException(409, "No records can be bridged")
    created, events = 0, {}
    for r in db.scalars(select(dm.VsbAllocRecord).where(dm.VsbAllocRecord.id.in_(list(ready)))).all():
        exam = db.get(models.Exam, ready[r.id])
        a = models.Allotment(student_id=r.student_id, exam_id=exam.id, hall=r.hall, seat=r.seat, source="vsb")
        db.add(a)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "A seat was taken meanwhile; nothing was bridged. Preview again.")
        log_history(db, exam_id=exam.id, student_id=r.student_id, action="created", actor=user.username, allotment_id=a.id,
                    new=(a.hall, a.seat), reason=f"VSB allocation batch {b.id}")
        r.allotment_id = a.id
        created += 1
        events.setdefault(exam.id, []).append({"student_id": r.student_id, "kind": "allocated", "hall": a.hall, "seat": a.seat})
    audit.record(db, user.username, "vsb_alloc.bridged", str(b.id), {"created": created, "blocked": plan["summary"]["blocked"]}, request, user.role)
    db.commit()
    from .. import notifications as notify
    for exam_id, evs in events.items():
        notify.notify_seat_events(db, db.get(models.Exam, exam_id), evs, user.username)
    return {"created": created, "skipped_blocked": plan["summary"]["blocked"]}


@router.get("/records/{record_id}/edits")
def record_edits(record_id: int, db: Session = Depends(get_db), user: models.User = Depends(require_roles(*STAFF))):
    _record(db, record_id)
    return [{"field": e.field, "old": e.old_value, "new": e.new_value, "by": e.edited_by, "at": iso(e.edited_at), "reason": e.reason}
            for e in db.scalars(select(dm.VsbAllocEdit).where(dm.VsbAllocEdit.record_id == record_id).order_by(dm.VsbAllocEdit.id.desc())).all()]


# ----------------------------------------------------------------------------- students
def published_for_student(db: Session, student: models.Student) -> list[dict]:
    """Only approved records of PUBLISHED batches, matched to this student record. Used by the signed-in and public lookups."""
    rows = db.execute(select(dm.VsbAllocRecord, dm.VsbAllocBatch).join(dm.VsbAllocBatch, dm.VsbAllocBatch.id == dm.VsbAllocRecord.batch_id)
                      .where(dm.VsbAllocRecord.student_id == student.id, dm.VsbAllocRecord.published == True,  # noqa: E712
                             dm.VsbAllocRecord.review_status == "approved", dm.VsbAllocBatch.status == "published")
                      .order_by(dm.VsbAllocBatch.exam_date, dm.VsbAllocBatch.session)).all()
    out = []
    for r, b in rows:
        src = None
        v = db.get(dm.DocumentVersion, b.seat_version_id or b.hall_version_id) if (b.seat_version_id or b.hall_version_id) else None
        d = db.get(dm.OfficialDocument, v.document_id) if v else None
        if d is not None:
            src = {"title": d.title, "url": d.source_url}
        out.append({"register_number": r.register_number, "department": r.department, "subject_code": r.subject_code,
                    "subject": r.subject_title, "exam": b.exam_name, "date": iso(b.exam_date), "session": b.session,
                    "hall": r.hall, "seat": r.seat, "source": src, "published_at": iso(b.published_at),
                    "verify_note": "The official PDF was replaced after this was published; confirm with the Controller of Examinations."
                    if svc.source_changed(db, b) else None})
    return out


@router.get("/my")
def my_allocation(db: Session = Depends(get_db), user: models.User = Depends(require_roles("student"))):
    """The signed-in student's own confirmed hall and seat details (approved + published only)."""
    if not user.student_id:
        raise HTTPException(403, "This account is not linked to a student record")
    s = db.get(models.Student, user.student_id)
    if not s:
        raise HTTPException(404, "Linked student record not found")
    return {"register_number": s.register_number, "allocations": published_for_student(db, s),
            "note": "Only seats confirmed by the examination office are shown. If yours is missing, check the official notice and ask the Controller of Examinations."}
