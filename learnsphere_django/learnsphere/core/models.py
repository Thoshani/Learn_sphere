from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [("user", "Student"), ("admin", "Admin")]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")
    avatar = models.CharField(max_length=8, default="🧑‍🎓")
    bio = models.TextField(blank=True)

    @property
    def is_platform_admin(self):
        return self.role == "admin" or self.is_superuser

    @property
    def display_name(self):
        return self.get_full_name() or self.username


class Course(models.Model):
    LEVELS = [("Beginner", "Beginner"), ("Intermediate", "Intermediate"), ("Advanced", "Advanced")]
    AUDIENCES = [(a, a) for a in ["Primary", "High School", "Diploma", "Bachelors", "Masters"]]
    STATUS = [("outline", "Outline ready"), ("generating", "Generating"),
              ("ready", "Ready"), ("failed", "Failed")]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="courses")
    name = models.CharField(max_length=200)
    audience = models.CharField(max_length=30, choices=AUDIENCES, default="Bachelors")
    level = models.CharField(max_length=20, choices=LEVELS, default="Beginner")
    num_modules = models.PositiveIntegerField(default=4)
    duration = models.CharField(max_length=80, blank=True)
    credit = models.CharField(max_length=80, blank=True)
    outline = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="outline")
    progress = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    quiz_raw = models.TextField(blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.course.name} – {self.title}"


class Question(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveIntegerField(default=0)
    text = models.TextField()
    option_a = models.TextField()
    option_b = models.TextField(blank=True)
    option_c = models.TextField(blank=True)
    option_d = models.TextField(blank=True)
    answer = models.CharField(max_length=1)
    explanation = models.TextField(blank=True)

    class Meta:
        ordering = ["order"]

    @property
    def options(self):
        pairs = [("A", self.option_a), ("B", self.option_b), ("C", self.option_c), ("D", self.option_d)]
        return [(k, v) for k, v in pairs if v]


class QuizAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts")
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="attempts")
    score = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def pct(self):
        return round(self.score / self.total * 100) if self.total else 0


class Feedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback")
    rating = models.PositiveSmallIntegerField(default=5)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ChatMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat")
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=10)  # user / assistant
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
