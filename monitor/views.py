import calendar
import csv
from urllib.parse import urlencode
from collections import defaultdict
from datetime import timedelta, datetime

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date

from .forms import (
	EmailAuthenticationForm,
	JournalEntryForm,
	ProfileForm,
	RegisterForm,
	UserPreferenceForm,
)
from .ml_model import predict_emotion
from .models import EmotionResult, JournalEntry, UserPreference


def landing_page(request):
	return render(request, 'monitor/landing.html')


def register_page(request):
	if request.user.is_authenticated:
		return redirect('dashboard')

	if request.method == 'POST':
		form = RegisterForm(request.POST)
		if form.is_valid():
			user = form.save()
			login(request, user)
			messages.success(request, 'Account created successfully.')
			return redirect('dashboard')
	else:
		form = RegisterForm()

	return render(request, 'monitor/register.html', {'form': form})


def login_page(request):
	return LoginView.as_view(
		template_name='registration/login.html',
		authentication_form=EmailAuthenticationForm,
	)(request)


@login_required
def dashboard_page(request):
	results = EmotionResult.objects.filter(entry__user=request.user).select_related('entry')
	entries = JournalEntry.objects.filter(user=request.user).select_related('emotion_result')

	total_entries = entries.count()
	positive_count = results.filter(emotion=EmotionResult.EMOTION_HAPPINESS).count()
	positive_ratio = round((positive_count / total_entries) * 100, 1) if total_entries else 0
	streak = _calculate_streak(entries)

	calendar_weeks, month_name = _build_month_calendar(entries)
	month, year = month_name.split(' ')

	emotion_counts = _emotion_counts(results)

	context = {
		'total_entries': total_entries,
		'positive_ratio': positive_ratio,
		'streak': streak,
		'month_days': calendar_weeks,
		'month': month,
		'year': year,
		'emotion_counts': emotion_counts,
	}
	return render(request, 'monitor/dashboard.html', context)


@login_required
def journal_page(request):
	if request.method == 'POST':
		form = JournalEntryForm(request.POST)
		if form.is_valid():
			entry = form.save(commit=False)
			entry.user = request.user
			entry.save()

			# Keep ML call separated in its own module for easy replacement later.
			emotion_label, confidence = predict_emotion(entry.content)
			result = EmotionResult.objects.create(
				entry=entry,
				emotion=emotion_label,
				confidence=confidence,
			)

			messages.success(request, 'Journal analyzed successfully.')
			return redirect('emotional_results', entry_id=result.entry_id)
	else:
		form = JournalEntryForm()

	context = {
		'form': form,
	}
	return render(request, 'monitor/journal.html', context)


@login_required
def emotional_results_page(request, entry_id):
	entry = get_object_or_404(JournalEntry.objects.select_related('emotion_result'), id=entry_id, user=request.user)
	result = get_object_or_404(EmotionResult, entry=entry)

	categories = [emotion for emotion, _ in EmotionResult.EMOTION_CHOICES]
	radar_data = {emotion: 12 for emotion in categories}
	radar_data[result.emotion] = max(25, int(result.confidence * 100))

	suggestions = {
		EmotionResult.EMOTION_HAPPINESS: 'Your reflection indicates emotional clarity and positive momentum. Maintain this stability with regular routines and gratitude-based journaling.',
		EmotionResult.EMOTION_SADNESS: 'Your writing suggests low emotional energy. Gentle routines, social connection, and structured sleep may help regulate mood over the next few days.',
		EmotionResult.EMOTION_FEAR: 'The current profile reflects elevated fear signals. Focus on grounding techniques and short certainty-based planning to reduce mental load.',
		EmotionResult.EMOTION_ANGER: 'Your reflection shows heightened frustration markers. Pause before major decisions and use brief breathing breaks to de-intensify reactions.',
		EmotionResult.EMOTION_ANXIETY: 'The model detects anxiety indicators. Consider reducing information overload and using short, actionable task lists to improve perceived control.',
		EmotionResult.EMOTION_NEUTRAL: 'Your emotional tone is currently balanced. Continue consistent journaling to monitor subtle shifts and maintain mental stability.',
	}

	context = {
		'entry': entry,
		'result': result,
		'radar_labels': categories,
		'radar_values': [radar_data[label] for label in categories],
		'suggestion': suggestions.get(result.emotion, suggestions[EmotionResult.EMOTION_NEUTRAL]),
	}
	return render(request, 'monitor/emotional_results.html', context)


