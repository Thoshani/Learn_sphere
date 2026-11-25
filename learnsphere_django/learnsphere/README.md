# 🎓 LearnSphere (Django)

AI-powered e-learning platform — a Django port of the original Streamlit + Groq app.

## Setup
```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then put your GROQ_API_KEY inside
python manage.py migrate
python manage.py seed_demo    # creates demo_student/demo123 and demo_admin/admin123
python manage.py runserver
```
Open http://127.0.0.1:8000

Set `AI_MOCK=1` in `.env` to try the whole app without an API key (fake AI output).

## Features
- Sign up / login / demo login, student & admin roles
- AI course outline (Prompter → Tabler), outline editing, full course generation
  (DICTator → Coursify lessons → Quizzy quizzes) running in a background thread with live progress
- Module reader, 10-question quizzes with instant scoring + explanations, saved attempts
- AI tutor chat (per-user history, optional course context), progress page
- Feedback, profile (avatar, bio, password)
- Admin: dashboard, manage users (add/delete/toggle role), all performance, all feedback
- PDF export of a full course

## Layout
- `core/models.py` – User, Course, Module, Question, QuizAttempt, Feedback, ChatMessage
- `core/services/ai.py` – LLM calls, parsing, background generation
- `core/services/prompts.py` – all prompts
- `core/services/pdf.py` – PDF builder
- `core/views.py`, `core/urls.py`, `core/templates/core/*`

## Notes
- Generation uses a plain thread (fine for development / single-process). For production use Celery or RQ.
- Set a real `DJANGO_SECRET_KEY` and `DJANGO_DEBUG=0` for deployment.
- The original prompt files in `prompts/` weren't readable, so the built-in fallback prompts from `ai.py` are used.
