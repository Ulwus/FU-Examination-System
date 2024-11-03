from django import forms
from .models import Competition
import pandas as pd
from django.core.exceptions import ValidationError

class CompetitionForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = [
            'title', 
            'description', 
            'start_date', 
            'end_date',
            'max_submissions_per_day',
            'training_dataset',
            'test_dataset'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'start_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'max_submissions_per_day': forms.NumberInput(attrs={'class': 'form-control'}),
            'training_dataset': forms.FileInput(attrs={'class': 'form-control'}),
            'test_dataset': forms.FileInput(attrs={'class': 'form-control'})
        }

    def clean(self):
        cleaned_data = super().clean()
        training_dataset = cleaned_data.get('training_dataset')
        test_dataset = cleaned_data.get('test_dataset')

        if training_dataset and test_dataset:
            if not (training_dataset.name.endswith('.csv') and test_dataset.name.endswith('.csv')):
                raise ValidationError("Dataset'ler CSV formatında olmalıdır.")

            try:
                import io

                training_dataset.seek(0)
                test_dataset.seek(0)

                training_content = training_dataset.read().decode('utf-8-sig')
                test_content = test_dataset.read().decode('utf-8-sig')

                training_df = pd.read_csv(io.StringIO(training_content))
                test_df = pd.read_csv(io.StringIO(test_content))

                if training_df.shape[1] != test_df.shape[1]:
                    raise ValidationError("Training ve test datasetlerinin sütun sayıları aynı olmalıdır.")

                if not all(training_df.columns == test_df.columns):
                    raise ValidationError("Training ve test datasetlerinin sütun isimleri aynı olmalıdır.")

            except Exception as e:
                raise ValidationError(f"Dataset kontrolü sırasında hata: {str(e)}")

        return cleaned_data

class ModelSubmissionForm(forms.Form):
    model_file = forms.FileField(
        required=True,
        label='Model Dosyası (.pkl)',
        help_text='Eğitilmiş modelinizi .pkl formatında yükleyin.'
    )

class JoinCompetitionForm(forms.Form):
    pin_code = forms.CharField(
        max_length=6,
        label='PIN Kodu',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )