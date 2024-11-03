from django.db import models
from django.db.models import Max

from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

class Competition(models.Model):
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_competitions'
    )
    pin_code = models.CharField(
        max_length=6, 
        unique=True,
        help_text="Yarışmaya katılım için 6 haneli PIN kodu"
    )
    title = models.CharField(
        max_length=255,
        help_text="Yarışma başlığı"
    )
    description = models.TextField(
        help_text="Yarışma açıklaması ve kuralları"
    )
    created_at = models.DateTimeField(auto_now_add=True) 
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, help_text="Yarışmanın aktif durumu")
    max_submissions_per_day = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="Kullanıcı başına günlük maksimum deneme sayısı"
    )
    training_dataset = models.FileField(
        upload_to='competition_datasets/training/',
        help_text="Öğrencilerin kullanacağı eğitim dataseti",
        null=True,
        blank=True
    )
    test_dataset = models.FileField(
        upload_to='competition_datasets/test/',
        help_text="Değerlendirme için kullanılacak test dataseti",
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Yarışma"
        verbose_name_plural = "Yarışmalar"

    def __str__(self):
        return f"{self.title} (PIN: {self.pin_code})"

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("Bitiş tarihi başlangıç tarihinden sonra olmalıdır.")

    def is_active_now(self):
        now = timezone.now()
        return (
            self.is_active and
            self.start_date <= now <= self.end_date
        )

    def get_leaderboard(self):
        submissions = CompetitionSubmission.objects.filter(
            competition=self,
            processing_status='completed'
        ).order_by('-f1_score', 'submitted_at')  
        
        best_by_user = {}
        for sub in submissions:
            user_id = sub.participant.id
            if user_id not in best_by_user:
                best_by_user[user_id] = sub
            elif sub.f1_score == best_by_user[user_id].f1_score and sub.submitted_at < best_by_user[user_id].submitted_at:
                best_by_user[user_id] = sub
        
        best_submissions = sorted(
            best_by_user.values(),
            key=lambda x: (-x.f1_score, x.submitted_at) 
        )
        
        return {
            'submissions': best_submissions[:10],  
            'best_scores': {
                'f1_score': best_submissions[0] if best_submissions else None,
                'accuracy': max(best_submissions, key=lambda x: x.accuracy) if best_submissions else None,
                'precision': max(best_submissions, key=lambda x: x.precision) if best_submissions else None,
                'recall': max(best_submissions, key=lambda x: x.recall) if best_submissions else None
            }
        }

    def is_participant(self, user):
        return any(participant.student == user for participant in self.competitionparticipant_set.all())

    def get_participant_count(self):
        return self.competitionparticipant_set.count()

class CompetitionParticipant(models.Model):
    competition = models.ForeignKey(
        Competition, 
        on_delete=models.CASCADE
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='competition_participations'
    )
    joined_at = models.DateTimeField(auto_now_add=True) 
    last_download = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['competition', 'student']
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.student.username} - {self.competition.title}"

    def get_submission_count(self):
        return self.student.competition_submissions.filter(
            competition=self.competition
        ).count()

    def get_best_submission(self):
        return self.student.competition_submissions.filter(
            competition=self.competition
        ).order_by('-f1_score').first()

class CompetitionSubmission(models.Model):
    competition = models.ForeignKey(
        Competition, 
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='competition_submissions'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)  

    model_file = models.FileField(
        upload_to='competition_models/',
        null=True,
        blank=True
    )
    f1_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        default=0.0
    )
    accuracy = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        default=0.0
    )
    precision = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        default=0.0
    )
    recall = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        null=True,
        blank=True,
        default=0.0
    )
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'İşleniyor'),
            ('completed', 'Tamamlandı'),
            ('failed', 'Başarısız')
        ],
        default='pending'
    )
    error_message = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = "Yarışma Gönderimi"
        verbose_name_plural = "Yarışma Gönderimleri"

    def __str__(self):
        return f"{self.participant.username} - {self.competition.title} - F1: {self.f1_score:.4f if self.f1_score else 0.0}"

    @property
    def rank(self):
        better_submissions = CompetitionSubmission.objects.filter(
            competition=self.competition,
            f1_score__gt=self.f1_score
        ).count()
        return better_submissions + 1