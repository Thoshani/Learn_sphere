from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Course, Module, Question, QuizAttempt, Feedback, ChatMessage

admin.site.register(User, UserAdmin)
for m in (Course, Module, Question, QuizAttempt, Feedback, ChatMessage):
    admin.site.register(m)
