from datetime import timedelta
from django.db import models
from django.utils import timezone
from users.models import User



class Exam(models.Model):
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_exams')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=30)
    total_marks = models.PositiveIntegerField(default=10)
    passing_marks = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    predefined_vars = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Sınav"
        verbose_name_plural = "Sınavlar"


class QuestionType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Question(models.Model):
    exam = models.ForeignKey(Exam, related_name='questions', on_delete=models.CASCADE)
    question_type = models.ForeignKey(QuestionType, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    image = models.ImageField(upload_to='question_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    marks = models.FloatField(default=1.0)
    def __str__(self):
        return f"{self.exam.title} - Question {self.id}"

class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    text = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        db_table = 'exams_answer'

    def __str__(self):
        return f"Answer for Question {self.question.id}"

class Submission(models.Model):
    exam = models.ForeignKey(Exam, related_name='submissions', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='submissions', on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(default=0)
    is_graded = models.BooleanField(default=False)
    is_submitted = models.BooleanField(default=False)
    attempts = models.IntegerField(default=3)  

    class Meta:
        ordering = ['-start_time']
        verbose_name = "Sınav Gönderimi"
        verbose_name_plural = "Sınav Gönderimleri"

    def is_time_expired(self):
        """Sınav süresinin dolup dolmadığını kontrol et"""
        if not self.start_time:
            return False
        
        duration = self.exam.duration
        end_time = self.start_time + timezone.timedelta(minutes=duration)
        return timezone.now() > end_time
    
    def get_remaining_time(self):
        """Kalan süreyi saniye cinsinden döndür"""
        if not self.start_time:
            return 0
            
        duration = self.exam.duration
        end_time = self.start_time + timezone.timedelta(minutes=duration)
        remaining = end_time - timezone.now()
        
        return max(0, int(remaining.total_seconds()))

class StudentAnswer(models.Model):
    submission = models.ForeignKey(Submission, related_name='student_answers', on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True)
    text_answer = models.TextField(null=True, blank=True)
    marks_obtained = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Öğrenci Cevabı"
        verbose_name_plural = "Öğrenci Cevapları"
    
class TempSubmission(models.Model):
    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name='temp_submission')
    temp_answers = models.JSONField(default=dict)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Geçici Gönderim"
        verbose_name_plural = "Geçici Gönderimleri"

