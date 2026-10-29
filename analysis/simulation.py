"""Independent Python implementation inspired by an Operations Analytics case study.
Synthetic single-queue, multiple-officer discrete-event simulation; no bank data used.
"""
from pathlib import Path
import heapq
import numpy as np
import pandas as pd

ARRIVALS_PER_HOUR = 8.5
MEAN_SERVICE_MIN = 12.0
SERVICE_CV = 0.25
DAY_MINUTES = 360
DAYS = 30
REPLICATIONS = 30
SLA_MIN = 15
OFFICER_HOURLY_COST_LKR = 2000
SEED = 2026


def simulate_day(arrivals, durations, officers):
    """FCFS; arrivals stop at closing, but all admitted customers finish service."""
    available = [0.0] * officers
    heapq.heapify(available)
    waits, system_times, busy = [], [], 0.0
    for arrival, service in zip(arrivals, durations):
        next_free = heapq.heappop(available)
        start = max(float(arrival), next_free)
        end = start + float(service)
        heapq.heappush(available, end)
        waits.append(start - arrival)
        system_times.append(end - arrival)
        # Busy time within the advertised operating window (not beyond closing)
        busy += max(0.0, min(end, DAY_MINUTES) - max(start, 0.0))
    return waits, system_times, busy


def generate_days(rng):
    """Identical synthetic arrivals/service requirements used in both staffing options."""
    sigma = np.sqrt(np.log(1 + SERVICE_CV**2))
    mu = np.log(MEAN_SERVICE_MIN) - sigma**2 / 2
    days = []
    for _ in range(DAYS):
        clock, arrivals = 0.0, []
        while True:
            clock += rng.exponential(60 / ARRIVALS_PER_HOUR)
            if clock >= DAY_MINUTES:
                break
            arrivals.append(clock)
        durations = rng.lognormal(mu, sigma, len(arrivals))
        days.append((np.array(arrivals), durations))
    return days


def run_experiment():
    results = []
    customer_rows = []
    for rep in range(REPLICATIONS):
        days = generate_days(np.random.default_rng(SEED + rep))
        for officers in [2, 3]:
            waits, systems, busy = [], [], 0.0
            for day_idx, (arrivals, service) in enumerate(days, start=1):
                w, t, b = simulate_day(arrivals, service, officers)
                waits.extend(w)
                systems.extend(t)
                busy += b
                customer_rows.extend({'replication': rep + 1, 'day': day_idx,
                                      'officers': officers, 'waiting_minutes': x}
                                     for x in w)
            n = len(waits)
            results.append({
                'replication': rep + 1, 'officers': officers,
                'customers': n,
                'mean_wait_min': float(np.mean(waits)),
                'p95_wait_min': float(np.percentile(waits, 95)),
                'mean_time_in_system_min': float(np.mean(systems)),
                'sla_within_15_pct': 100 * float(np.mean(np.array(waits) <= SLA_MIN)),
                'utilization_pct': 100 * busy / (officers * DAY_MINUTES * DAYS),
                'labor_cost_lkr': officers * (DAY_MINUTES / 60) * DAYS * OFFICER_HOURLY_COST_LKR,
            })
    return pd.DataFrame(results), pd.DataFrame(customer_rows)


def make_plots(results, output_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    means = results.groupby('officers').mean(numeric_only=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(2)
    w = .34
    ax.bar(x-w/2, means['mean_wait_min'].values, w, label='Average wait')
    ax.bar(x+w/2, means['p95_wait_min'].values, w, label='95th percentile wait')
    ax.set_xticks(x, ['2 officers', '3 officers'])
    ax.set_ylabel('Waiting time (minutes)')
    ax.set_title('Simulated customer waiting times')
    ax.legend()
    fig.tight_layout()
    fig.savefig(out/'waiting_times.png', dpi=170)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(['2 officers', '3 officers'], means['sla_within_15_pct'].values)
    ax.set_ylim(0, 105)
    ax.set_ylabel('Share starting service within 15 min (%)')
    ax.set_title('Simulated service-level compliance')
    fig.tight_layout()
    fig.savefig(out/'service_level.png', dpi=170)
    plt.close(fig)


if __name__ == '__main__':
    results, customers = run_experiment()
    summary = results.groupby('officers').mean(numeric_only=True).drop(columns='replication')
    print(summary.round(2).to_string())
    make_plots(results, Path(__file__).resolve().parent.parent/'visuals')
