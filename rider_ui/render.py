"""Small presentation helpers; never alter a saved response."""
import math
from rider_ui.timings import timing_summary

STAGES = (('retrieval', 'Retrieval'), ('ranking', 'Ranking'),
          ('generation', 'Generation'), ('verification', 'Verification'),
          ('streaming', 'Streaming'))


def timing_caption(view, delivery=None):
    """Show only fixed stage names and measured durations/availability."""
    summary = timing_summary(view, delivery)
    parts = []
    for key, label in STAGES:
        row = summary.get(key, {})
        seconds = row.get('seconds')
        status = row.get('status')
        if (status == 'recorded' and type(seconds) in (int, float) and
                math.isfinite(seconds) and seconds >= 0):
            value = '<0.01 s' if 0 < seconds < 0.01 else f'{seconds:.2f} s'
        elif status == 'not_required':
            value = 'Not needed'
        elif status == 'interrupted':
            value = 'Interrupted'
        else:
            value = 'Not recorded'
        parts.append(label + ': ' + value)
    return 'Timings · ' + ' · '.join(parts)
