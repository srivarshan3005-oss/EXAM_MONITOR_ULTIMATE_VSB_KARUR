# VSB Karur official data: provenance and verification limits

## Provenance
All notice documents come only from links found on the official Controller of Examinations page, https://vsbec.edu.in/controller-of-examination/ (V.S.B. Engineering College, Karur). Each stored document keeps its source URL, discovery time and file hash; the staff and student screens show "Source:" links back to the college site. The application never constructs PDF addresses and never contains official PDFs or seating data of its own. Hall capacities, register numbers and seat numbers are **never** guessed: a value that cannot be read is left empty and flagged.

## Publication rules (enforced in code)
* Parsed data is a proposed batch. Nothing is visible to students until an **administrator** approves records and publishes the batch with a confirmation bound to the previewed data.
* "Approve confident" approves only records with no flag at all. A flagged record (including every seat with the flag `seat_from_text_order` = seat paired from text order, **unconfirmed**) needs an individual administrator decision with a written note of how it was verified against the official PDF; blocking flags need an extra acknowledgement. Records without hall or seat can never be published. Students only see approved, published records.

## What was actually validated (16 Nov 2026)
Text extracted by a fetch tool from `16.11.26-FN-HALL.pdf` and `16.11.26-FN-SEAT.pdf` (raw PDF files could not be downloaded in the sandbox). **Selected pages only:** 10 hall-list programme pages (282 students; all 10 printed totals reconciled) and 7 seating sheets (A101, A202, A203, A204, A303, A304, 02: 170 seats matched an independent reading, 0 mismatches). Halls A202, A203, A204, A303, A304 agree exactly between hall list and seating sheets.

## NOT verified
Raw-PDF extraction and **OCR** on real files; coordinate-based seat mapping on real files; the **AN** session; the **14 November 2026** PDFs; the ECE and AI&DS blocks and all other hall sheets of 16 Nov; any later notices. Real register numbers used for the test run were removed from this package.

## Manual validation procedure
1. In the staff page "VSB official notices" run *Check official page now*; download the hall and seating PDFs.
2. Process them into a draft batch; open every issue and every flagged record.
3. For each hall, compare in a PDF viewer: register numbers, hall, date, FN/AN session and each seat number; check totals against the printed "TOTAL".
4. Correct or reject anything uncertain; approve records individually where flagged, with a note.
5. Use the publish preview, check counts, then publish. Withdraw immediately if a discrepancy is found.
