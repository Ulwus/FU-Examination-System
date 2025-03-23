import random
import string
import pandas as pd
from io import BytesIO
import joblib
from sklearn.metrics import f1_score, accuracy_score, precision_score, recall_score, confusion_matrix

def generate_pin_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

def evaluate_model(model_file, competition):
    try:
        # Test verisini yükle
        test_dataset = competition.test_dataset.open('rb')
        test_df = pd.read_csv(test_dataset)
        X_test = test_df.drop('target', axis=1)
        y_test = test_df['target']

        # Modeli yükle
        model_bytes = model_file.read()
        model = joblib.load(BytesIO(model_bytes))

        # Tahmin yap
        y_pred = model.predict(X_test)

        # Confusion matrix hesapla
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = cm.ravel()

        # Metrikleri hesapla
        scores = {
            'f1_score': f1_score(y_test, y_pred, average='weighted'),
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, average='weighted'),
            'recall': recall_score(y_test, y_pred, average='weighted'),
            'confusion_matrix': {
                'true_positives': int(tp),
                'false_positives': int(fp),
                'false_negatives': int(fn),
                'true_negatives': int(tn)
            }
        }
        return scores

    except Exception as e:
        raise ValueError(f"Model değerlendirme hatası: {str(e)}")
    
    finally:
        if 'test_dataset' in locals():
            test_dataset.close()