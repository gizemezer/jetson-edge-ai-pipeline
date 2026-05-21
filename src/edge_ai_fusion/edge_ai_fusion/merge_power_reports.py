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
C_WARMUP     = '#FFE5CC'
C_MEASURE    = '#CCFFCC'
C_COOLDOWN   = '#CCE5FF'
C_THRESH     = '#FF6B6B'
EDGE         = '#888888'
MEASURE_SEC  = 60
N_RUNS       = 5
COOLDOWN_SEC = 180
WINDOW_SEC   = 10
LOG_DIR      = '/workspace/logs'
OUT_PATH     = f'{LOG_DIR}/power_benchmark_final.png'


def load_csv(mode):
    path = f'{LOG_DIR}/power_benchmark_{mode}.csv'
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


def get_phase(data, phase):
    return [d for d in data if d.get('phase') == phase]


def get_run(data, run_idx):
    return [d for d in data
            if d.get('phase') == 'measure' and int(d.get('run', 0)) == run_idx]


def sliding_change(data, key):
    vals    = get_vals(data, key)
    changes = []
    for i in range(WINDOW_SEC, len(vals)):
        r = np.mean(vals[i-WINDOW_SEC//2:i])
        p = np.mean(vals[i-WINDOW_SEC:i-WINDOW_SEC//2])
        changes.append(abs(r-p)/abs(p)*100 if p != 0 else 0)
    return changes


def main():
    missing = [f'{LOG_DIR}/power_benchmark_{m}.csv'
               for m in MODES
               if not os.path.exists(f'{LOG_DIR}/power_benchmark_{m}.csv')]
    if missing:
        print(f'Missing files: {missing}')
        print('Run power_benchmark_node for each power mode first.')
        return

    all_data = {m: load_csv(m) for m in MODES}

    fig   = plt.figure(figsize=(18, 8 * len(MODES) + 6))
    outer = gridspec.GridSpec(
        len(MODES) + 1, 1, figure=fig,
        hspace=0.6,
        height_ratios=[3.0] * len(MODES) + [1.5])
    fig.suptitle(
        'Power Mode Benchmark — Jetson Orin Nano\n'
        f'7W vs 15W vs 25W  |  N={N_RUNS} runs × {MEASURE_SEC}s  |  '
        f'Stability threshold: 8%',
        fontsize=12, fontweight='bold', y=1.01)

    summary = {}

    for mi, (mode, color) in enumerate(zip(MODES, COLORS)):
        data  = all_data[mode]
        inner = gridspec.GridSpecFromSubplotSpec(
            2, 4, subplot_spec=outer[mi],
            hspace=0.5, wspace=0.4)

        wd    = get_phase(data, 'warmup')
        cd    = get_phase(data, 'cooldown')
        w_len = len(wd)
        c_len = len(cd)

        # ── CPU Timeline ──
        ax1 = fig.add_subplot(inner[0, :2])
        ax1.axvspan(0, w_len, alpha=0.15, color=C_WARMUP, label='Warmup')
        for r in range(N_RUNS):
            s = w_len + r * MEASURE_SEC
            ax1.axvspan(s, s + MEASURE_SEC, alpha=0.15,
                        color=C_MEASURE, label='Measure' if r == 0 else '')
        ax1.axvspan(w_len + N_RUNS * MEASURE_SEC,
                    w_len + N_RUNS * MEASURE_SEC + c_len,
                    alpha=0.15, color=C_COOLDOWN, label='Cool-down')
        all_cpu = get_vals(data, 'cpu')
        ax1.plot(all_cpu, color=color, linewidth=1.2, label='CPU %')
        ax1.axvline(x=w_len, color='gray', linestyle='--',
                    linewidth=1, label='Warmup end')
        ax1.set_title(f'{mode} — CPU % Timeline', fontweight='bold')
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('CPU %')
        ax1.legend(fontsize=7, loc='upper right')

        # ── Warmup % Change ──
        ax2 = fig.add_subplot(inner[0, 2])
        changes = sliding_change(wd, 'cpu')
        ax2.plot(changes, color=color, linewidth=1.2)
        ax2.axhline(y=8, color=C_THRESH, linestyle='--',
                    linewidth=1.2, label='8% threshold')
        ax2.set_title('Warmup % Change', fontweight='bold')
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('% Change')
        ax2.legend(fontsize=7)

        # ── Latency Timeline ──
        ax3 = fig.add_subplot(inner[0, 3])
        latency_vals = get_vals(data, 'latency_ms')
        if latency_vals:
            ax3.plot(latency_vals, color=color, linewidth=0.8, alpha=0.8)
        else:
            ax3.text(0.5, 0.5, 'No data', transform=ax3.transAxes,
                     ha='center', va='center', fontsize=9, color='gray')
        ax3.set_title('Pipeline Latency (ms)', fontweight='bold')
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('ms')

        # ── N Runs CPU ──
        ax4 = fig.add_subplot(inner[1, :2])
        means, stds = [], []
        for r in range(1, N_RUNS + 1):
            run_data = get_run(data, r)
            cpu_vals = get_vals(run_data, 'cpu')
            m = np.mean(cpu_vals) if cpu_vals else 0
            s = np.std(cpu_vals)  if cpu_vals else 0
            means.append(m)
            stds.append(s)
            ax4.bar(r-1, m, yerr=s, color=C_MEASURE,
                    edgecolor=EDGE, linewidth=0.8, capsize=5,
                    error_kw={'ecolor': EDGE, 'linewidth': 1.2})
            ax4.text(r-1, m + s + 0.5, f'{m:.1f}%',
                     ha='center', fontsize=8, fontweight='bold')
        ax4.set_title(f'{mode} — {N_RUNS} Runs CPU %', fontweight='bold')
        ax4.set_xticks(range(N_RUNS))
        ax4.set_xticklabels([f'Run {i+1}' for i in range(N_RUNS)])
        ax4.set_ylabel('CPU %')

        # ── Temperature Timeline ──
        ax5 = fig.add_subplot(inner[1, 2])
        all_temp = get_vals(data, 'temp')
        ax5.plot(all_temp, color='#FF9999', linewidth=1.2)
        ax5.axvline(x=w_len, color='gray', linestyle='--', linewidth=1)
        ax5.set_title('Temperature (°C)', fontweight='bold')
        ax5.set_xlabel('Time (s)')
        ax5.set_ylabel('°C')

        # ── N Runs Latency ──
        ax6 = fig.add_subplot(inner[1, 3])
        lat_means, lat_stds = [], []
        for r in range(1, N_RUNS + 1):
            run_data = get_run(data, r)
            lv = get_vals(run_data, 'latency_ms')
            lm = np.mean(lv) if lv else 0
            ls = np.std(lv)  if lv else 0
            lat_means.append(lm)
            lat_stds.append(ls)
            ax6.bar(r-1, lm, yerr=ls, color=color,
                    edgecolor=EDGE, linewidth=0.8, capsize=5,
                    error_kw={'ecolor': EDGE, 'linewidth': 1.2})
            ax6.text(r-1, lm + ls + 0.1, f'{lm:.1f}ms',
                     ha='center', fontsize=8, fontweight='bold')
        ax6.set_title(f'{mode} — {N_RUNS} Runs Latency', fontweight='bold')
        ax6.set_xticks(range(N_RUNS))
        ax6.set_xticklabels([f'Run {i+1}' for i in range(N_RUNS)])
        ax6.set_ylabel('ms')

        all_latency = get_vals(get_phase(data, 'measure'), 'latency_ms')
        summary[mode] = {
            'cpu_mean'    : np.mean(means)      if means      else 0,
            'cpu_std'     : np.std(means)        if means      else 0,
            'warmup_sec'  : w_len,
            'temp_max'    : max(all_temp)         if all_temp   else 0,
            'latency_mean': np.mean(all_latency)  if all_latency else 0,
            'latency_std' : np.std(all_latency)   if all_latency else 0,
        }

    # ── Summary table ──
    ax_t = fig.add_subplot(outer[len(MODES)])
    ax_t.axis('off')
    ax_t.set_title(
        f'Summary Table  |  mean ± std across {N_RUNS} runs  |  green = best per metric',
        fontweight='bold', fontsize=9, pad=15)

    rows = ['CPU Mean %', 'CPU Std %', 'Warmup (s)', 'Max Temp (°C)',
            'Latency Mean (ms)', 'Latency Std (ms)']
    keys = ['cpu_mean', 'cpu_std', 'warmup_sec', 'temp_max',
            'latency_mean', 'latency_std']
    tdata = [[f"{summary[m][k]:.2f}" for m in MODES] for k in keys]

    cell_colors = []
    for i, k in enumerate(keys):
        rc = ['#FFFFFF'] * 3
        try:
            nums     = [float(tdata[i][j]) for j in range(3)]
            best     = int(np.argmin(nums))
            rc[best] = '#D4EDDA'
        except Exception:
            pass
        cell_colors.append(rc)

    tbl = ax_t.table(
        cellText    = tdata,
        rowLabels   = rows,
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