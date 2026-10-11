"""Transparent price arithmetic; no cloud or provider operations."""
import json
from pathlib import Path

fx = 108.3965 / 1.1206  # ECB 9 October 2026 EUR cross-rate, checked 11 October.
seconds = 30 * 86400
rows = []
for mode in ('request', 'instance'):
    for minimum in (0, 1):
        for active in (0, 100 * 30):
            # 100 requests/day, 1 second each, no overlap; startup/shutdown excluded.
            idle = seconds - active if minimum else 0
            if mode == 'request':
                cpu = active * .000024 + idle * .0000025
                memory = (active + idle) * .5 * .0000025
                requests = active * .40 / 1_000_000
                cpu_credit, mem_credit = 180000 * .000024, 360000 * .0000025
            else:
                cpu = (active + idle) * .000018
                memory = (active + idle) * .5 * .000002
                requests = 0
                cpu_credit, mem_credit = 240000 * .000018, 450000 * .000002
            gross = cpu + memory + requests
            net = max(0, cpu - cpu_credit) + max(0, memory - mem_credit)
            rows.append(dict(billing_mode=mode, min_instances=minimum, requests_per_day=active//30,
                             active_instance_seconds=active, idle_instance_seconds=idle,
                             gross_month_usd=gross, gross_day_usd=gross/30,
                             gross_month_inr=gross*fx, gross_day_inr=gross*fx/30,
                             full_available_free_tier_month_usd=net,
                             full_available_free_tier_month_inr=net*fx,
                             full_available_free_tier_daily_equivalent_usd=net/30,
                             full_available_free_tier_daily_equivalent_inr=net*fx/30))
report = dict(checked_date='2026-10-11', region='us-central1', vcpu=1, memory_gib=.5,
              horizon_days=30, inr_per_usd=fx, fx_date='2026-10-09',
              fx_source='https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html',
              assumptions=['No commitments; no tax; no egress, logs, storage, registry, build or inference charges.',
                           'Free tier fully available is an optimistic separate scenario; account-wide use unknown.',
                           'INR is planning conversion only; Google local currency SKU rates govern invoice.',
                           '100 daily requests each consume one active instance-second, without overlap.',
                           'Startup/shutdown/replacements excluded from base rows; min0 idle compute zero is not zero total project bill.',
                           'Instance-based min0 rows exclude idle retention; actual lifecycle can cost more.'],
              rows=rows, budget_inr=800, stop_inr=640,
              last_delayed_guard_observation={'timestamp':'2026-10-11T08:37:13.856785Z','cost_inr':0,'stop':False},
              gross_request_min1_idle_days_to_stop=640/(.324*fx),
              gross_request_min1_idle_days_to_budget=800/(.324*fx),
              full_free_tier_request_min1_idle_month_usd=4.5,
              source='https://cloud.google.com/run/pricing')
Path('reports/cloud_run_cost_options_20261011.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('FX',round(fx,6))
for r in rows:
    print(r['billing_mode'],r['min_instances'],r['requests_per_day'],
          round(r['gross_month_usd'],6),round(r['gross_month_inr'],2),
          round(r['full_available_free_tier_month_usd'],6))
