"""Official-source integration: the verified page, link extraction/classification on the REAL link list, host rules."""
from datetime import date

from app import vsb_sources as vs

OFFICIAL = "https://vsbec.edu.in/controller-of-examination/"
BASE = "https://vsbec.edu.in/wp-content/uploads/"
# Link texts and addresses exactly as listed on the official page (checked 15 Nov 2026), plus the other PDF/links found there.
REAL_HTML = f"""
<nav><a href="{BASE}2026/03/IQAC-composition-2025-2026.pdf">IQAC</a><a href="{BASE}2021/10/ARIIA-2021-Report_.pdf">ARIIA</a></nav>
<table><tr>
<td><a href="https://coe.vsbec.edu.in/students/">Results</a></td>
<td><a href="{BASE}2026/10/NOV_DEC_2026-END-SEM-TIME-TABLE-PHASE_1.pdf">End-Semester Examination Timetable</a></td>
<td><a href="{BASE}2026/08/Academic-schedule-for-2026-27-ODD-SEM.pdf">Academic Schedule</a></td></tr>
<tr><td><a href="https://coe.vsbec.edu.in/internals/">COE Staff Login</a></td>
<td><a href="{BASE}2026/10/Anna-University-Malpractice_punishments.pdf">PUNISHMENT FOR MALPRACTICE CASES</a></td></tr>
<tr><td><a href="{BASE}2026/11/14.11.26-FN-HALL.pdf">HALL ALLOTMENT - FN (14.11.2026)</a></td>
<td><a href="{BASE}2026/11/14.11.26-AN-HALL.pdf">HALL ALLOTMENT - AN (14.11.2026)</a></td></tr>
<tr><td><a href="{BASE}2026/11/14.11.26-FN-SEAT.pdf">SEATING ALLOTMENT - FN (14.11.2026)</a></td>
<td><a href="{BASE}2026/11/14.11.26-AN-SEAT.pdf">SEATING ALLOTMENT - AN (14.11.2026)</a></td></tr>
<tr><td><a href="{BASE}2026/11/16.11.26-FN-HALL.pdf">HALL ALLOTMENT - FN (16.11.2026)</a></td>
<td><a href="{BASE}2026/11/16.11.26-AN-SEAT.pdf">SEATING ALLOTMENT - AN (16.11.2026)</a></td></tr></table>
<a href="http://evil.example/x.pdf">offsite</a><a href="https://vsbec.edu.in.evil.example/y.pdf">lookalike</a>
"""


def test_verified_official_sources_are_preserved():
    urls = {s["key"]: s["url"] for s in vs.CONFIRMED_SOURCES}
    assert urls["coe_page"] == OFFICIAL
    assert vs.coe_page_url() == OFFICIAL
    crawl = [s["key"] for s in vs.CONFIRMED_SOURCES if s["crawl"]]
    assert crawl == ["coe_page"]


def test_only_official_https_pdf_links_are_extracted():
    links = vs.extract_pdf_links(REAL_HTML, OFFICIAL)
    urls = [l["url"] for l in links]
    assert all(u.startswith("https://vsbec.edu.in/") and u.endswith(".pdf") for u in urls)
    assert not any("evil" in u or "coe.vsbec" in u for u in urls)
    assert len(urls) == len(set(urls)) == 11


def test_real_allotment_links_are_classified_with_date_and_session():
    got = {l["url"].rsplit("/", 1)[1]: vs.classify(l["url"], l["text"]) for l in vs.extract_pdf_links(REAL_HTML, OFFICIAL)}
    c = got["14.11.26-FN-HALL.pdf"]
    assert (c["doc_kind"], c["exam_date"], c["session"], c["upload_month"]) == ("hall_allotment", date(2026, 11, 14), "FN", "2026-11")
    c = got["14.11.26-AN-SEAT.pdf"]
    assert (c["doc_kind"], c["exam_date"], c["session"]) == ("seating_allotment", date(2026, 11, 14), "AN")
    assert got["16.11.26-FN-HALL.pdf"]["exam_date"] == date(2026, 11, 16)
    assert got["16.11.26-AN-SEAT.pdf"]["doc_kind"] == "seating_allotment"
    assert got["NOV_DEC_2026-END-SEM-TIME-TABLE-PHASE_1.pdf"]["doc_kind"] == "timetable"
    assert got["Anna-University-Malpractice_punishments.pdf"]["doc_kind"] == "notice"
    assert got["Academic-schedule-for-2026-27-ODD-SEM.pdf"]["doc_kind"] == "other"
    assert got["IQAC-composition-2025-2026.pdf"]["doc_kind"] == "other"


def test_file_name_alone_is_enough_when_text_is_empty():
    c = vs.classify(BASE + "2026/11/14.11.26-AN-HALL.pdf", "")
    assert (c["doc_kind"], c["exam_date"], c["session"]) == ("hall_allotment", date(2026, 11, 14), "AN")


def test_new_address_for_same_document_is_a_new_link():
    html = f'<a href="{BASE}2026/11/14.11.26-FN-HALL-REVISED.pdf">HALL ALLOTMENT - FN (14.11.2026) revised</a>'
    l = vs.extract_pdf_links(html, OFFICIAL)[0]
    c = vs.classify(l["url"], l["text"])
    assert c["doc_kind"] == "hall_allotment" and c["session"] == "FN" and l["url"].endswith("REVISED.pdf")


def test_host_rules():
    assert vs.is_allowed_url("https://vsbec.edu.in/a.pdf")
    assert not vs.is_allowed_url("http://vsbec.edu.in/a.pdf")
    assert not vs.is_allowed_url("https://vsbec.edu.in.evil.example/a.pdf")
    assert not vs.is_allowed_url("https://user:pw@vsbec.edu.in/a.pdf")
    assert not vs.is_allowed_url("https://coe.vsbec.edu.in/internals/")
