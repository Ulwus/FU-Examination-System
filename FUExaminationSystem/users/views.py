from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.views import PasswordResetView
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from .forms import CustomUserCreationForm, EditProfileForm  
from .models import User


def logout_view(request):
    logout(request)
    return redirect('login') 

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('exam_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def user_profile(request):
    return render(request, 'users/user_profile.html', {'user': request.user})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('exam_list')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset.html'
    email_template_name = 'registration/password_reset_email.html'



from exams.models import Submission
from competitions.models import CompetitionSubmission, CompetitionParticipant
from django.db.models import Avg, Max, Count

def get_recent_activities(user, days=30):
    thirty_days_ago = timezone.now() - timedelta(days=days)
    activities = []
    
    all_exam_submissions = Submission.objects.all()
    all_competition_submissions = CompetitionSubmission.objects.all()
    
    exam_activities = [
        submission for submission in all_exam_submissions
        if submission.user == user and submission.end_time >= thirty_days_ago
    ]
    exam_activities = sorted(exam_activities, key=lambda x: x.end_time, reverse=True)[:5]

    competition_activities = [
        submission for submission in all_competition_submissions
        if submission.participant == user and submission.submitted_at >= thirty_days_ago
    ]
    competition_activities = sorted(competition_activities, key=lambda x: x.submitted_at, reverse=True)[:5]
    
    for submission in exam_activities:
        activities.append({
            'type': 'exam',
            'date': submission.end_time,
            'title': submission.exam.title,
            'score': submission.score if submission.is_graded else None,
            'status': 'Tamamlandı' if submission.is_graded else 'Değerlendiriliyor',
            'icon': 'fas fa-book',
            'url': f'/exams/result/{submission.exam.id}'
        })
    
    for submission in competition_activities:
        activities.append({
            'type': 'competition',
            'date': submission.submitted_at,
            'title': submission.competition.title,
            'score': submission.f1_score,
            'status': submission.get_processing_status_display(),
            'icon': 'fas fa-trophy',
            'url': f'/competitions/{submission.competition.id}/leaderboard'
        })
        
    return sorted(activities, key=lambda x: x['date'], reverse=True)[:3]


@login_required  
def user_profile(request):
    user = request.user
    
    all_submissions = Submission.objects.all()
    all_competition_participants = CompetitionParticipant.objects.all()
    all_competition_submissions = CompetitionSubmission.objects.all()

    user_exam_submissions = [s for s in all_submissions if s.user == user and s.is_graded]
    
    exam_stats = {
        'total_exams': len(user_exam_submissions),
        'avg_score': sum(s.score for s in user_exam_submissions) / len(user_exam_submissions) if user_exam_submissions else 0,
        'highest_score': max((s.score for s in user_exam_submissions), default=0)
    }

    user_participations = [p for p in all_competition_participants if p.student == user]
    user_comp_submissions = [s for s in all_competition_submissions if s.participant == user]
    
    competition_stats = {
        'participation_count': len(user_participations),
        'submission_count': len(user_comp_submissions)
    }

    first_places = 0
    for participation in user_participations:
        comp_submissions = [s for s in all_competition_submissions 
                        if s.competition == participation.competition 
                        and s.processing_status == 'completed' 
                        and s.f1_score is not None]
        
        if comp_submissions:
            best_by_user = {}
            for sub in comp_submissions:
                user_id = sub.participant.id
                if user_id not in best_by_user:
                    best_by_user[user_id] = sub
                elif sub.f1_score > best_by_user[user_id].f1_score:
                    best_by_user[user_id] = sub
                elif sub.f1_score == best_by_user[user_id].f1_score and sub.submitted_at < best_by_user[user_id].submitted_at:
                    best_by_user[user_id] = sub

            sorted_submissions = sorted(
                best_by_user.values(),
                key=lambda x: (-x.f1_score, x.submitted_at)
            )
            
            if sorted_submissions[0].participant == user:
                first_places += 1

    completed_submissions = [s for s in user_comp_submissions if s.processing_status == 'completed']
    avg_f1_score = sum(s.f1_score or 0 for s in completed_submissions) / len(completed_submissions) if completed_submissions else 0

    best_rank = float('inf')
    for submission in completed_submissions:
        better_submissions = len([s for s in all_competition_submissions 
                                if s.competition == submission.competition 
                                and s.f1_score and s.f1_score > submission.f1_score])
        current_rank = better_submissions + 1
        best_rank = min(best_rank, current_rank)

    context = {
        'activities': get_recent_activities(user),
        'exam_stats': exam_stats,
        'competition_stats': {
            'participations': competition_stats['participation_count'],
            'submissions': competition_stats['submission_count'],
            'first_places': first_places,
            'avg_f1_score': avg_f1_score,
            'best_rank': best_rank if best_rank != float('inf') else '-'
        }
    }
    
    return render(request, 'users/user_profile.html', context)

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = EditProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('user_profile')  
    else:
        form = EditProfileForm(instance=request.user)

    return render(request, 'users/edit_profile.html', {'form': form})