from datetime import datetime, timedelta
import json
import time
from django.contrib import messages
from django.forms import formset_factory
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
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
        'completed_exams': completed_exams if request.user.is_student else None,
        'now': timezone.now()
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
    
    # Tamamlanmış sınavları kontrol et
    completed_exams = Submission.objects.filter(
        user=request.user, 
        end_time__isnull=False
    ).values_list('exam_id', flat=True)

    # Sınav başlamadıysa yönlendir
    if exam.start_time > timezone.now():
        messages.warning(request, 'Sınav henüz başlamamıştır!')
        return redirect('exam_list')

    # Sınav zaten tamamlandıysa sonuç sayfasına yönlendir 
    if exam.id in completed_exams:
        return redirect('exam_result', pk=exam.pk)

    # Yetki kontrolü
    if not request.user.is_student or not exam.is_active:
        return redirect('exam_list')

    # Submission oluştur veya mevcut olanı al
    submission, created = Submission.objects.get_or_create(
        exam=exam,
        user=request.user,
        defaults={
            'start_time': timezone.now(),
            'attempts': 4
        }
    )

    # Deneme hakkı kalmadıysa sınavı bitir
    if submission.attempts <= 0:
        finish_exam_task.delay(submission.id)
        messages.warning(request, 'Deneme haklarınız tükendiği için sınavınız otomatik olarak gönderildi.')
        time.sleep(2)
        return redirect('exam_result', pk=exam.pk)

    # Süre kontrolü
    if submission.is_time_expired():
        finish_exam_task.delay(submission.id)
        messages.warning(request, 'Sınav süresi dolduğu için sınavınız otomatik olarak gönderildi.')
        time.sleep(2)
        return redirect('exam_result', pk=exam.pk)

    # Yeni submission ise bitiş zamanı ayarla
    if created:
        finish_time = timezone.now() + timedelta(minutes=exam.duration)
        finish_exam_task.apply_async((submission.id,), eta=finish_time)

    # Soruları prefetch ile çek
    questions = exam.questions.all().prefetch_related('answers')

    # POST isteklerini işle
    if request.method == 'POST':
        # Sınav zaten gönderildiyse hata döndür
        if submission.is_submitted:
            return JsonResponse({'status': 'already_submitted'}, status=400)

        # Tab değiştirme kontrolü  
        if 'tab_change' in request.POST:
            submission.attempts -= 1
            submission.save()
            
            if submission.attempts <= 0:
                finish_exam_task.delay(submission.id)
                time.sleep(1)
                return JsonResponse({
                    'status': 'redirect',
                    'url': reverse('exam_result', kwargs={'pk': exam.pk})
                })
            
            return JsonResponse({
                'status': 'success',
                'attempts': submission.attempts
            })

        # Süre kontrolü yap
        if submission.is_time_expired():
            finish_exam_task.delay(submission.id)
            time.sleep(1)
            return JsonResponse({
                'status': 'redirect', 
                'url': reverse('exam_result', kwargs={'pk': exam.pk}),
                'message': 'Sınav süresi doldu!'
            })

        # Sınavı bitirme isteği
        if 'finish_exam' in request.POST:
            finish_exam_task.delay(submission.id)
            time.sleep(1)
            return redirect('exam_result', pk=exam.pk)

        # Geçici cevapları kaydetme
        if 'save_temp_answers' in request.POST:
            try:
                temp_answers = json.loads(request.POST.get('temp_answers', '{}'))
                
                # Önceki geçici cevapları sil
                TempSubmission.objects.filter(submission=submission).delete()
                
                # Yeni geçici cevapları kaydet
                temp_submission = TempSubmission(
                    submission=submission, 
                    temp_answers=temp_answers
                )
                temp_submission.save()
                
                return JsonResponse({
                    'status': 'success',
                    'remaining_time': submission.get_remaining_time()
                })
                
            except json.JSONDecodeError:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Geçersiz JSON formatı.'
                }, status=400)
                
            except ObjectDoesNotExist:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Gönderi bulunamadı.'
                }, status=404)
                
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=500)

    # Geçici cevapları getir
    temp_submission = TempSubmission.objects.filter(
        submission=submission
    ).order_by('-last_updated').first()
    
    answered_dict = temp_submission.temp_answers if temp_submission else {}

    # IDE için değişkenleri ayarla  
    predefined_vars = exam.predefined_vars if exam.predefined_vars else ''
    request.session['predefined_vars'] = predefined_vars

    context = {
        'exam': exam,
        'submission': submission,
        'questions': questions,
        'answered_dict': json.dumps(answered_dict),
        'csrf_token': get_token(request),
        'predefined_vars': predefined_vars,
        'remaining_time': submission.get_remaining_time()
    }

    return render(request, 'exams/take_exam.html', context)


@login_required
def exam_result(request, pk):
    try:
        exam = get_object_or_404(Exam, pk=pk)
        
        submission = Submission.objects.filter(
            exam=exam,
            user=request.user,
            is_submitted=True
        ).order_by('-end_time').first()
        
        if not submission:
            messages.error(request, 'Bu sınava ait sonucunuz bulunmamaktadır.')
            return redirect('exam_list')
            
        context = {
            'submission': submission,
            'exam': exam,
            'all_submissions': Submission.objects.filter(exam=exam).order_by('-end_time')
        }

        return render(request, 'exams/exam_result.html', context)
        
    except Exception as e:
        logger.error(f"Exam result error: {str(e)}")
        messages.error(request, 'Sınav sonuçları görüntülenirken bir hata oluştu.')
        return redirect('exam_list')
@login_required
def grade_exam(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    submissions = Submission.objects.filter(exam=exam)
    submission_count = submissions.count()

    if not request.user.is_instructor or exam.instructor != request.user:
        messages.error(request, 'Bu sınava erişim yetkiniz bulunmamaktadır.')
        return redirect('exam_list')

    if request.method == 'POST':
        if 'finish_exam' in request.POST:
            exam.is_active = False
            exam.save()

            for submission in submissions:
                if not submission.is_graded:
                    correct_answers = 0
                    total_questions = submission.exam.questions.count()
                    
                    for student_answer in submission.student_answers.all():
                        if student_answer.answer and student_answer.answer.is_correct:
                            correct_answers += 1
                    
                    if total_questions > 0:
                        score = (correct_answers / total_questions) * 100
                        submission.score = round(score, 2)
                    
                    submission.is_graded = True
                    submission.is_submitted = True
                    submission.end_time = timezone.now()
                    submission.save()

            messages.success(request, 'Sınav başarıyla tamamlandı ve notlandırıldı.')
            return redirect('exam_list')

    context = {
        'exam': exam,
        'submissions': submissions,
        'submission_count': submission_count
    }
    return render(request, 'exams/grade_exam.html', context)