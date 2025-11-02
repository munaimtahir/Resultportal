# Import Playbook (Admin)

## 0) Prepare data
- Ensure `students.csv` (master) exists and is imported first.
- Ensure `results.csv` follows `DATA_CONTRACT.md`.

## 1) Import students
- Admin UI → Data → Import Students
- Upload `students.csv`
- Review dry-run report (unmatched emails, duplicates)
- Confirm import

## 2) Import results
- Admin UI → Data → Import Results
- Upload `results.csv`
- Dry-run preview shows:
  - created: N
  - updated: M
  - skipped (missing student / invalid marks): K with reasons
- Confirm to write

## 3) Publish
- Toggle batch to **Published** so students can see.
- Optional: send notification emails on publish.

## 4) Audit
- ImportBatch detail keeps: who, when, counts, file name.
