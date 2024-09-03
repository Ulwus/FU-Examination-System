from datetime import datetime, timedelta
import json
from django.contrib import messages
from django.forms import formset_factory
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Answer, Exam, Submission, StudentAnswer, TempSubmission, Question
from .forms import ExamForm, QuestionForm, AnswerForm
from django.core.exceptions import ObjectDoesNotExist
import logging
from django.middleware.csrf import get_token
from django.db.models import Avg

from .tasks import finish_exam_task

logger = logging.getLogger(__name__)

@login_required
def exam_list(request):
    exams = Exam.objects.all().order_by('-is_active', '-end_time')
    completed_exams = []
    active_submissions = []

    if request.user.is_student:
        submissions = Submission.objects.filter(user=request.user)
        for submission in submissions:
            if submission.end_time is not None and submission.is_submitted:
                completed_exams.append(submission.exam_id)
            elif not submission.is_submitted and submission.end_time is None:
                active_submissions.append(submission.exam_id)
    elif request.user.is_instructor:
        exams = [exam for exam in exams if exam.instructor == request.user]
        active_submissions = None
    else:
        active_submissions = None

    context = {
        'exams': exams,
        'active_submissions': active_submissions,
        'completed_exams': completed_exams if request.user.is_student else None
    }
    return render(request, 'exams/exam_list.html', context)

