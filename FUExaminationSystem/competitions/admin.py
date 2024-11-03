from django.contrib import admin
from .models import Competition, CompetitionParticipant, CompetitionSubmission

admin.site.register(Competition)
admin.site.register(CompetitionParticipant)
admin.site.register(CompetitionSubmission)
