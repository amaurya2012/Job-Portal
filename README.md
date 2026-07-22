# Job Portal (Flask)

Quick start:

1. Create a virtualenv and activate it

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill values (Gmail app password recommended for `EMAIL_PASS`).

4. (Optional) Update DB schema:

```bash
python update_db.py
```

5. Run the app:

```bash
python app.py
```

6. Open http://127.0.0.1:5000 in your browser.

Notes:
- Uploaded resumes are saved to `static/resumes`.
- Default secret is read from `SECRET_KEY` in `.env`; change it for production.
- This project uses a simple SQLite DB `database.db` in the project root.
