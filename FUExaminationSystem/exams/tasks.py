from datetime import datetime
from celery import shared_task
from django.utils import timezone
from django.shortcuts import get_object_or_404
import pytz

from users.models import User
from .models import Submission, Exam, TempSubmission, Question, Answer, StudentAnswer
import logging

logger = logging.getLogger(__name__)

@shared_task
def finish_exam_task(submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    
    if submission.end_time is not None and submission.is_submitted:
        logger.info(f"Exam already finished for submission {submission_id}")
        return
    
    exam = submission.exam

    temp_submission = TempSubmission.objects.filter(submission=submission).order_by('-last_updated').first()
    if temp_submission:
        correct_answers = 0
        total_questions = exam.questions.count()
        
        for question_id, answer_id in temp_submission.temp_answers.items():
            try:
                question = get_object_or_404(Question, id=question_id)
                answer = get_object_or_404(Answer, id=answer_id)
                student_answer, created = StudentAnswer.objects.update_or_create(
                    submission=submission,
                    question=question,
                    defaults={'answer': answer}
                )
                if student_answer.answer.is_correct:
                    correct_answers += 1
            except:
                continue

        if temp_submission.id:
            temp_submission.delete()

        score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        submission.score = round(score, 2)
        submission.end_time = timezone.now()
        submission.is_submitted = True
        submission.save()

        logger.info(f"Exam finished for submission {submission_id}")
    else:
        logger.warning(f"No temp submission found for submission {submission_id}")


def process_submission(submission):
    temp_submission = TempSubmission.objects.filter(submission=submission).order_by('-last_updated').first()
    
    if temp_submission:
        correct_answers = 0
        total_questions = submission.exam.questions.count()
        
        for question_id, answer_id in temp_submission.temp_answers.items():
            try:
                question = get_object_or_404(Question, id=question_id)
                answer = get_object_or_404(Answer, id=answer_id)
                student_answer, created = StudentAnswer.objects.update_or_create(
                    submission=submission,
                    question=question,
                    defaults={'answer': answer}
                )
                if student_answer.answer.is_correct:
                    correct_answers += 1
            except:
                continue

        if temp_submission.id:
            temp_submission.delete()
    else:
        correct_answers = 0
        total_questions = submission.exam.questions.count()

    score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    submission.score = round(score, 2)
    submission.end_time = timezone.now()
    submission.is_submitted = True
    submission.save()

    logger.info(f"Exam finished for submission {submission.id}")



@shared_task
def check_and_finish_exams():
    try:
        current_time_utc = timezone.now()
        logger.info(f"Current time in UTC: {current_time_utc.isoformat()}")

        active_exams = Exam.objects.all()

        for exam in active_exams:
            if (exam.end_time < current_time_utc and exam.is_active==True):
                exam.is_active = False
                exam.save()

                students = User.objects.all()
                for student in students:
                    if student.is_student:
                        Submission.objects.create(exam=exam, user=student, start_time=timezone.now())
                logger.info(f"Deactivated exam {exam.id}")

                submissions = Submission.objects.all()

                for submission in submissions:
                    if submission.exam_id == exam.id and not submission.is_submitted:
                        logger.info(f"Finished exam for submission {submission.id}")
                        finish_exam_task(submission.id)

                        submission.is_graded=True
                        submission.is_submitted=True
                        submission.end_time = timezone.now()

                        submission.save()

        logger.info("Completed check for exams that need to be finished.")
    except Exception as e:
        logger.error(f"Error in check_and_finish_exams task: {str(e)}")
