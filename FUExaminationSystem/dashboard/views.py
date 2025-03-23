from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from competitions.models import Competition, CompetitionSubmission
from exams.models import Exam, Submission
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from django.db.models import Max, Avg, Sum, F
from django.views.decorators.cache import cache_page



@login_required
def dashboard(request):
    """Ana dashboard view'ı"""
    user = request.user
    
    # Tüm verileri tek seferde çek
    cached_data = {
        'competitions': Competition.objects.all(),
        'exams': Exam.objects.all(),
        'competition_submissions': (CompetitionSubmission.objects
                                 .select_related('competition', 'participant')
                                 .all()),
        'exam_submissions': (Submission.objects
                          .select_related('exam', 'user')
                          .all())
    }
    
    # Kullanıcıya özel verileri filtrele
    user_data = {
        'competition_submissions': [s for s in cached_data['competition_submissions'] 
                                  if s.participant == user],
        'exam_submissions': [s for s in cached_data['exam_submissions'] 
                           if s.user == user]
    }
    
    context = {
        'stats': get_user_stats(cached_data, user),
        'competition_stats': get_competition_stats(user_data['competition_submissions']),
        'exam_stats': get_exam_stats(user_data['exam_submissions']),
        'activities': get_recent_activities(user_data),
        'upcoming_exams': get_upcoming_exams(cached_data['exams']),
        'leaderboard': get_leaderboard(cached_data['competition_submissions'])
    }
    
    return render(request, 'dashboard/index.html', context)

def get_user_stats(cached_data, user):
    """Kullanıcı istatistiklerini hesapla"""
    active_competitions = len([c for c in cached_data['competitions'] if c.is_active])
    active_exams = len([e for e in cached_data['exams'] if e.is_active])
    upcoming_exams = len([e for e in cached_data['exams'] 
                         if e.start_time > timezone.now()])
    
    return {
        'active_competitions': active_competitions,
        'active_exams': active_exams,
        'total_submissions': len([s for s in cached_data['competition_submissions'] 
                                if s.participant == user]),
        'completed_exams': len([s for s in cached_data['exam_submissions'] 
                              if s.user == user and s.is_graded]),
        'upcoming_exams': upcoming_exams
    }

def get_competition_stats(user_submissions):
    """Yarışma istatistiklerini hesapla"""
    completed_submissions = [s for s in user_submissions 
                           if s.processing_status == 'completed']
    
    if not completed_submissions:
        return {
            'best_score': 0,
            'submission_dates': '[]',  # JSON formatında boş liste
            'f1_scores': '[]',        # JSON formatında boş liste
            'recent_submissions': []
        }
        
    submission_data = sorted(
        [(s.submitted_at.strftime('%Y-%m-%d'), s.f1_score) 
         for s in completed_submissions 
         if s.f1_score is not None],
        key=lambda x: x[0]
    )
    
    dates, scores = zip(*submission_data) if submission_data else ([], [])
    
    return {
        'best_score': max(scores, default=0),
        'submission_dates': list(dates),  # Tarihleri liste olarak gönder
        'f1_scores': list(scores),        # Skorları liste olarak gönder
        'recent_submissions': sorted(completed_submissions, 
                                  key=lambda x: x.submitted_at,
                                  reverse=True)[:5]
    }

def get_exam_stats(user_submissions):
    """Sınav istatistiklerini hesapla"""
    # Sadece notlandırılmış sınavları al
    graded_submissions = [s for s in user_submissions 
                         if s.is_graded and s.score is not None]
    
    if not graded_submissions:
        return {
            'submission_dates': [],  # Boş liste
            'scores': [],           # Boş liste
            'avg_score': 0
        }
    
    # Her sınav için en yüksek notu al
    exam_best_scores = {}
    for submission in graded_submissions:
        exam_id = submission.exam.id
        if exam_id not in exam_best_scores or submission.score > exam_best_scores[exam_id]['score']:
            exam_best_scores[exam_id] = {
                'date': submission.end_time.strftime('%Y-%m-%d'),
                'score': submission.score
            }
    
    # Tarihe göre sırala
    submission_data = sorted(
        [(data['date'], data['score']) 
         for data in exam_best_scores.values()],
        key=lambda x: x[0]
    )
    
    dates, scores = zip(*submission_data) if submission_data else ([], [])
    
    return {
        'submission_dates': list(dates),
        'scores': list(scores),
        'avg_score': sum(scores)/len(scores) if scores else 0
    }



def get_recent_activities(user_data):
    activities = []
    
    all_comp_subs = user_data['competition_submissions']
    user_comp_subs = sorted(
        [s for s in all_comp_subs],
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
    
    all_exam_subs = user_data['exam_submissions']
    user_exam_subs = sorted(
        [s for s in all_exam_subs if s.end_time is not None], 
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


def get_upcoming_exams(exams):
    """Yaklaşan sınavları getir"""
    now = timezone.now()
    upcoming = [e for e in exams if e.start_time > now]
    return sorted(upcoming, key=lambda x: x.start_time)[:5]

def get_leaderboard(submissions):
    """Global liderlik tablosunu getir"""
    all_submissions = submissions
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
        
        # Her yarışma için en iyi skoru ve gönderim zamanını güncelle
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
    
    # Her yarışmanın birincisini belirle
    for competition_id in set(s.competition.id for s in all_submissions):
        comp_submissions = [(
            username, 
            data['best_scores'].get(competition_id, 0),
            data['submission_times'].get(competition_id)
        ) for username, data in user_scores.items() 
        if competition_id in data['best_scores']]
        
        if comp_submissions:
            # Eşit skorlarda erken gönderen kazansın
            winner = sorted(
                comp_submissions,
                key=lambda x: (-x[1], x[2])  # Skor yüksek, zaman küçük olsun
            )[0][0]
            
            if winner in user_scores:
                user_scores[winner]['first_places'] += 1
    
    # Ortalama skorları hesapla
    for username, data in user_scores.items():
        total_score = sum(data['best_scores'].values())
        num_competitions = len(data['best_scores'])
        data['avg_score'] = total_score / num_competitions if num_competitions > 0 else 0
        data['total_competitions'] = len(data['total_competitions'])
        
        # Gereksiz verileri temizle
        data.pop('best_scores')
        data.pop('submission_times')
    
    # Önce birincilik sayısı, sonra ortalama skor
    sorted_users = sorted(
        user_scores.values(),
        key=lambda x: (-x['first_places'], -x['avg_score'])
    )
    
    return sorted_users[:10]