@login_required
def insights_page(request):
	from .services import detect_trend, calculate_volatility, generate_ai_insight, prepare_trend_data
	
	user_results = EmotionResult.objects.filter(entry__user=request.user).select_related('entry').order_by('-entry__created_at')
	
	# Collect emotion data
	emotions_chronological = [r.emotion for r in user_results.order_by('entry__created_at')]
	emotions_recent_first = [r.emotion for r in user_results]
	
	# Calculate analytics
	total_entries = user_results.count()
	emotion_counts = _emotion_counts(user_results)
	
	# Find dominant emotion
	dominant_emotion = emotion_counts[0]['emotion'] if emotion_counts else "Unknown"
	
	# Calculate positive ratio
	positive_emotions = {"Happiness"}
	positive_count = sum(1 for r in user_results if r.emotion in positive_emotions)
	positive_ratio = round((positive_count / total_entries) * 100, 1) if total_entries else 0
	
	# Detect trend and volatility
	trend_direction = detect_trend(emotions_recent_first)
	volatility = calculate_volatility(emotions_chronological)
	
	# Generate AI insight
	emotional_data = {
		"dominant_emotion": dominant_emotion,
		"positive_ratio": positive_ratio,
		"volatility": volatility,
		"trend_direction": trend_direction
	}
	ai_insight = generate_ai_insight(emotional_data)
	
	# Prepare trend data for chart
	trend_data = prepare_trend_data(user_results)
	
	# Additional aggregations (keep existing for backward compatibility)
	weekly_summary = _weekly_summary(user_results)
	monthly_summary = _monthly_summary(user_results)
	pattern_insights = _pattern_insights(user_results, weekly_summary['results'])
	
	context = {
		'total_entries': total_entries,
		'emotion_counts': emotion_counts,
		'dominant_emotion': dominant_emotion,
		'positive_ratio': positive_ratio,
		'trend_direction': trend_direction,
		'volatility': volatility,
		'pattern_summary': ai_insight['summary'],
		'ai_tip': ai_insight['recommendation'],
		'trend_labels': trend_data['labels'],
		'trend_scores': trend_data['scores'],
		'trend_has_data': trend_data['has_data'],
		'weekly_summary': weekly_summary,
		'monthly_summary': monthly_summary,
		'pattern_insights': pattern_insights,
	}
	return render(request, 'monitor/insights.html', context)


@login_required
def history_page(request):
	query = request.GET.get('q', '').strip()
	emotion = request.GET.get('emotion', '').strip()
	date_value = request.GET.get('date', '').strip()
	parsed_date = parse_date(date_value) if date_value else None
	entries = JournalEntry.objects.filter(user=request.user).select_related('emotion_result')

	if query:
		entries = entries.filter(content__icontains=query)
	if emotion:
		entries = entries.filter(emotion_result__emotion=emotion)
	if parsed_date:
		entries = entries.filter(created_at__date=parsed_date)

	if request.method == 'POST':
		entry_id = request.POST.get('entry_id')
		if entry_id:
			JournalEntry.objects.filter(id=entry_id, user=request.user).delete()
			messages.success(request, 'Entry deleted successfully.')
			params = {}
			if query:
				params['q'] = query
			if emotion:
				params['emotion'] = emotion
			if date_value:
				params['date'] = date_value
			if params:
				return redirect(f"{request.path}?{urlencode(params)}")
			return redirect('history')

	context = {
		'entries': entries,
		'query': query,
		'emotion': emotion,
		'date': date_value,
		'emotion_choices': EmotionResult.EMOTION_CHOICES,
	}
	return render(request, 'monitor/history.html', context)


@login_required
def history_by_date(request, selected_date):
	"""View for filtering entries by a specific date from calendar click."""
	try:
		parsed_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
		
		# Filter entries by the selected date (local timezone)
		entries = JournalEntry.objects.filter(user=request.user).select_related('emotion_result')
		
		# Use date filtering on created_at (Django handles timezone conversion)
		entries = entries.filter(created_at__date=parsed_date).order_by('-created_at')
		
		if request.method == 'POST':
			entry_id = request.POST.get('entry_id')
			if entry_id:
				JournalEntry.objects.filter(id=entry_id, user=request.user).delete()
				messages.success(request, 'Entry deleted successfully.')
				return redirect('history_by_date', selected_date=selected_date)
		
		context = {
			'entries': entries,
			'selected_date': parsed_date,
			'emotion_choices': EmotionResult.EMOTION_CHOICES,
		}
		return render(request, 'monitor/history.html', context)
	
	except (ValueError, TypeError):
		return redirect('history')


@login_required
def settings_page(request):
	preference, _ = UserPreference.objects.get_or_create(user=request.user)

	if request.method == 'POST':
		action = request.POST.get('action', 'save')

		if action == 'export':
			return _export_entries_csv(request.user)

		if action == 'delete_account':
			user = request.user
			logout(request)
			user.delete()
			messages.success(request, 'Your account has been deleted.')
			return redirect('landing')

		profile_form = ProfileForm(request.POST, instance=request.user)
		preference_form = UserPreferenceForm(request.POST, instance=preference)
		if profile_form.is_valid() and preference_form.is_valid():
			profile_form.save()
			preference_form.save()
			messages.success(request, 'Settings updated successfully.')
			return redirect('settings')
	else:
		profile_form = ProfileForm(instance=request.user)
		preference_form = UserPreferenceForm(instance=preference)

	context = {
		'profile_form': profile_form,
		'preference_form': preference_form,
	}
	return render(request, 'monitor/settings.html', context)


