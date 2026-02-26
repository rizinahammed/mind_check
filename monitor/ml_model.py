import random


EMOTIONS = [
    'Happiness',
    'Sadness',
    'Fear',
    'Anger',
    'Anxiety',
    'Neutral',
]


def predict_emotion(text: str) -> tuple[str, float]:
    """
    Placeholder emotion predictor.

    Later, replace this with real model loading and inference logic:
    1) Load your .pkl / transformer model once.
    2) Preprocess incoming text.
    3) Return (predicted_label, confidence_score).
    """
    cleaned = (text or '').strip().lower()

    # Very simple rule-based placeholder to make demo output look realistic.
    if any(word in cleaned for word in ['happy', 'grateful', 'good', 'great', 'joy']):
        return 'Happiness', 0.87
    if any(word in cleaned for word in ['sad', 'cry', 'lonely', 'down']):
        return 'Sadness', 0.84
    if any(word in cleaned for word in ['afraid', 'scared', 'fear', 'panic']):
        return 'Fear', 0.82
    if any(word in cleaned for word in ['angry', 'mad', 'annoyed', 'frustrated']):
        return 'Anger', 0.80
    if any(word in cleaned for word in ['anxious', 'stress', 'overthink', 'worried']):
        return 'Anxiety', 0.85

    return random.choice(EMOTIONS), round(random.uniform(0.62, 0.79), 2)