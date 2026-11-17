"""Seating-sheet fixtures.

REAL_TEXT_* : text layer of pages of the official 14.11.26-FN-SEAT.pdf (fetched 15 Nov 2026), register numbers rewritten
              92252x -> 92259x (see fixtures_hall.py). They exercise the text-order fallback and the table-row logic.
build_page  : synthetic page generator that reproduces the printed geometry (4 serpentine columns, 7 rows) and emits BOTH the
              stream-order text and word boxes, so the coordinate mapping can be tested - including empty cells whose seat
              number is printed without a register number, dropped labels and duplicated labels.
write_pdf   : draws a generated page with reportlab so real PDF coordinates can be read back (pdfplumber in tests, PyMuPDF in
              production).
"""
from app.vsb_alloc.common import PageInput, Word

PAGE_HEAD = """V.S.B. ENGINEERING COLLEGE
(An Autonomous Institution)
Approved by AICTE, Affiliated to Anna University, Chennai.
NH-67 Covai Road, Karudayampalayam Post, Karur-639111.-
HALL SEATING FOR THE END SEMESTER EXAMINATIONS - DEC 2026
DATE OF EXAMINATION: 14-11-2026 SESSION : FN
"""
TABLE_HEAD = "CODE TITLE OF THE PAPER TOTAL REGISTER NUMBERS\n"

# ----- verbatim-structure pages (text layer) -----
REAL_TEXT_02 = PAGE_HEAD + """EXAM HALL : MB III 02 Name of the Hall Superindentent : 
1 14 15 28 922595104013
2 922595104001 13 922595105006 16 922595104007 27 922595105012
3 922595105001 12 922595104006 17 922595105007 26 922595104012
4 922595104002 11 922595105005 18 922595104008 25 922595105011
5 922595105002 10 922595104005 19 922595105008 24 922595104011
6 922595104003 9 922595105004 20 922595104009 23 922595105010
7 922595105003 8 922595104004 21 922595105009 22 922595104010
""" + TABLE_HEAD + """23CST302R FOUNDATIONS OF DATA SCIENCE 13 922595104001 - 013
23EET302R ELECTRICAL MACHINES - I 12 922595105001 - 012
TOTAL 25
"""

REAL_TEXT_103 = PAGE_HEAD + """EXAM HALL : MB III 103 Name of the Hall Superindentent : 
1 14 15 28 922595104078
2 922595104066 13 922595244002 16 922595104072 27 922595244008
3 922595105063 12 922595104071 17 922595244003 26 922595104077
4 922595104067 11 922595244001 18 922595104073 25 922595244007
5 922595105301 10 922595104070 19 922595244004 24 922595104076
6 922595104068 9 922595105501 20 922595104074 23 922595244006
7 922595105302 8 922595104069 21 922595244005 22 922595104075
""" + TABLE_HEAD + """23CST302R FOUNDATIONS OF DATA SCIENCE 13 922595104066 - 078
23CBT303 FORMAL LANGUAGE AND AUTOMATA THEORY 8 922595244001 - 008
23EET302R ELECTRICAL MACHINES - I 4 922595105063, 301 - 302, 501
TOTAL 25
"""

REAL_TEXT_208 = PAGE_HEAD + """EXAM HALL : MB III 208 Name of the Hall Superindentent : 
1 14 15 28 922595121003
2 922595104186 13 922595205016 16 922595104301 27 922595205022
3 922595205011 12 922595104193 17 922595205017 26 922595121002
4 922595104187 11 922595205015 18 922595104302 25 922595205021
5 922595205012 10 922595104192 19 922595205018 24 922595121001
6 922595104188 9 922595205014 20 922595104303 23 922595205020
7 922595205013 8 922595104189 21 922595205019 22 922595104304
""" + TABLE_HEAD + """23BMT302 SENSORS AND MEASUREMENTS 3 922595121001 - 003
23CST302R FOUNDATIONS OF DATA SCIENCE 22 922595104186 - 189, 192 - 193, 301 - 304, 922595205011 - 022
TOTAL 25
"""

# register lines are printed BEFORE the "CODE TITLE TOTAL" line of the second subject
REAL_TEXT_A203 = PAGE_HEAD + """EXAM HALL : MB III A203 Name of the Hall Superindentent : 
1 14 15 28 922595148126
2 922595148114 13 922594243183 16 922595148120 27 922594205007
3 922594105032 12 922595148119 17 922594243302 26 922595148125
4 922595148115 11 922594243163 18 922595148121 25 922594114062
5 922594105306 10 922595148118 19 922594114008 24 922595148124
6 922595148116 9 922594243159 20 922595148122 23 922594114030
7 922594243158 8 922595148117 21 922594114026 22 922595148123
""" + TABLE_HEAD + """23CST302R FOUNDATIONS OF DATA SCIENCE 13 922595148114 - 126
922594105032, 306, 922594114008, 026, 030, 062, 922594205007,
922594243158 - 159, 163, 183, 302
23GET401R ENVIRONMENTAL SCIENCE AND ENGINEERING 12
TOTAL 25
"""

