# boiler-reviews

Course reviews on Flask and SQLite. Parameterized queries throughout; aggregates in `course_stats`.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 init_db.py
python3 seed_db.py
python3 app.py
```

Open `http://127.0.0.1:5001/`.

Routes: `/reviews`, `/report`, `/course-stats`. SQLi notes and index design: `INDEX_NOTES.md`, `TRANSACTIONS_NOTES.md`.