@login_required
def exam_detail(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if request.user.is_student and not exam.is_active:
        return redirect('exam_list')
    return render(request, 'exams/exam_detail.html', {'exam': exam})

@login_required
def create_exam(request):
    if request.user.is_student:
        return redirect('exam_list')

    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.instructor = request.user
            exam.save()

            predefined_vars = request.POST.get('predefined_vars', '')
            exam.predefined_vars = predefined_vars
            exam.save()

            return redirect('create_exam_questions', pk=exam.pk)
    else:
        form = ExamForm()

    return render(request, 'exams/create_exam.html', {'form': form})

@login_required
def create_exam_questions(request, pk):
    exam = get_object_or_404(Exam, pk=pk)

    QuestionFormSet = formset_factory(QuestionForm, extra=exam.total_marks)
    AnswerFormSet = formset_factory(AnswerForm, extra=4)

    if request.method == 'POST':
        question_formset = QuestionFormSet(request.POST, request.FILES, prefix='questions')
        answer_formsets = [AnswerFormSet(request.POST, prefix=f'answers_{i}') for i in range(exam.total_marks)]

        if question_formset.is_valid() and all(formset.is_valid() for formset in answer_formsets):
            try:
                for index, question_form in enumerate(question_formset):
                    if question_form.cleaned_data:
                        question = question_form.save(commit=False)
                        question.exam = exam
                        question.image = question_form.cleaned_data.get('image')
                        question.save()

                        answer_formset = answer_formsets[index]
                        for answer_form in answer_formset:
                            if answer_form.cleaned_data:
                                answer = answer_form.save(commit=False)
                                answer.question = question
                                answer.save()

                exam.is_active = True
                exam.save()
                messages.success(request, 'Exam questions and answers saved successfully.')
                return redirect('exam_list')
            except Exception as e:
                messages.error(request, f'An error occurred while saving: {str(e)}')
        else:
            for i, question_form in enumerate(question_formset):
                for field, errors in question_form.errors.items():
                    for error in errors:
                        messages.error(request, f'Question {i+1} - {field}: {error}')
                
                answer_formset = answer_formsets[i]
                for j, answer_form in enumerate(answer_formset):
                    for field, errors in answer_form.errors.items():
                        for error in errors:
                            messages.error(request, f'Question {i+1}, Answer {j+1} - {field}: {error}')
            
            messages.error(request, 'There were errors in your form. Please check the error messages above and try again.')
    else:
        question_formset = QuestionFormSet(prefix='questions')
        answer_formsets = [AnswerFormSet(prefix=f'answers_{i}') for i in range(exam.total_marks)]

    return render(request, 'exams/create_exam_questions.html', {
        'exam': exam,
        'question_formset': question_formset,
        'answer_formsets': answer_formsets,
    })

@login_required
def take_exam(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    completed_exams = Submission.objects.filter(user=request.user, end_time__isnull=False).values_list('exam_id', flat=True)

    if exam.id in completed_exams:
        submission = Submission.objects.get(exam=exam, user=request.user)
        return redirect('exam_result', pk=submission.pk)

    if not request.user.is_student or not exam.is_active:
        return redirect('exam_list')

    submission, created = Submission.objects.get_or_create(
        exam=exam,
        user=request.user,
        defaults={'start_time': timezone.now()}
    )

    if created:
        finish_time = timezone.now() + timedelta(minutes=exam.duration)
        finish_exam_task.apply_async((submission.id,), eta=finish_time)

    questions = exam.questions.all().prefetch_related('answers')
    total_questions = questions.count()

    if request.method == 'POST':
        if submission.is_submitted:
            return JsonResponse({'status': 'already_submitted'}, status=400)

        if 'save_temp_answers' in request.POST:
            try:
                temp_answers = json.loads(request.POST.get('temp_answers', '{}'))

                TempSubmission.objects.filter(submission=submission).delete()

                temp_submission = TempSubmission(submission=submission, temp_answers=temp_answers)
                temp_submission.save()

                return JsonResponse({'status': 'success'})
            except json.JSONDecodeError as e:
                return JsonResponse({'status': 'error', 'message': 'Invalid JSON format.'}, status=400)
            except ObjectDoesNotExist as e:
                return JsonResponse({'status': 'error', 'message': 'Submission not found.'}, status=404)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': 'An unexpected error occurred.'}, status=500)

        if timezone.now() > submission.start_time + timezone.timedelta(minutes=exam.duration) or 'finish_exam' in request.POST:
            finish_exam_task.delay(submission.id)
            return redirect('exam_result', pk=submission.pk)

    temp_submission = TempSubmission.objects.filter(submission=submission).order_by('-last_updated').first()
    answered_dict = temp_submission.temp_answers if temp_submission else {}
    predefined_vars = exam.predefined_vars if exam.predefined_vars else ''
    request.session['predefined_vars'] = predefined_vars



    return render(request, 'exams/take_exam.html', {
        'exam': exam,
        'submission': submission,
        'questions': questions,
        'answered_dict': json.dumps(answered_dict),
        'csrf_token': get_token(request),
        'predefined_vars': predefined_vars,


    })




@login_required
def student_dashboard(request):
    student = request.user
    submissions = Submission.objects.filter(user=student)

    total_exams = submissions.count()
    completed_exams = 0
    graded_submissions = []
    recent_exams = []
    exam_performance = []
    upcoming_exams = 0

    for submission in submissions:
        if submission.is_submitted:
            completed_exams += 1
        if submission.is_graded:
            graded_submissions.append(submission)
        recent_exams.append(submission)

    upcoming_exams_list = []
    all_exams = Exam.objects.all()
    for exam in all_exams:
        if exam.start_time > timezone.now() and exam.is_active:
            upcoming_exams_list.append(exam)

    upcoming_exams = len(upcoming_exams_list)

    total_score = 0
    for submission in graded_submissions:
        total_score += submission.score
        exam_performance.append({
            'name': submission.exam.title,
            'score': submission.score
        })
    
    average_score = round(total_score / len(graded_submissions), 2) if graded_submissions else 0

    recent_exams = sorted(recent_exams, key=lambda x: x.exam.start_time, reverse=True)[:5]

    context = {
        'studentData': {
            'name': student.get_full_name(),
            'totalExams': total_exams,
            'completedExams': completed_exams,
            'upcomingExams': upcoming_exams,
            'averageScore': average_score,
            'recentExams': [
                {
                    'title': submission.exam.title,
                    'date': submission.exam.start_time.strftime('%d %b %Y'),
                    'duration': submission.exam.duration,
                    'status': 'completed' if submission.is_submitted else 'incomplete'
                } for submission in recent_exams
            ],
            'examPerformance': exam_performance
        }
    }

    return render(request, 'users/student_dashboard.html', context)


@login_required
def exam_result(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    if submission.user != request.user and not request.user.is_instructor:
        return redirect('exam_list')
    return render(request, 'exams/exam_result.html', {'submission': submission})

@login_required
def grade_exam(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    exam = submission.exam
    submission_count = Submission.objects.filter(exam=exam).count()

    if not request.user.is_instructor or submission.exam.instructor != request.user:
        return redirect('exam_list')

    if request.method == 'POST':
        if 'finish_exam' in request.POST:
            exam = submission.exam
            exam.is_active = False
            exam.save()

            submissions = Submission.objects.filter(exam=exam)
            for sub in submissions:
                sub.is_graded = True
                sub.save()

            messages.success(request, 'Exam has been marked as complete.')
            return redirect('exam_list')

    return render(request, 'exams/grade_exam.html', {'submission': submission, 'submission_count': submission_count})