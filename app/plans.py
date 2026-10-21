import json
from pathlib import Path


def plan_config(plan):
    config = json.loads(Path(__file__).with_name('plan_templates.json').read_text(encoding='utf-8'))
    rule = config['plans'][plan]
    if len(rule['phase_days']) != len(config['phases']) or sum(rule['phase_days']) != rule['duration_days']:
        raise ValueError('Phase durations must match total onboarding duration')
    schedule = []
    day = 1
    for phase, days in zip(config['phases'], rule['phase_days']):
        if days < 1:
            raise ValueError('Phase durations must be positive')
        schedule.append({**phase, 'start_day': day, 'end_day': day + days - 1, 'duration_days': days})
        day += days
    return {**rule, 'phases': schedule}
