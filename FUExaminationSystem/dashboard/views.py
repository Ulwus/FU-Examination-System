from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from competitions.models import Competition, CompetitionSubmission
from exams.models import Exam, Submission
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from django.db.models import Max, Avg, Sum, F

@login_required
def dashboard(request):
    user = request.user
    context = {
        'stats': get_user_stats(user),
        'competition_stats': get_competition_stats(user),
        'exam_stats': get_exam_stats(user),
        'activities': get_recent_activities(user),
        'upcoming_exams': get_upcoming_exams(),
        'leaderboard': get_leaderboard()
    }
    return render(request, 'dashboard/index.html', context)

def get_user_stats(user):
    all_competitions = Competition.objects.all()
    all_exams = Exam.objects.all()
    all_submissions = CompetitionSubmission.objects.all()
    all_exam_submissions = Submission.objects.all()

    return {
        'active_competitions': len([c for c in all_competitions if c.is_active]),
        'active_exams': len([e for e in all_exams if e.is_active]),
        'total_submissions': len([s for s in all_submissions if s.participant == user]),
        'completed_exams': len([s for s in all_exam_submissions if s.user == user and s.is_graded]),
        'upcoming_exams': len([e for e in all_exams if e.start_time > timezone.now()]),
    }

def get_competition_stats(user):
    all_submissions = CompetitionSubmission.objects.all()
    user_submissions = [s for s in all_submissions if s.participant == user and s.processing_status == 'completed']
    
    if not user_submissions:
        return {
            'best_score': 0,
            'avg_score': 0,
            'submission_dates': [],
            'f1_scores': [],
            'recent_submissions': []
        }
    
    sorted_submissions = sorted(user_submissions, key=lambda x: x.submitted_at, reverse=True)
    scores = [s.f1_score for s in user_submissions]
    
    return {
        'best_score': max(scores),
        'avg_score': sum(scores) / len(scores),
        'submission_dates': [s.submitted_at.strftime('%d/%m') for s in sorted_submissions],
        'f1_scores': [s.f1_score for s in sorted_submissions],
        'recent_submissions': sorted_submissions[:5]
    }

def get_exam_stats(user):
    all_submissions = Submission.objects.all()
    user_submissions = [s for s in all_submissions if s.user == user and s.is_graded]
    
    if not user_submissions:
        return {
            'avg_score': 0,
            'best_score': 0,
            'total_time': timezone.timedelta(0),
            'submission_dates': [],
            'scores': [],
            'recent_submissions': []
        }
    
    sorted_submissions = sorted(user_submissions, key=lambda x: x.end_time, reverse=True)
    scores = [s.score for s in user_submissions]
    total_time = sum(
        [(s.end_time - s.start_time) for s in user_submissions],
        timezone.timedelta(0)
    )
    
    return {
        'avg_score': sum(scores) / len(scores),
        'best_score': max(scores),
        'total_time': total_time,
        'submission_dates': [s.end_time.strftime('%d/%m') for s in sorted_submissions],
        'scores': [s.score for s in sorted_submissions],
        'recent_submissions': sorted_submissions[:5]
    }

def get_recent_activities(user):
    activities = []
    
    all_comp_subs = CompetitionSubmission.objects.all()
    user_comp_subs = sorted(
        [s for s in all_comp_subs if s.participant == user],
        key=lambda x: x.submitted_at,
        reverse=True
    )[:5]
    
    for sub in user_comp_subs:
        if sub.submitted_at:  
            activities.append({
                'type': 'competition',
                'title': f"{sub.competition.title} yarışmasına model gönderimi",
                'score': sub.f1_score,
                'date': sub.submitted_at
            })
    
    all_exam_subs = Submission.objects.all()
    user_exam_subs = sorted(
        [s for s in all_exam_subs if s.user == user and s.end_time is not None], 
        key=lambda x: x.end_time,
        reverse=True
    )[:5]
    
    for sub in user_exam_subs:
        activities.append({
            'type': 'exam',
            'title': f"{sub.exam.title} sınavı tamamlandı",
            'score': sub.score if sub.is_graded else None,
            'date': sub.end_time
        })
        
    return sorted(
        [a for a in activities if a['date'] is not None],  
        key=lambda x: x['date'],
        reverse=True
    )[:5]

def get_upcoming_exams():
    """Yaklaşan sınavları getir"""
    all_exams = Exam.objects.all()
    upcoming = [
        e for e in all_exams 
        if e.start_time > timezone.now()
    ]
    return sorted(upcoming, key=lambda x: x.start_time)[:5]

def get_leaderboard():
    """Global liderlik tablosunu getir"""
    all_submissions = CompetitionSubmission.objects.all()
    user_scores = {}
    
    for sub in all_submissions:
        username = sub.participant.username
        score = sub.f1_score
        competition_id = sub.competition.id
        submission_time = sub.submitted_at
        
        if score is None or score == 0:
            continue
            
        if username not in user_scores:
            user_scores[username] = {
                'username': username,
                'first_places': 0,
                'total_competitions': set(),
                'best_scores': {},
                'submission_times': {},
                'avg_score': 0
            }
        
        if competition_id not in user_scores[username]['best_scores']:
            user_scores[username]['best_scores'][competition_id] = score
            user_scores[username]['submission_times'][competition_id] = submission_time
        elif score > user_scores[username]['best_scores'][competition_id]:
            user_scores[username]['best_scores'][competition_id] = score
            user_scores[username]['submission_times'][competition_id] = submission_time
        elif score == user_scores[username]['best_scores'][competition_id]:
            if submission_time < user_scores[username]['submission_times'][competition_id]:
                user_scores[username]['best_scores'][competition_id] = score
                user_scores[username]['submission_times'][competition_id] = submission_time
            
        user_scores[username]['total_competitions'].add(competition_id)
    
    for competition_id in set(s.competition.id for s in all_submissions):
        comp_submissions = [(
            username, 
            data['best_scores'].get(competition_id, 0),
            data['submission_times'].get(competition_id)
        ) for username, data in user_scores.items() 
        if competition_id in data['best_scores']]
        
        if comp_submissions:
            winner = sorted(
                comp_submissions,
                key=lambda x: (-x[1], x[2])  
            )[0][0]
            
            if winner in user_scores:
                user_scores[winner]['first_places'] += 1
    
    for username, data in user_scores.items():
        total_score = sum(data['best_scores'].values())
        num_competitions = len(data['best_scores'])
        data['avg_score'] = total_score / num_competitions if num_competitions > 0 else 0
        data['total_competitions'] = len(data['total_competitions'])
    
    sorted_users = sorted(
        user_scores.values(),
        key=lambda x: (-x['first_places'], -x['avg_score'])
    )
    
    return sorted_users[:10]  