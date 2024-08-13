from django.db import models
from users.models import User



class Exam(models.Model):
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_exams')
    title = models.CharField(max_length=255)
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration = models.IntegerField(help_text="Sınav süresi dakika cinsinden")
    total_marks = models.PositiveIntegerField()
    passing_marks = models.PositiveIntegerField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.course.code} - {self.title}"

class QuestionType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Question(models.Model):
    exam = models.ForeignKey(Exam, related_name='questions', on_delete=models.CASCADE)
    question_type = models.ForeignKey(QuestionType, on_delete=models.SET_NULL, null=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    score = models.FloatField(null=True, blank=True)
    is_graded = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.exam.title}"

class StudentAnswer(models.Model):
    submission = models.ForeignKey(Submission, related_name='student_answers', on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True)
    text_answer = models.TextField(null=True, blank=True)
    marks_obtained = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Answer by {self.submission.user.username} for Question {self.question.id}"