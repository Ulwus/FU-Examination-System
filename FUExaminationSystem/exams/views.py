from django.forms import formset_factory
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Answer, Exam, Submission, StudentAnswer
from .forms import ExamForm, QuestionForm, AnswerForm

@login_required
def exam_list(request):
    
    if request.user.is_student:
            exams = Exam.objects.filter(is_active=True)
    elif request.user.is_instructor:
            exams = Exam.objects.filter(instructor=request.user)
    else:
            exams = Exam.objects.all()     
        
     

    
    return render(request, 'exams/exam_list.html', {'exams': exams})

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
    
    if request.method == 'POST':
        question_formset = QuestionFormSet(request.POST, prefix='questions')
        
        if question_formset.is_valid():
            questions = question_formset.save(commit=False)
            for question in questions:
                question.exam = exam
                question.save()
                
                # Create Answer formset for each question
                answer_formset = formset_factory(AnswerForm, extra=4)(request.POST, prefix=f'answers_{question.id}')
                
                if answer_formset.is_valid():
                    answers = answer_formset.save(commit=False)
                    for answer in answers:
                        answer.question = question
                        answer.save()

            return redirect('exam_list')

    else:
        question_formset = QuestionFormSet(prefix='questions')

    return render(request, 'exams/create_exam_questions.html', {
        'exam': exam,
        'question_formset': question_formset,
    })
@login_required
def take_exam(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if not request.user.is_student or not exam.is_active:
        return redirect('exam_list')

    submission, created = Submission.objects.get_or_create(
        exam=exam,
        user=request.user,
        defaults={'start_time': timezone.now()}
    )

    if request.method == 'POST':
        for question in exam.questions.all():
            answer_id = request.POST.get(f'question_{question.id}')
            text_answer = request.POST.get(f'text_answer_{question.id}')
            if answer_id:
                answer = get_object_or_404(Answer, id=answer_id)
                StudentAnswer.objects.update_or_create(
                    submission=submission,
                    question=question,
                    defaults={'answer': answer}
                )
            elif text_answer:
                StudentAnswer.objects.update_or_create(
                    submission=submission,
                    question=question,
                    defaults={'text_answer': text_answer}
                )

        submission.end_time = timezone.now()
        submission.save()
        return redirect('exam_result', pk=submission.pk)

    return render(request, 'exams/take_exam.html', {'exam': exam, 'submission': submission})

@login_required
def exam_result(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    if submission.user != request.user and not request.user.is_instructor:
        return redirect('exam_list')
    return render(request, 'exams/exam_result.html', {'submission': submission})

@login_required
def grade_exam(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    if not request.user.is_instructor or submission.exam.course.instructor != request.user:
        return redirect('exam_list')
    
    if request.method == 'POST':
        total_score = 0
        for answer in submission.student_answers.all():
            marks = float(request.POST.get(f'marks_{answer.id}', 0))
            answer.marks_obtained = marks
            answer.save()
            total_score += marks
        
        submission.score = total_score
        submission.is_graded = True
        submission.save()
        return redirect('exam_result', pk=submission.pk)
    
    return render(request, 'exams/grade_exam.html', {'submission': submission})
