import os
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib import rcParams

rcParams.update({
    'font.family': 'serif', 'font.size': 9,
    'axes.titlesize': 10, 'axes.labelsize': 9,
    'axes.grid': True, 'grid.color': '#EEEEEE',
    'grid.linewidth': 0.8, 'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.spines.top': False, 'axes.spines.right': False,
})

MODES        = ['7W', '15W', '25W']
COLORS       = ['#AEC6CF', '#B5EAD7', '#FFD1A9']
STEADY_START = 300
LOG_DIR      = '/workspace/logs'
OUT_PATH     = f'{LOG_DIR}/calibration_report_final.png'


def load_csv(mode):
    path = f'{LOG_DIR}/calibration_data_{mode}.csv'
    if not os.path.exists(path):
        return None
    data = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = {}
            for k, v in row.items():
                try:
                    d[k] = float(v)
                except (ValueError, TypeError):
                    d[k] = v
            data.append(d)
    return data


def get_vals(data, key):
    return [d[key] for d in data
            if d.get(key) not in (None, '', 'None')
            and not (isinstance(d[key], float) and np.isnan(d[key]))]



def get_time_series(data, key):
    times = []
    vals = []
    for d in data:
        t = d.get('elapsed_sec')
        v = d.get(key)
        if t is not None and v not in (None, '', 'None') and not (isinstance(v, float) and np.isnan(v)):
            times.append(float(t))
            vals.append(float(v))
    return times, vals



def compute_cv(data, key):
    steady = [d for d in data if float(d.get('elapsed_sec', 0)) >= STEADY_START]
    vals   = get_vals(steady, key)
    if len(vals) < 10:
        return None, None, None
    mean = np.mean(vals)
    std  = np.std(vals)
    cv   = std / mean if mean != 0 else 0
    return cv, mean, std



def sliding_cv(data, key, window_sec=60):
    times, vals = get_time_series(data, key)
    cv_times = []
    cv_vals = []
    for i in range(len(times)):
        current_time = times[i]
        if current_time < window_sec:
            continue
        window_data = [v for t, v in zip(times, vals) if current_time - window_sec <= t <= current_time]
        if len(window_data) > 5:
            m = np.mean(window_data)
            s = np.std(window_data)
            cv_times.append(current_time)
            cv_vals.append((s / m * 100) if m != 0 else 0)
    return cv_times, cv_vals


