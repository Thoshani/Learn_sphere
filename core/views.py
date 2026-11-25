from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import admin_required
from .forms import AdminUserForm, CourseForm, FeedbackForm, ProfileForm, SignupForm
from .models import ChatMessage, Course, Feedback, Module, QuizAttempt
from .services import ai, prompts
from .services.pdf import build_course_pdf

User = get_user_model()


# ------------------------------------------------------------------ auth
def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to LearnSphere!")
        return redirect("dashboard")
    return render(request, "core/signup.html", {"form": form})


@require_POST
def demo_login(request):
    user, created = User.objects.get_or_create(
        username="demo_student", defaults={"first_name": "Alex", "last_name": "Demo",
                                           "email": "alex@demo.com", "role": "user"})
    if created:
        user.set_password("demo123")
        user.save()
    login(request, user)
    return redirect("dashboard")


# ------------------------------------------------------------------ dashboard
@login_required
def dashboard(request):
    attempts = QuizAttempt.objects.filter(user=request.user)
    avg = round(sum(a.pct for a in attempts) / attempts.count()) if attempts.exists() else 0
    ctx = {
        "courses_count": Course.objects.filter(status="ready").count(),
        "quizzes_taken": attempts.count(),
        "avg_score": avg,
        "my_modules": Module.objects.filter(course__owner=request.user).count(),
        "recent": attempts.select_related("module")[:5],
        "latest_courses": Course.objects.filter(status="ready").annotate(n=Count("modules"))[:3],
    }
    return render(request, "core/dashboard.html", ctx)


# ------------------------------------------------------------------ courses
@login_required
def generate(request):
    form = CourseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)
        course.owner = request.user
        try:
            course.outline = ai.generate_outline(course)
        except ai.AIError as e:
            messages.error(request, f"AI error: {e}")
            return render(request, "core/generate.html", {"form": form})
        course.save()
        messages.success(request, "Course outline generated!")
        return redirect("course_detail", pk=course.pk)
    return render(request, "core/generate.html", {"form": form})


@login_required
def courses(request):
    mine = request.GET.get("scope") == "mine"
    qs = Course.objects.select_related("owner").annotate(n=Count("modules"))
    qs = qs.filter(owner=request.user) if mine else qs.filter(status="ready")
    return render(request, "core/courses.html", {"courses": qs, "mine": mine})


@login_required
def course_detail(request, pk):
    course = get_object_or_404(Course.objects.select_related("owner"), pk=pk)
    is_owner = course.owner_id == request.user.pk or request.user.is_platform_admin
    if course.status != "ready" and not is_owner:
        raise Http404
    return render(request, "core/course_detail.html", {
        "course": course, "is_owner": is_owner,
        "modules": course.modules.prefetch_related("questions"),
    })


@login_required
@require_POST
def course_modify(request, pk):
    course = get_object_or_404(Course, pk=pk, owner=request.user)
    changes = request.POST.get("changes", "").strip()
    if not changes:
        messages.error(request, "Describe the changes you want.")
    elif course.status == "generating":
        messages.error(request, "Course is currently generating.")
    else:
        try:
            course.outline = ai.modify_outline(course, changes)
            course.status = "outline"
            course.save()
            course.modules.all().delete()
            messages.success(request, "Outline updated. Regenerate the full course to apply changes.")
        except ai.AIError as e:
            messages.error(request, f"AI error: {e}")
    return redirect("course_detail", pk=pk)


@login_required
@require_POST
def course_run(request, pk):
    course = get_object_or_404(Course, pk=pk, owner=request.user)
    if course.status != "generating":
        ai.start_generation(course)
    return redirect("course_detail", pk=pk)


@login_required
def course_status(request, pk):
    course = get_object_or_404(Course, pk=pk)
    return JsonResponse({"status": course.status, "progress": course.progress, "error": course.error})