@login_required
def profile_page(request):
	return redirect('settings')


@login_required
@require_POST
def predict_emotion_api(request):
	form = JournalEntryForm(request.POST)
	if not form.is_valid():
		return JsonResponse({'error': 'Invalid input.'}, status=400)

	entry = form.save(commit=False)
	entry.user = request.user
	entry.save()

	emotion_label, confidence = predict_emotion(entry.content)
	result = EmotionResult.objects.create(
		entry=entry,
		emotion=emotion_label,
		confidence=confidence,
	)

	return JsonResponse({
		'emotion': result.emotion,
		'confidence': result.confidence_percent(),
		'message': _supportive_message(result.emotion),
	})


def _calculate_streak(entries_queryset):
	dates = sorted({entry.created_at.date() for entry in entries_queryset}, reverse=True)
	if not dates:
		return 0

	today = timezone.localdate()
	start = today if dates[0] == today else today - timedelta(days=1)
	if dates[0] < start:
		return 0

	streak = 0
	cursor = start
	date_set = set(dates)
	while cursor in date_set:
		streak += 1
		cursor -= timedelta(days=1)
	return streak


def _calculate_volatility_index(results_queryset):
	sequence = list(results_queryset.order_by('entry__created_at').values_list('emotion', flat=True))
	if len(sequence) < 2:
		return 0

	transitions = sum(1 for index in range(1, len(sequence)) if sequence[index] != sequence[index - 1])
	return round((transitions / (len(sequence) - 1)) * 100, 1)


def _emotion_counts(results_queryset):
	total = results_queryset.count()
	rows = results_queryset.values('emotion').annotate(total=Count('id')).order_by('-total')
	return [
		{
			'emotion': row['emotion'],
			'count': row['total'],
			'percent': round((row['total'] / total) * 100, 1) if total else 0,
		}
		for row in rows
	]


def _weekly_summary(results_queryset):
	start = timezone.now() - timedelta(days=7)
	results = results_queryset.filter(entry__created_at__gte=start)
	count = results.count()
	top = results.values('emotion').annotate(total=Count('id')).order_by('-total').first()
	return {
		'count': count,
		'top': top,
		'results': results,
	}


def _monthly_summary(results_queryset):
	start = timezone.now() - timedelta(days=30)
	results = results_queryset.filter(entry__created_at__gte=start)
	count = results.count()
	top = results.values('emotion').annotate(total=Count('id')).order_by('-total').first()
	return {
		'count': count,
		'top': top,
		'results': results,
	}


def _weekly_trend_scores(results_queryset):
	# Simple emotion-to-score map for a 7-day trend line.
	map_scores = {
		EmotionResult.EMOTION_HAPPINESS: 2,
		EmotionResult.EMOTION_NEUTRAL: 0,
		EmotionResult.EMOTION_SADNESS: -1,
		EmotionResult.EMOTION_FEAR: -2,
		EmotionResult.EMOTION_ANGER: -2,
		EmotionResult.EMOTION_ANXIETY: -2,
	}

	start = timezone.now().date() - timedelta(days=6)
	labels = []
	scores = []

	for day_index in range(7):
		date_value = start + timedelta(days=day_index)
		labels.append(date_value.strftime('%b %d'))
		day_results = results_queryset.filter(entry__created_at__date=date_value)
		if not day_results.exists():
			scores.append(0)
			continue
		day_scores = [map_scores.get(result.emotion, 0) for result in day_results]
		scores.append(round(sum(day_scores) / len(day_scores), 2))

	return labels, scores


def _stability_score(results_queryset):
	# Convert volatility into a 0-100 stability score.
	volatility = _calculate_volatility_index(results_queryset)
	score = max(0, round(100 - volatility, 1))
	label = 'Stable' if score >= 70 else 'Moderate' if score >= 40 else 'Needs Attention'
	return score, label