# the anomalous real page: some seat numbers are missing/duplicated in the text layer, a whole row (6) has no labels
REAL_TEXT_A204 = PAGE_HEAD + """EXAM HALL : MB III A204 Name of the Hall Superindentent : 
1 14 15 28 922593103012
2 922595148127 27 16 27
3 922594205111 12 922594205182 17 922594148060 26 922594103004
4 922595148301 25 18 25
5 922594205116 10 922594244023 19 922594103016 24 922594214026
7 922595148302 8 922594118014 21 922594121020 22 922594103014
""" + TABLE_HEAD + """23CET304 WATER SUPPLY AND WASTEWATER ENGINEERING 2 922593103012, 922594103004
23CST302R FOUNDATIONS OF DATA SCIENCE 3 922595148127, 301 - 302
922594103014, 016, 922594118014, 922594121020, 922594148060,
922594205111, 116, 182, 922594214026, 922594244023
23GET401R 10 ENVIRONMENTAL SCIENCE AND ENGINEERING
TOTAL 15
"""

# ----- synthetic generator -----
LABEL_X = [40.0, 170.0, 300.0, 430.0]
ROW_Y0, ROW_DY = 150.0, 18.0
SEAT_OF = [lambda r: 1 + r, lambda r: 14 - r, lambda r: 15 + r, lambda r: 28 - r]     # serpentine, rows 0..6


def seat_cell(seat: int):
    for c, f in enumerate(SEAT_OF):
        for r in range(7):
            if f(r) == seat:
                return r, c
    raise ValueError(seat)


def build_page(index, hall, seats, subjects, *, date="14-11-2026", session="FN", total=None, pre_lines=(),
               drop_labels=(), extra_labels=(), with_words=True, table_total_override=None):
    """seats: {seat_no: register_number}. subjects: [(code, title, total, register_text)].
    pre_lines: codes whose register text is printed on lines BEFORE the code line (vertically centred cell).
    drop_labels: [(row, col)] cells whose seat number is NOT printed. extra_labels: [(row, col, number)] stray labels."""
    words: list[Word] = []
    text = PAGE_HEAD.replace("14-11-2026", date).replace("SESSION : FN", f"SESSION : {session}")
    text += f"EXAM HALL : {hall} Name of the Hall Superindentent : \n"
    y = 100.0
    for t, x in (("EXAM", 40), ("HALL", 80), (":", 110), (hall, 120), ("Name", 250), ("of", 280), ("the", 295), ("Hall", 315),
                 ("Superindentent", 340), (":", 420)):
        words.append(Word(t, x, y, x + 6 * len(t), y + 9))
    drop = set(drop_labels)
    extra: dict = {}
    for r, c, n in extra_labels:
        extra.setdefault((r, c), []).append(n)
    for r in range(7):
        yy = ROW_Y0 + ROW_DY * r
        toks = []
        for c in range(4):
            n = SEAT_OF[c](r)
            reg = seats.get(n)
            if (r, c) not in drop:
                toks.append(str(n))
                words.append(Word(str(n), LABEL_X[c], yy, LABEL_X[c] + 7 * len(str(n)), yy + 9))
            for n2 in extra.get((r, c), []):
                toks.append(str(n2))
                words.append(Word(str(n2), LABEL_X[c], yy, LABEL_X[c] + 7 * len(str(n2)), yy + 9))
            if reg:
                toks.append(reg)
                words.append(Word(reg, LABEL_X[c] + 26, yy, LABEL_X[c] + 26 + 6 * len(reg), yy + 9))
        if any(t for t in toks):
            text += " ".join(_group_empty(toks)) + "\n"
    ty = 300.0
    for t, x in (("CODE", 40), ("TITLE", 100), ("OF", 140), ("THE", 160), ("PAPER", 185), ("TOTAL", 300), ("REGISTER", 350), ("NUMBERS", 420)):
        words.append(Word(t, x, ty, x + 6 * len(t), ty + 9))
    text += TABLE_HEAD
    for code, title, tot, regs in subjects:
        if code in pre_lines:
            parts = [p.strip() for p in regs.split("\n")]
            text += "\n".join(parts) + "\n" + f"{code} {tot} {title}\n"
        else:
            text += f"{code} {title} {tot} {regs}\n"
    text += f"TOTAL {total if total is not None else len(seats)}\n" if table_total_override is None else f"TOTAL {table_total_override}\n"
    return PageInput(index, text, words if with_words else [], "text_layer")


def _group_empty(toks):
    return toks


def write_pdf(path, page: PageInput, height=842.0):
    """Draw the generated page's words with reportlab (text drawn in word order)."""
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(path, pagesize=(595.0, height))
    c.setFont("Helvetica", 8)
    for w in page.words:
        c.drawString(w.x0, height - w.y1 + 2, w.text)
    c.showPage()
    c.save()
