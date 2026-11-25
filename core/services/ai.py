import json
import re
import threading

from django.conf import settings
from django.db import connection, transaction

from . import prompts


class AIError(Exception):
    pass


# ---------------------------------------------------------------- LLM calls
def _mock(system, user):
    s = system.lower()
    if "you are prompter" in s:
        return "Create an outline for the given course using all six inputs."
    if "you are tabler" in s:
        return ("# Course Outline\n\n## Module 1: Foundations\n- Lesson 1.1: Introduction\n- Lesson 1.2: Core Concepts\n\n"
                "## Module 2: Applications\n- Lesson 2.1: Real-world Use\n- Lesson 2.2: Case Study\n")
    if "you are dictator" in s:
        return json.dumps({"Module 1: Foundations": ["Lesson 1.1: Introduction", "Lesson 1.2: Core Concepts"],
                           "Module 2: Applications": ["Lesson 2.1: Real-world Use", "Lesson 2.2: Case Study"]})
    if "you are quizzy" in s:
        out = []
        for i in range(1, 11):
            out.append(f"Q{i}. Sample question {i}?\nA) Option A\nB) Option B\nC) Option C\nD) Option D\n"
                       f"Answer: {'ABCD'[i % 4]}\nExplanation: Because it is correct.\n")
        return "\n".join(out)
    if "you are coursify" in s:
        return "## Introduction\n\nThis is **mock** lesson content.\n\n- Key term: *example*\n- Summary"
    return "This is a mock tutor reply."


def call_llm(system, user="", messages=None, max_tokens=4096):
    """Call the chat-completions API. `messages` (history) may be passed instead of `user`."""
    if settings.AI_MOCK:
        return _mock(system, user or (messages[-1]["content"] if messages else ""))
    if not settings.GROQ_API_KEY:
        raise AIError("GROQ_API_KEY is not set. Add it to your .env file.")
    from openai import OpenAI
    client = OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.AI_BASE_URL)
    msgs = [{"role": "system", "content": system}]
    if messages:
        msgs += messages
    elif user:
        msgs.append({"role": "user", "content": user})
    try:
        r = client.chat.completions.create(model=settings.AI_MODEL, messages=msgs, max_tokens=max_tokens)
    except Exception as e:  # network / auth / rate-limit
        raise AIError(str(e)) from e
    return r.choices[0].message.content or ""


# ---------------------------------------------------------------- parsing
def parse_quiz(text):
    """Parse Quizzy output into a list of dicts."""
    qs = []
    for block in re.split(r"\n\s*Q\d+[\.\)]", "\n" + (text or "")):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        q, opts, ans, exp = lines[0].strip(), {}, "", ""
        for ln in lines[1:]:
            ln = ln.strip()
            m = re.match(r"^([A-D])[\)\.]\s*(.*)$", ln)
            if m:
                opts[m.group(1)] = m.group(2).strip()
            elif ln.lower().startswith("answer:"):
                m2 = re.search(r"[A-D]", ln.split(":", 1)[1].upper())
                ans = m2.group(0) if m2 else ""
            elif ln.lower().startswith("explanation:"):
                exp = ln.split(":", 1)[1].strip()
        if q and opts.get("A") and ans:
            qs.append({"question": q, "options": opts, "answer": ans, "explanation": exp})
    return qs


def parse_modules(text):
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text or "", re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                return None
    return None


# ---------------------------------------------------------------- course generation
def generate_outline(course):
    p = prompts.PROMPTER_TEMPLATE.format(
        name=course.name, audience=course.audience, level=course.level,
        modules=course.num_modules, duration=course.duration or "n/a", credit=course.credit or "n/a")
    smart_prompt = call_llm(p)
    return call_llm(prompts.TABLER_PROMPT, smart_prompt)


def modify_outline(course, changes):
    p = ("Modify this course outline using the changes described and return the complete updated outline.\n"
         f"Changes: {changes}\nCurrent outline: {course.outline}")
    return call_llm(prompts.TABLER_PROMPT, p)


def _set_progress(course, text, status=None):
    course.progress = text
    fields = ["progress"]
    if status:
        course.status = status
        fields.append("status")
    course.save(update_fields=fields)


def run_generation(course_id):
    """Background job: outline -> modules -> lessons -> quizzes. Persists everything to the DB."""
    from core.models import Course, Module, Question
    try:
        course = Course.objects.get(pk=course_id)
        course.error = ""
        _set_progress(course, "Extracting module structure…", "generating")

        structure = parse_modules(call_llm(prompts.DICTATOR_PROMPT, course.outline))
        if not structure:
            raise AIError("Could not parse the module structure. Please try again.")

        course.modules.all().delete()
        for idx, (mod_title, lessons) in enumerate(structure.items(), start=1):
            content = ""
            for les in lessons:
                _set_progress(course, f"Module {idx}/{len(structure)} – writing: {les}")
                p = prompts.COURSIFY_TEMPLATE.format(lesson=les, module=mod_title, course=course.name,
                                                     audience=course.audience, level=course.level)
                content += f"## {les}\n\n{call_llm(p)}\n\n---\n\n"

            _set_progress(course, f"Module {idx}/{len(structure)} – generating quiz…")
            quiz_raw = call_llm(prompts.QUIZZY_PROMPT + content[:12000])
            module = Module.objects.create(course=course, order=idx, title=mod_title,
                                           content=content, quiz_raw=quiz_raw)
            Question.objects.bulk_create([
                Question(module=module, order=i, text=q["question"],
                         option_a=q["options"].get("A", ""), option_b=q["options"].get("B", ""),
                         option_c=q["options"].get("C", ""), option_d=q["options"].get("D", ""),
                         answer=q["answer"], explanation=q["explanation"])
                for i, q in enumerate(parse_quiz(quiz_raw), start=1)
            ])
        _set_progress(course, "Done", "ready")
    except Exception as e:
        try:
            course = Course.objects.get(pk=course_id)
            course.status, course.error, course.progress = "failed", str(e), "Failed"
            course.save(update_fields=["status", "error", "progress"])
        except Exception:
            pass
    finally:
        connection.close()  # release this thread's DB connection


def start_generation(course):
    course.status, course.progress = "generating", "Starting…"
    course.save(update_fields=["status", "progress"])
    t = threading.Thread(target=run_generation, args=(course.pk,), daemon=True)
    # Start after the surrounding transaction commits so the thread sees the updated row.
    transaction.on_commit(t.start)
