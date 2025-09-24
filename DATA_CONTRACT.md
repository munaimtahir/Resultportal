# Data Contract

## students.csv
Columns:
- roll_no (string, required, unique)
- first_name (string, required)
- last_name (string, required)
- display_name (string, required) — full name
- official_email (email, required, unique, domain @pmc.edu.pk)
- recovery_email (email, optional)
- batch_code (string, e.g., b29)
- status (enum: active|inactive), default active

## results.csv
Columns:
- respondent_id (string, optional)
- roll_no (string, required) — links to Student
- name (string, required) — original name in result sheet
- block (string, required, e.g., E)
- year (int, required, e.g., 2025)
- subject (string, required, e.g., Pathology)
- written_marks (float, required)
- viva_marks (float, required)
- total_marks (float, required)
- grade (string, required)
- exam_date (date, YYYY-MM-DD, required)

## Rules
- `roll_no` must exist in `Student` on results import; otherwise skip with error.
- Marks must be non-negative; totals should match written+viva if applicable.
- Grades must match allowed set (configurable later; MVP: pass-through string).
