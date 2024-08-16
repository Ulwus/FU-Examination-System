from django.core.management.base import BaseCommand
from django.utils import timezone
from exams.models import Submission, TempSubmission, StudentAnswer, Question, Answer

class Command(BaseCommand):
    help = 'Checks and finalizes exam submissions that have exceeded their time limit'

    def handle(self, *args, **options):
        now = timezone.now()
        active_submissions = Submission.objects.filter(end_time__isnull=True, is_submitted=False)
        for submission in active_submissions:
            exam_end_time = submission.start_time + timezone.timedelta(minutes=submission.exam.duration)
            if now > exam_end_time:
                self.finalize_submission(submission)

        pending_submissions = Submission.objects.filter(end_time__isnull=True)
        for submission in pending_submissions:
            exam_end_time = submission.start_time + timezone.timedelta(minutes=submission.exam.duration)
            if submission.start_time is None or now >= exam_end_time:
                self.finalize_submission(submission, is_auto=True)

    def finalize_submission(self, submission, is_auto=False):
        questions = submission.exam.questions.all()
        total_questions = questions.count()
        correct_answers = 0

        if is_auto:
            temp_submission = TempSubmission.objects.filter(submission=submission).order_by('-last_updated').first()
            temp_answers = temp_submission.temp_answers if temp_submission else {}

            for question in questions:
                answer_id = temp_answers.get(str(question.id))
                if answer_id:
                    answer = Answer.objects.get(id=answer_id)
                    student_answer, created = StudentAnswer.objects.update_or_create(
                        submission=submission,
                        question=question,
                        defaults={'answer': answer}
                    )
                    if student_answer.answer.is_correct:
                        correct_answers += 1
        else:
            for question in questions:
                student_answer = submission.student_answers.filter(question=question).first()
                if student_answer and student_answer.answer.is_correct:
                    correct_answers += 1

        score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        submission.score = round(score, 2)
        submission.end_time = timezone.now()
        submission.is_submitted = True
        submission.save()

        self.stdout.write(self.style.SUCCESS(
            f'Finalized submission for {submission.user.username} on exam {submission.exam.title}'
        ))
