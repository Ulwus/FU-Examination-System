from django.core.management.base import BaseCommand
from django.utils import timezone
from exams.models import Submission

class Command(BaseCommand):
    help = 'Checks and finalizes exam submissions that have exceeded their time limit'

    def handle(self, *args, **options):
        active_submissions = Submission.objects.filter(end_time__isnull=True, is_submitted=False)
        for submission in active_submissions:
            if submission.is_time_up():
                self.finalize_submission(submission)

    def finalize_submission(self, submission):
        questions = submission.exam.questions.all()
        correct_answers = 0
        total_questions = questions.count()

        for question in questions:
            student_answer = submission.student_answers.filter(question=question).first()
            if student_answer and student_answer.answer.is_correct:
                correct_answers += 1

        score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        submission.score = round(score, 2)
        submission.end_time = timezone.now()
        submission.is_submitted = True
        submission.save()

        self.stdout.write(self.style.SUCCESS(f'Finalized submission for {submission.user.username} on exam {submission.exam.title}'))