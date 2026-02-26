"""
Insight generation service layer for emotional analytics.
Produces rule-based AI guidance based on historical emotion data.
"""

from collections import Counter
from datetime import timedelta
from django.utils import timezone


def detect_trend(emotions_list):
    """
    Analyze trend direction from last 7 emotional entries.
    
    Args:
        emotions_list: List of emotion strings (most recent first)
    
    Returns:
        str: "upward", "downward", or "stable"
    """
    if not emotions_list:
        return "neutral"
    
    # Keep last 7 entries
    recent = emotions_list[:7]
    
    score_map = {
        "Happiness": 1,
        "Neutral": 0,
        "Sadness": -1,
        "Fear": -1,
        "Anger": -1,
        "Anxiety": -1,
    }
    scored = [score_map.get(emotion, 0) for emotion in recent]
    average_score = sum(scored) / len(scored)

    if average_score >= 0.4:
        return "upward"
    elif average_score <= -0.4:
        return "downward"
    else:
        return "stable"


def calculate_volatility(emotions_list):
    """
    Measure emotional variability as ratio of emotion switches to total entries.
    
    Args:
        emotions_list: List of emotion strings (chronological order)
    
    Returns:
        float: Volatility score (0.0 to 1.0)
    """
    if len(emotions_list) <= 1:
        return 0.0
    
    # Count transitions between different emotions
    switches = 0
    for i in range(len(emotions_list) - 1):
        if emotions_list[i] != emotions_list[i + 1]:
            switches += 1
    
    volatility = switches / (len(emotions_list) - 1)
    return round(volatility, 2)


def generate_ai_insight(emotional_data):
    """
    Generate structured AI insight based on rule-based logic.
    
    Args:
        emotional_data: Dict with keys:
            - dominant_emotion (str)
            - positive_ratio (float, 0-100)
            - volatility (float, 0-1)
            - trend_direction (str)
    
    Returns:
        Dict: {
            "summary": str,
            "recommendation": str
        }
    """
    dominant = emotional_data.get("dominant_emotion", "Unknown")
    positive_ratio = emotional_data.get("positive_ratio", 0)
    volatility = emotional_data.get("volatility", 0)
    trend = emotional_data.get("trend_direction", "stable")
    
    # Rule 1: Anxiety with high volatility
    if dominant == "Anxiety" and volatility > 0.4:
        return {
            "summary": "Recurring anxiety signals detected in your emotional patterns. Your entries show heightened emotional variability paired with anxiety as a dominant theme.",
            "recommendation": "Introduce structured breathing reset exercises during identified peak anxiety periods. Consider implementing a daily grounding routine to interrupt anxiety cycles before they intensify."
        }
    
    # Rule 2: Downward emotional trend
    if trend == "downward":
        return {
            "summary": "A decline in positive emotional affect has been detected over your recent entries. Your baseline mood stability is shifting downward.",
            "recommendation": "Establish consistent daily routines and maintain regular sleep cycles. Structured daily activities help stabilize emotional baseline. Consider increasing journaling frequency to track the root triggers of this decline."
        }
    
    # Rule 3: High positive ratio
    if positive_ratio > 65:
        return {
            "summary": "Your emotional baseline shows predominantly positive affect. Happiness and calm states are well-represented in your recent reflections.",
            "recommendation": "Maintain your current journaling frequency to reinforce emotional stability. Document what conditions support this positive baseline—this pattern recognition helps predict and sustain wellbeing."
        }
    
    # Rule 4: High volatility
    if volatility > 0.5:
        return {
            "summary": "High emotional variability detected. Your emotional states are shifting frequently across entries, indicating unstable baseline patterns.",
            "recommendation": "Prioritize sleep cycle regulation and establish consistent daily structure. Emotional volatility often correlates with disrupted sleep and unstructured routines. Gradual stabilization through routine consistency is recommended."
        }
    
    # Rule 5: Sadness dominance
    if dominant in ["Sadness", "Fear"]:
        return {
            "summary": f"Your emotional profile shows {dominant.lower()} as a dominant state. This pattern suggests sustained low mood or worry cycles in your recent reflections.",
            "recommendation": "Engage in structured social connection and physical activity. Isolation amplifies negative emotional patterns. Establish small daily activities that create emotional counterweights to {dominant.lower()}."
        }
    
    # Rule 6: Default - moderate variability
    return {
        "summary": "Moderate emotional variability observed in your patterns. Your emotional states show normal fluctuation within a balanced range, with no dominant negative patterns.",
        "recommendation": "Continue your structured self-reflection practice. Regular journaling maintains baseline emotional awareness and helps identify patterns before they accumulate. Consistency is the strongest predictor of emotional stability."
    }


def prepare_trend_data(entries):
    """
    Prepare daily trend data for Chart.js visualization.
    
    Groups entries by date, converts emotions to numeric scores,
    and averages multiple entries per day.
    
    Args:
        entries: QuerySet of EmotionResult objects (ordered chronologically)
    
    Returns:
        Dict with formatted data for Chart.js:
        {
            "labels": ["Jan 15", "Jan 16", ...],
            "scores": [4.5, 3.2, ...],
            "has_data": bool
        }
    """
    # Emotion to intensity score mapping
    emotion_scores = {
        "Happiness": 5,
        "Excited": 4,
        "Calm": 4,
        "Neutral": 3,
        "Sadness": 2,
        "Anger": 1,
        "Anxiety": 1,
        "Fear": 2,
    }
    
    # Group emotions by date
    date_scores = {}
    
    for result in entries.order_by("entry__created_at"):
        # Convert to local timezone for date calculation
        local_datetime = timezone.localtime(result.entry.created_at)
        date_key = local_datetime.date()
        
        # Get emotion score (default to Neutral if not found)
        score = emotion_scores.get(result.emotion, 3)
        
        # Append to date's scores
        if date_key not in date_scores:
            date_scores[date_key] = []
        date_scores[date_key].append(score)
    
    # Build labels and averaged scores
    labels = []
    scores = []
    
    for date_key in sorted(date_scores.keys()):
        labels.append(date_key.strftime("%b %d"))
        daily_scores = date_scores[date_key]
        avg_score = sum(daily_scores) / len(daily_scores)
        scores.append(round(avg_score, 1))
    
    return {
        "labels": labels,
        "scores": scores,
        "has_data": len(labels) >= 2  # Need at least 2 points for trend
    }
