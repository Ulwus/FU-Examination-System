import random
import string
import pandas as pd
from io import BytesIO
import joblib
from sklearn.metrics import f1_score, accuracy_score, precision_score, recall_score

def generate_pin_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

def evaluate_model(model_file, competition):
    test_dataset = competition.test_dataset.open('rb')
    test_df = pd.read_csv(test_dataset)
    X_test = test_df.drop('target', axis=1)
    y_test = test_df['target']

    model_bytes = model_file.read()
    model = joblib.load(BytesIO(model_bytes))

    y_pred = model.predict(X_test)
    scores = {
        'f1_score': f1_score(y_test, y_pred, average='weighted'),
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred, average='macro'),
        'recall': recall_score(y_test, y_pred, average='weighted')
    }

    return scores