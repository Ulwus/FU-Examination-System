from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import FileResponse, HttpResponseForbidden
from django.utils import timezone

from .forms import CompetitionForm, ModelSubmissionForm, JoinCompetitionForm
from .models import Competition, CompetitionSubmission, CompetitionParticipant
from .utils import generate_pin_code, evaluate_model

import joblib
import pandas as pd
from io import BytesIO
from sklearn.metrics import f1_score, accuracy_score, precision_score, recall_score

class InstructorRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_instructor

class CompetitionListView(LoginRequiredMixin, ListView):
    model = Competition
    template_name = 'competitions/list.html'
    context_object_name = 'competitions'

class CompetitionDetailView(LoginRequiredMixin, DetailView):
    model = Competition
    template_name = 'competitions/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        competition = self.object
        

        try:
            context['leaderboard'] = competition.get_leaderboard()
        except Exception as e:
            print("Leaderboard yüklenirken hata: ", e)
            context['leaderboard'] = []

        if self.request.user.is_authenticated:
            try:
                context['is_participant'] = competition.is_participant(self.request.user)

                today = timezone.now().date()
                submissions = CompetitionSubmission.objects.filter(
                    competition=competition,
                    participant=self.request.user
                )
                today_submissions = sum(1 for submission in submissions if submission.submitted_at.date() == today)
                remaining_submissions = competition.max_submissions_per_day - today_submissions
                context['remaining_submissions'] = remaining_submissions

                best_submission = submissions.order_by('-f1_score').first()
                context['best_submission'] = best_submission
                

            except Exception as e:
                    print("Katılım durumu kontrol edilirken hata: ", e)
                    context['is_participant'] = False

            if best_submission:
                    context['confusion_matrix'] = {
                        'true_positives': best_submission.true_positives,
                        'false_positives': best_submission.false_positives,
                        'false_negatives': best_submission.false_negatives, 
                        'true_negatives': best_submission.true_negatives
                    }
        return context


class CreateCompetitionView(LoginRequiredMixin, InstructorRequiredMixin, CreateView):
    model = Competition
    form_class = CompetitionForm
    template_name = 'competitions/create.html'
    success_url = reverse_lazy('competition_list')

    def form_valid(self, form):
        form.instance.instructor = self.request.user
        form.instance.pin_code = generate_pin_code()

        try:
            form.clean()
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)

        messages.success(self.request, f'Yarışma başarıyla oluşturuldu. PIN: {form.instance.pin_code}')
        return super().form_valid(form)

@login_required
def download_training_dataset(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    if not competition.is_participant(request.user):
        return HttpResponseForbidden('Bu yarışmanın dataseti için yetkiniz yok.')

    if not competition.training_dataset:
        messages.error(request, 'Training dataset bulunamadı.')
        return redirect('competition_detail', pk=competition_id)

    try:
        response = FileResponse(
            competition.training_dataset.open('rb'),
            as_attachment=True,
            filename=f'training_dataset_{competition.id}.csv'
        )
        return response
    except Exception as e:
        messages.error(request, f'Dataset indirme hatası: {str(e)}')
        return redirect('competition_detail', pk=competition_id)

@login_required
def submit_model(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    if not competition.is_participant(request.user):
        messages.error(request, 'Bu yarışmaya katılmamışsınız.')
        return redirect('competition_detail', pk=competition_id)

    if request.method == 'POST':
        form = ModelSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            model_file = form.cleaned_data['model_file']

            today = timezone.now()
            today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
            today_end = today_start + timedelta(days=1)

            today_submissions = CompetitionSubmission.objects.filter(
                competition=competition,
                participant=request.user,
                submitted_at__range=(today_start, today_end)
            ).count()

            if today_submissions >= competition.max_submissions_per_day:
                messages.error(request, 'Günlük maksimum deneme sayısına ulaştınız.')
                return redirect('competition_detail', pk=competition_id)

            try:
                scores = evaluate_model(model_file, competition)
                submission = CompetitionSubmission.objects.create(
                    competition=competition,
                    participant=request.user,
                    model_file=model_file,
                    f1_score=scores['f1_score'],
                    accuracy=scores['accuracy'],
                    precision=scores['precision'],
                    recall=scores['recall'],
                    true_positives=scores['confusion_matrix']['true_positives'],
                    false_positives=scores['confusion_matrix']['false_positives'],
                    false_negatives=scores['confusion_matrix']['false_negatives'],
                    true_negatives=scores['confusion_matrix']['true_negatives'],
                    processing_status='completed'
                )
                messages.success(request, f'Modeliniz başarıyla değerlendirildi. F1 Skorunuz: {scores["f1_score"]:.4f}')
                return redirect('competition_detail', pk=competition_id)
            except Exception as e:
                CompetitionSubmission.objects.create(
                    competition=competition,
                    participant=request.user,
                    model_file=model_file,
                    processing_status='failed',
                    error_message=str(e)
                )
                messages.error(request, f'Model değerlendirme hatası: {str(e)}')
    else:
        form = ModelSubmissionForm()

    return render(request, 'competitions/submit_model.html', {
        'form': form,
        'competition': competition
    })

@login_required
def join_competition(request):
    competitions = Competition.objects.all()
    
    if request.method == 'POST':
        form = JoinCompetitionForm(request.POST)
        if form.is_valid():
            pin_code = form.cleaned_data['pin_code']
            
            matching_competition = next(
                (comp for comp in competitions if comp.pin_code == pin_code),
                None
            )
            
            if matching_competition:
                participant, created = CompetitionParticipant.objects.get_or_create(
                    competition=matching_competition,
                    student=request.user
                )
                
                if created:
                    messages.success(request, 'Yarışmaya başarıyla katıldınız.')
                else:
                    messages.info(request, 'Bu yarışmaya zaten katılmışsınız.')
                    
                return redirect('competition_detail', pk=matching_competition.id)
            else:
                messages.error(request, 'Geçersiz PIN kodu.')
    else:
        form = JoinCompetitionForm()

    return render(request, 'competitions/join_competition.html', {
        'form': form,
        'active_competitions_count': competitions.count()
    })