def main():
    missing = [f'{LOG_DIR}/calibration_data_{m}.csv'
               for m in MODES
               if not os.path.exists(f'{LOG_DIR}/calibration_data_{m}.csv')]
    if missing:
        print(f'Missing files: {missing}')
        print('Run calibration_node for each power mode first.')
        return

    all_data = {m: load_csv(m) for m in MODES}

    fig = plt.figure(figsize=(18, 18))
    gs  = gridspec.GridSpec(4, len(MODES), figure=fig,
                            hspace=0.6, wspace=0.35)
    fig.suptitle(
        'Calibration Report — Natural Variability Analysis\n'
        'Jetson Orin Nano (7W, 15W, 25W — 10 minutes each)',
        fontsize=13, fontweight='bold', y=1.01)

    cvs_summary = {}

    for mi, (mode, color) in enumerate(zip(MODES, COLORS)):
        data = all_data[mode]

        # ── CPU Timeline ── 
        ax1 = fig.add_subplot(gs[0, mi])
        t_cpu, v_cpu = get_time_series(data, 'cpu') 
        ax1.plot(t_cpu, v_cpu, color=color, linewidth=0.8, alpha=0.8)
        ax1.axvline(x=STEADY_START, color='gray', linestyle='--',
                    linewidth=1, label='Steady-state start (300s)')
        ax1.set_title(f'{mode} — CPU % Timeline', fontweight='bold')
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('CPU %')
        ax1.legend(fontsize=7)

        # ── Sliding CV ── 
        ax2 = fig.add_subplot(gs[1, mi])
        t_cv, v_cv = sliding_cv(data, 'cpu', window_sec=60)
        ax2.plot(t_cv, v_cv, color=color, linewidth=1.0)
        ax2.set_title(f'{mode} — Sliding CV (60s window)', fontweight='bold')
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('CV %')

        # ── Latency Timeline 
        ax3 = fig.add_subplot(gs[2, mi])
        t_lat, v_lat = get_time_series(data, 'latency_ms')
        if v_lat:
            ax3.plot(t_lat, v_lat, color=color, linewidth=0.8, alpha=0.8)
            ax3.axvline(x=STEADY_START, color='gray', linestyle='--',
                        linewidth=1, label='Steady-state start (300s)')
            ax3.legend(fontsize=7)
        else:
            ax3.text(0.5, 0.5, 'No latency data', transform=ax3.transAxes,
                     ha='center', va='center', fontsize=9, color='gray')
        ax3.set_title(f'{mode} — Pipeline Latency (ms)', fontweight='bold')
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('ms')

        
        cv, mean, std = compute_cv(data, 'cpu')
        
        steady_data = [d for d in data if float(d.get('elapsed_sec', 0)) >= STEADY_START]
        lat_vals_steady = get_vals(steady_data, 'latency_ms')
        
        lat_mean = np.mean(lat_vals_steady) if lat_vals_steady else None
        lat_std  = np.std(lat_vals_steady)  if lat_vals_steady else None
        lat_cv   = (lat_std / lat_mean * 100) if (lat_mean and lat_mean != 0) else None

        cvs_summary[mode] = {
            'cv': cv, 'mean': mean, 'std': std,
            'lat_mean': lat_mean, 'lat_std': lat_std, 'lat_cv': lat_cv
        }
        print(f'[{mode}] CPU CV: {cv*100:.2f}% | Latency mean: {lat_mean:.2f}ms' if cv and lat_mean else f'[{mode}] insufficient data')

    # ── Summary table ──
    ax4 = fig.add_subplot(gs[3, :])
    ax4.axis('off')
    ax4.set_title(
        'Calibration Summary — Steady-State Natural Variability',
        fontweight='bold', fontsize=9, pad=15)

    metrics = ['CPU Mean %', 'CPU Std %', 'CPU CV %',
               'Latency Mean (ms)', 'Latency Std (ms)', 'Latency CV %']
    tdata   = []
    for m in metrics:
        row = []
        for mode in MODES:
            s = cvs_summary[mode]
            if m == 'CPU Mean %':
                row.append(f"{s['mean']:.2f}" if s['mean'] else 'N/A')
            elif m == 'CPU Std %':
                row.append(f"{s['std']:.2f}" if s['std'] else 'N/A')
            elif m == 'CPU CV %':
                row.append(f"{s['cv']*100:.2f}" if s['cv'] else 'N/A')
            elif m == 'Latency Mean (ms)':
                row.append(f"{s['lat_mean']:.2f}" if s['lat_mean'] else 'N/A')
            elif m == 'Latency Std (ms)':
                row.append(f"{s['lat_std']:.2f}" if s['lat_std'] else 'N/A')
            elif m == 'Latency CV %':
                row.append(f"{s['lat_cv']:.2f}" if s['lat_cv'] else 'N/A')
        tdata.append(row)

    cell_colors = [['#FFFFFF'] * len(MODES) for _ in metrics]

    tbl = ax4.table(
        cellText    = tdata,
        rowLabels   = metrics,
        colLabels   = MODES,
        cellLoc     = 'center',
        loc         = 'center',
        cellColours = cell_colors)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 2.0)

    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor('#CCCCCC')
        if r == 0:
            cell.set_facecolor('#E8F0FE')
            cell.set_text_props(fontweight='bold')
        if c == -1:
            cell.set_facecolor('#F5F5F5')
            cell.set_text_props(fontweight='bold')

    plt.savefig(OUT_PATH, dpi=150, bbox_inches='tight', facecolor='white')
    print(f'Final report saved: {OUT_PATH}')


if __name__ == '__main__':
    main()