def _pattern_insights(all_results_queryset, weekly_results_queryset):
	negative_emotions = [
		EmotionResult.EMOTION_SADNESS,
		EmotionResult.EMOTION_FEAR,
		EmotionResult.EMOTION_ANGER,
		EmotionResult.EMOTION_ANXIETY,
	]

	this_week = weekly_results_queryset
	last_week_start = timezone.now() - timedelta(days=14)
	last_week_end = timezone.now() - timedelta(days=7)
	last_week = all_results_queryset.filter(entry__created_at__gte=last_week_start, entry__created_at__lt=last_week_end)

	insights = []
	for emotion in negative_emotions:
		count = this_week.filter(emotion=emotion).count()
		if count >= 2:
			insights.append(f"You experienced {emotion.lower()} {count} times this week.")

	this_negative = this_week.filter(emotion__in=negative_emotions).count()
	last_negative = last_week.filter(emotion__in=negative_emotions).count()
	if this_negative < last_negative:
		insights.append('Negative emotions have reduced compared to last week.')
	elif this_negative > last_negative:
		insights.append('Negative emotions were higher than last week.')

	this_happy = this_week.filter(emotion=EmotionResult.EMOTION_HAPPINESS).count()
	last_happy = last_week.filter(emotion=EmotionResult.EMOTION_HAPPINESS).count()
	if this_happy > last_happy:
		insights.append('Your happiness increased compared to last week.')

	return insights


def _gentle_suggestion(weekly_results_queryset):
	negative_emotions = [
		EmotionResult.EMOTION_SADNESS,
		EmotionResult.EMOTION_FEAR,
		EmotionResult.EMOTION_ANGER,
		EmotionResult.EMOTION_ANXIETY,
	]

	negative_count = weekly_results_queryset.filter(emotion__in=negative_emotions).count()
	if negative_count >= 4:
		return 'You may benefit from short breaks, slower breathing, or a brief walk to reset focus.'
	if negative_count >= 2:
		return 'Consider a few minutes of quiet reflection or gentle movement to ease mental load.'
	return 'Your recent entries show balance. Maintain steady routines and keep journaling.'


def _calculate_stability_score(results_queryset):
	volatility = _calculate_volatility_index(results_queryset)
	return max(0, round(100 - volatility, 1))


def _build_month_calendar(entries_queryset):
	today = timezone.localdate()
	year = today.year
	month = today.month

	# Get all entries for the month and convert to local dates
	month_entries = entries_queryset.filter(created_at__year=year, created_at__month=month).order_by('-created_at')
	emotion_by_date = {}
	for entry in month_entries:
		# Convert to local timezone before getting date
		local_datetime = timezone.localtime(entry.created_at)
		date_key = local_datetime.date()
		if date_key not in emotion_by_date:
			emotion_by_date[date_key] = getattr(entry.emotion_result, 'emotion', None)

	calendar_weeks = []
	month_dates = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
	for week in month_dates:
		week_data = []
		for day in week:
			week_data.append({
				'day': day,
				'day_number': day.day,
				'in_month': day.month == month,
				'is_today': day == today,
				'emotion': emotion_by_date.get(day),
				'date_str': day.strftime('%Y-%m-%d'),
			})
		calendar_weeks.append(week_data)

	return calendar_weeks, today.strftime('%B %Y')


def _build_emotion_distribution(results_queryset):
	total = results_queryset.count()
	counts_qs = results_queryset.values('emotion').annotate(total=Count('id'))
	counts = {row['emotion']: row['total'] for row in counts_qs}
	distribution = []
	for emotion, _ in EmotionResult.EMOTION_CHOICES:
		count = counts.get(emotion, 0)
		percent = round((count / total) * 100, 1) if total else 0
		distribution.append({'emotion': emotion, 'count': count, 'percent': percent})
	return distribution


def _export_entries_csv(user):
	entries = JournalEntry.objects.filter(user=user).select_related('emotion_result').order_by('-created_at')
	response = HttpResponse(content_type='text/csv')
	response['Content-Disposition'] = 'attachment; filename="mindcheck_entries.csv"'

	writer = csv.writer(response)
	writer.writerow(['Date', 'Journal Text', 'Emotion', 'Confidence'])
	for entry in entries:
		writer.writerow([
			entry.created_at.strftime('%Y-%m-%d %H:%M'),
			entry.content,
			getattr(entry.emotion_result, 'emotion', 'N/A'),
			getattr(entry.emotion_result, 'confidence', 'N/A'),
		])
	return response


def _supportive_message(emotion):
	if emotion == EmotionResult.EMOTION_HAPPINESS:
		return 'You seem steady and positive today. Keep nurturing what is working.'
	if emotion == EmotionResult.EMOTION_ANXIETY:
		return 'You seem slightly anxious today. Consider slowing down and taking a short pause.'
	if emotion == EmotionResult.EMOTION_SADNESS:
		return 'Your tone feels a bit low. Gentle routines and connection can help.'
	if emotion == EmotionResult.EMOTION_ANGER:
		return 'There are signs of frustration. A brief reset can ease intensity.'
	if emotion == EmotionResult.EMOTION_FEAR:
		return 'Some fear signals appear. Grounding exercises may help you feel safer.'
	return 'Your emotional tone looks balanced. Keep journaling to maintain clarity.'
