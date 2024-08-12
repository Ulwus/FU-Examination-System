from django import forms
from .models import Exam, Question, Answer

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['title', 'description', 'start_time', 'end_time', 'duration', 'total_marks', 'passing_marks', 'is_active']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text']  # 'marks' ve 'question_type' kaldırıldı

class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ['text', 'is_correct']  # 'question' alanı formset ile kontrol edilecek

    def __init__(self, *args, **kwargs):
        self.question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)
        if self.question:
            self.fields['is_correct'].required = False  # Doğru cevap işaretlenmesini zorunlu kılma

class QuestionFormSet(forms.BaseFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queryset = self.queryset.none()  # Formset'in queryset'ini yok sayarak formset'i dinamik yapacağız

class AnswerFormSet(forms.BaseFormSet):
    def __init__(self, *args, **kwargs):
        self.question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)
        self.queryset = self.queryset.none()  # Formset'in queryset'ini yok sayarak formset'i dinamik yapacağız