@login_required
def course_pdf(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if course.status != "ready":
        raise Http404
    resp = HttpResponse(build_course_pdf(course), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{course.name.replace(" ", "_")}.pdf"'
    return resp


@login_required
@require_POST
def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if course.owner_id != request.user.pk and not request.user.is_platform_admin:
        raise Http404
    course.delete()
    messages.success(request, "Course deleted.")
    return redirect("courses")


# ------------------------------------------------------------------ quiz
@login_required
def quiz_list(request):
    return render(request, "core/quiz_list.html", {
        "courses": Course.objects.filter(status="ready").prefetch_related("modules__questions")})


@login_required
def quiz_take(request, module_id):
    module = get_object_or_404(Module.objects.select_related("course"), pk=module_id, course__status="ready")
    questions = list(module.questions.all())
    if not questions:
        messages.warning(request, "This module has no parsed quiz questions.")
        return redirect("quiz_list")

    if request.method == "POST":
        rows, score = [], 0
        for q in questions:
            chosen = request.POST.get(f"q_{q.pk}", "")
            correct = chosen == q.answer
            score += correct
            rows.append({"q": q, "chosen": chosen, "correct": correct})
        attempt = QuizAttempt.objects.create(user=request.user, module=module, score=score, total=len(questions))
        g = "Excellent! 🏆" if attempt.pct >= 90 else "Great job! 🎉" if attempt.pct >= 70 else "Keep practicing! 💪"
        return render(request, "core/quiz_result.html",
                      {"module": module, "rows": rows, "attempt": attempt, "grade": g})
    return render(request, "core/quiz_take.html", {"module": module, "questions": questions})


# ------------------------------------------------------------------ AI tutor
@login_required
def tutor(request):
    course = None
    cid = request.GET.get("course") or request.POST.get("course")
    if cid:
        course = Course.objects.filter(pk=cid).first()

    if request.method == "POST":
        text = request.POST.get("message", "").strip()
        if request.POST.get("clear"):
            ChatMessage.objects.filter(user=request.user).delete()
        elif text:
            ChatMessage.objects.create(user=request.user, course=course, role="user", content=text)
            history = list(ChatMessage.objects.filter(user=request.user).order_by("-created_at")[:12])[::-1]
            ctx = f"Course: {course.name}" if course else "General learning assistant"
            try:
                reply = ai.call_llm(prompts.TUTOR_TEMPLATE.format(context=ctx),
                                    messages=[{"role": m.role, "content": m.content} for m in history],
                                    max_tokens=1024)
            except ai.AIError as e:
                reply = f"Error: {e}"
            ChatMessage.objects.create(user=request.user, course=course, role="assistant", content=reply)
        return redirect(f"{request.path}?course={course.pk}" if course else request.path)

    return render(request, "core/tutor.html", {
        "chat": ChatMessage.objects.filter(user=request.user).order_by("-created_at")[:40][::-1],
        "course": course,
        "all_courses": Course.objects.filter(status="ready"),
        "prompts": ["Explain key concepts", "Give a real example", "Summarize my learning",
                    "What to study next?", "Quiz me!"],
    })


# ------------------------------------------------------------------ progress / feedback / profile
@login_required
def progress(request):
    attempts = list(QuizAttempt.objects.filter(user=request.user).select_related("module", "module__course"))
    stats = None
    if attempts:
        scores = [a.pct for a in attempts]
        stats = {"avg": round(sum(scores) / len(scores)), "best": max(scores),
                 "count": len(attempts), "questions": sum(a.total for a in attempts)}
    return render(request, "core/progress.html", {"attempts": attempts, "stats": stats})


@login_required
def feedback(request):
    form = FeedbackForm(request.POST or None, initial={"rating": 5})
    if request.method == "POST" and form.is_valid():
        fb = form.save(commit=False)
        fb.user = request.user
        fb.save()
        messages.success(request, "Thank you for your feedback!")
        return redirect("feedback")
    return render(request, "core/feedback.html", {
        "form": form, "mine": Feedback.objects.filter(user=request.user)[:3]})


@login_required
def profile(request):
    u = request.user
    form = ProfileForm(request.POST or None, initial={
        "first_name": u.first_name, "last_name": u.last_name, "email": u.email,
        "avatar": u.avatar, "bio": u.bio})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        u.first_name, u.last_name, u.email = d["first_name"], d["last_name"], d["email"]
        u.avatar, u.bio = d["avatar"], d["bio"]
        if d["new_password"]:
            u.set_password(d["new_password"])
        u.save()
        if d["new_password"]:
            update_session_auth_hash(request, u)
        messages.success(request, "Profile saved!")
        return redirect("profile")
    attempts = QuizAttempt.objects.filter(user=u)
    avg = round(sum(a.pct for a in attempts) / attempts.count()) if attempts.exists() else 0
    return render(request, "core/profile.html", {
        "form": form, "quizzes": attempts.count(), "avg": avg,
        "courses_available": Course.objects.filter(status="ready").count()})


# ------------------------------------------------------------------ admin pages
@admin_required
def admin_panel(request):
    ctx = {
        "users": User.objects.count(), "courses": Course.objects.count(),
        "attempts": QuizAttempt.objects.count(), "feedback": Feedback.objects.count(),
        "recent": Course.objects.select_related("owner").annotate(n=Count("modules"))[:5],
    }
    return render(request, "core/admin_panel.html", ctx)


@admin_required
def manage_users(request):
    form = AdminUserForm(request.POST or None)
    if request.method == "POST" and request.POST.get("action") == "create":
        if form.is_valid():
            u = form.save(commit=False)
            u.set_password(form.cleaned_data["password"])
            u.save()
            messages.success(request, f"Created {u.username}.")
            return redirect("manage_users")
    elif request.method == "POST":
        target = get_object_or_404(User, pk=request.POST.get("user_id"))
        if target.pk == request.user.pk:
            messages.error(request, "You can't modify your own account here.")
        elif request.POST.get("action") == "delete":
            target.delete()
            messages.success(request, f"Deleted {target.username}.")
        elif request.POST.get("action") == "toggle_role":
            target.role = "user" if target.role == "admin" else "admin"
            target.save(update_fields=["role"])
        return redirect("manage_users")
    users = User.objects.order_by("username")
    rows = []
    for u in users:
        atts = list(u.attempts.all())
        rows.append({"u": u, "n": len(atts),
                     "avg": round(sum(a.pct for a in atts) / len(atts)) if atts else 0})
    return render(request, "core/manage_users.html", {"rows": rows, "form": form})


@admin_required
def all_performance(request):
    rows = []
    for u in User.objects.order_by("username"):
        atts = list(QuizAttempt.objects.filter(user=u).select_related("module"))
        pcts = [a.pct for a in atts]
        rows.append({"u": u, "attempts": atts[:6], "n": len(atts),
                     "avg": round(sum(pcts) / len(pcts)) if pcts else 0, "best": max(pcts, default=0)})
    return render(request, "core/all_performance.html", {"rows": rows})


@admin_required
def all_feedback(request):
    fb = Feedback.objects.select_related("user")
    avg = fb.aggregate(a=Avg("rating"))["a"]
    return render(request, "core/all_feedback.html", {
        "feedback": fb, "total": fb.count(), "avg": round(avg, 1) if avg else 0,
        "positive": fb.filter(rating__gte=4).count()})
