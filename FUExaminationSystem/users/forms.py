from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import InstructorProfile, StudentProfile, User

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'profile_picture', 'bio', 'is_student', 'is_instructor']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_student = True
        if commit:
            user.save()
            
            import uuid
            student_id = str(uuid.uuid4().hex)[:8]  
            
            if user.is_student:
                StudentProfile.objects.create(
                    user=user,
                    student_id=f"ST{student_id}",  
                    department=""
                )
            elif user.is_instructor:
                InstructorProfile.objects.create(
                    user=user,
                    employee_id=f"INS{student_id}",  
                    department="",
                    specialization=""
                )

        return user

class CustomAuthenticationForm(forms.Form):
    username = forms.CharField()
    email = forms.CharField(widget=forms.EmailInput)
    password = forms.CharField(widget=forms.PasswordInput)




class EditProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'bio', 'profile_picture']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'profile_picture': forms.FileInput(),
        }