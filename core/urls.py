from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("demo/", views.demo_login, name="demo_login"),

    path("", views.dashboard, name="dashboard"),
    path("generate/", views.generate, name="generate"),
    path("courses/", views.courses, name="courses"),
    path("courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("courses/<int:pk>/modify/", views.course_modify, name="course_modify"),
    path("courses/<int:pk>/run/", views.course_run, name="course_run"),
    path("courses/<int:pk>/status/", views.course_status, name="course_status"),
    path("courses/<int:pk>/pdf/", views.course_pdf, name="course_pdf"),
    path("courses/<int:pk>/delete/", views.course_delete, name="course_delete"),

    path("quiz/", views.quiz_list, name="quiz_list"),
    path("quiz/<int:module_id>/", views.quiz_take, name="quiz_take"),
    path("tutor/", views.tutor, name="tutor"),
    path("progress/", views.progress, name="progress"),
    path("feedback/", views.feedback, name="feedback"),
    path("profile/", views.profile, name="profile"),

    path("manage/", views.admin_panel, name="admin_panel"),
    path("manage/users/", views.manage_users, name="manage_users"),
    path("manage/performance/", views.all_performance, name="all_performance"),
    path("manage/feedback/", views.all_feedback, name="all_feedback"),
]
