from django import forms
from django.contrib.auth import get_user_model
from .models import Course, Feedback

User = get_user_model()
AVATARS = ["🧑‍🎓", "👨‍💻", "👩‍🏫", "🧑‍🔬", "👨‍🎨", "🦸", "🧙", "🧑‍💼", "👩‍💻", "🧑‍🚀"]


class SignupForm(forms.ModelForm):
    full_name = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput, min_length=6)

    class Meta:
        model = User
        fields = ["username", "email"]

    def clean_email(self):
        email = self.cleaned_data.get("email", "")
        if not email:
            raise forms.ValidationError("Email is required.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        parts = self.cleaned_data["full_name"].split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        user.role = "user"
        if commit:
            user.save()
        return user


class CourseForm(forms.ModelForm):
    num_modules = forms.IntegerField(min_value=1, max_value=15, initial=4, label="Number of modules")

    class Meta:
        model = Course
        fields = ["name", "audience", "level", "num_modules", "duration", "credit"]
        labels = {"name": "Course name", "audience": "Your education level", "level": "Difficulty level",
                  "duration": "Course duration", "credit": "Credits / hours"}
        widgets = {"name": forms.TextInput(attrs={"placeholder": "e.g., Introduction to Data Science"}),
                   "duration": forms.TextInput(attrs={"placeholder": "e.g., 6 weeks"}),
                   "credit": forms.TextInput(attrs={"placeholder": "e.g., 3 credit hours"})}


class FeedbackForm(forms.ModelForm):
    rating = forms.ChoiceField(choices=[(i, "⭐" * i) for i in range(5, 0, -1)])

    class Meta:
        model = Feedback
        fields = ["rating", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell us what you think..."})}


class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")
    email = forms.EmailField()
    avatar = forms.ChoiceField(choices=[(a, a) for a in AVATARS])
    bio = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    new_password = forms.CharField(widget=forms.PasswordInput, required=False, min_length=6,
                                   label="New password (leave blank to keep)")


class AdminUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=6)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "username", "role"]
