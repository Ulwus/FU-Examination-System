from datetime import datetime
from django.contrib import messages
from django.forms import formset_factory
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Answer, Exam, Submission, StudentAnswer
from .forms import ExamForm, QuestionForm, AnswerForm

@login_required
def exam_list(request):
    if request.user.is_student:
        
        exams = Exam.objects.all().order_by('-is_active', '-start_time')
        completed_exams = Submission.objects.filter(user=request.user, end_time__isnull=False).values_list('exam_id', flat=True)
    elif request.user.is_instructor:
        exams = Exam.objects.filter(instructor=request.user)
    else:
        exams = Exam.objects.all()

    context = {
        'exams': exams,
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
        question_formset = QuestionFormSet(request.POST, prefix='questions')
        answer_formsets = [AnswerFormSet(request.POST, prefix=f'answers_{i}') for i in range(exam.total_marks)]

        if question_formset.is_valid() and all(formset.is_valid() for formset in answer_formsets):
            try:
                for index, question_form in enumerate(question_formset):
                    if question_form.cleaned_data:
                        question = question_form.save(commit=False)
                        question.exam = exam
                        question.save()

                        answer_formset = answer_formsets[index]
                        for answer_form in answer_formset:
                            if answer_form.cleaned_data:
                                answer = answer_form.save(commit=False)
                                answer.question = question
                                answer.save()

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


from django.db.models import Sum

@login_required
def take_exam(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    completed_exams = Submission.objects.filter(user=request.user, end_time__isnull=False).values_list('exam_id', flat=True)

    if exam.id in completed_exams:
        return redirect('exam_list')

    if not request.user.is_student or not exam.is_active:
        return redirect('exam_list')
    

    submission, created = Submission.objects.get_or_create(
        exam=exam,
        user=request.user,
        defaults={'start_time': timezone.now()}
    )

    questions = exam.questions.all().prefetch_related('answers')
    total_questions = questions.count()

    if request.method == 'POST':
        correct_answers = 0
        for question in questions:
            answer_id = request.POST.get(f'question_{question.id}')
            if answer_id:
                answer = get_object_or_404(Answer, id=answer_id)
                student_answer, created = StudentAnswer.objects.update_or_create(
                    submission=submission,
                    question=question,
                    defaults={'answer': answer}
                )
                
                if answer.is_correct:
                    correct_answers += 1

        score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        submission.score = round(score, 2)  
        submission.end_time = timezone.now()
        submission.save()
        
        return redirect('exam_result', pk=submission.pk)

    return render(request, 'exams/take_exam.html', {
        'exam': exam,
        'submission': submission,
        'questions': questions
    })

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
