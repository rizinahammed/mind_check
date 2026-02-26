from django.conf import settings
from django.db import models


class JournalEntry(models.Model):
	# Journal text written by an authenticated user.
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='journal_entries')
	content = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'JournalEntry #{self.id} by {self.user.username}'


class EmotionResult(models.Model):
	EMOTION_HAPPINESS = 'Happiness'
	EMOTION_SADNESS = 'Sadness'
	EMOTION_FEAR = 'Fear'
	EMOTION_ANGER = 'Anger'
	EMOTION_ANXIETY = 'Anxiety'
	EMOTION_NEUTRAL = 'Neutral'

	EMOTION_CHOICES = [
		(EMOTION_HAPPINESS, 'Happiness'),
		(EMOTION_SADNESS, 'Sadness'),
		(EMOTION_FEAR, 'Fear'),
		(EMOTION_ANGER, 'Anger'),
		(EMOTION_ANXIETY, 'Anxiety'),
		(EMOTION_NEUTRAL, 'Neutral'),
	]

	# One analysis record per journal entry.
	entry = models.OneToOneField(JournalEntry, on_delete=models.CASCADE, related_name='emotion_result')
	emotion = models.CharField(max_length=20, choices=EMOTION_CHOICES)
	confidence = models.FloatField(help_text='Prediction confidence between 0 and 1.')
	analyzed_at = models.DateTimeField(auto_now_add=True)
	model_version = models.CharField(max_length=50, default='dummy-v1')

	class Meta:
		ordering = ['-analyzed_at']

	def confidence_percent(self):
		return round(self.confidence * 100, 2)

	def __str__(self):
		return f'{self.emotion} ({self.confidence_percent()}%)'


class UserPreference(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preference')
	notifications_enabled = models.BooleanField(default=True)
	dark_mode_enabled = models.BooleanField(default=False)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f'Preferences for {self.user.username}'
