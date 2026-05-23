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

LAT_KEYS   = ['acq_ms', 'process_ms', 'transport_ms', 'decision_ms']
LAT_LABELS = ['Acquisition', 'Processing', 'Transport', 'Decision']
LAT_COLORS = ['#A8D8EA', '#AA96DA', '#FCBAD3', '#FFFFD2']


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
        return

    all_data = {m: load_csv(m) for m in MODES}

    # ── Layout: per-mode rows + latency comparison + summary table ──
    fig   = plt.figure(figsize=(20, 8 * len(MODES) + 14))
    outer = gridspec.GridSpec(
        len(MODES) + 2, 1, figure=fig,
        hspace=0.7,
        height_ratios=[3.0] * len(MODES) + [2.5, 1.5])

    fig.suptitle(
        'Power Mode Benchmark — Jetson Orin Nano\n'
        f'7W vs 15W vs 25W  |  N={N_RUNS} runs × {MEASURE_SEC}s  |  '
        f'Stability threshold: 8%',
        fontsize=13, fontweight='bold', y=1.01)

    summary = {}

    # ── Per-mode plots (mevcut yapı korundu) ──
    for mi, (mode, color) in enumerate(zip(MODES, COLORS)):
        data  = all_data[mode]
        inner = gridspec.GridSpecFromSubplotSpec(
            2, 4, subplot_spec=outer[mi],
            hspace=0.5, wspace=0.4)

        wd    = get_phase(data, 'warmup')
        cd    = get_phase(data, 'cooldown')
        w_len = len(wd)
        c_len = len(cd)

        # CPU Timeline
        ax1 = fig.add_subplot(inner[0, :2])
        ax1.axvspan(0, w_len, alpha=0.15, color=C_WARMUP, label='Warmup')
        for r in range(N_RUNS):
            s = w_len + r * MEASURE_SEC
            ax1.axvspan(s, s + MEASURE_SEC, alpha=0.15,
                        color=C_MEASURE, label='Measure' if r == 0 else '')
        ax1.axvspan(w_len + N_RUNS * MEASURE_SEC,
                    w_len + N_RUNS * MEASURE_SEC + c_len,
                    alpha=0.15, color=C_COOLDOWN, label='Cool-down')
        ax1.plot(get_vals(data, 'cpu'), color=color, linewidth=1.2, label='CPU %')
        ax1.axvline(x=w_len, color='gray', linestyle='--', linewidth=1, label='Warmup end')
        ax1.set_title(f'{mode} — CPU % Timeline', fontweight='bold')
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('CPU %')
        ax1.legend(fontsize=7, loc='upper right')

        # Warmup % Change
        ax2 = fig.add_subplot(inner[0, 2])
        ax2.plot(sliding_change(wd, 'cpu'), color=color, linewidth=1.2)
        ax2.axhline(y=8, color=C_THRESH, linestyle='--', linewidth=1.2, label='8% threshold')
        ax2.set_title('Warmup % Change', fontweight='bold')
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('% Change')
        ax2.legend(fontsize=7)

        # E2E Latency Timeline
        ax3 = fig.add_subplot(inner[0, 3])
        e2e_vals = get_vals(data, 'e2e_ms')
        if e2e_vals:
            ax3.plot(e2e_vals, color=color, linewidth=0.8, alpha=0.8)
        else:
            ax3.text(0.5, 0.5, 'No data', transform=ax3.transAxes,
                     ha='center', va='center', fontsize=9, color='gray')
        ax3.set_title('E2E Latency (ms)', fontweight='bold')
        ax3.set_xlabel('Time (s)')
        ax3.set_ylabel('ms')

        # N Runs CPU
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

        # Temperature Timeline
        ax5 = fig.add_subplot(inner[1, 2])
        ax5.plot(get_vals(data, 'temp'), color='#FF9999', linewidth=1.2)
        ax5.axvline(x=w_len, color='gray', linestyle='--', linewidth=1)
        ax5.set_title('Temperature (°C)', fontweight='bold')
        ax5.set_xlabel('Time (s)')
        ax5.set_ylabel('°C')

        # N Runs E2E Latency
        ax6 = fig.add_subplot(inner[1, 3])
        lat_means, lat_stds = [], []
        for r in range(1, N_RUNS + 1):
            run_data = get_run(data, r)
            lv = get_vals(run_data, 'e2e_ms')
            lm = np.mean(lv) if lv else 0
            ls = np.std(lv)  if lv else 0
            lat_means.append(lm)
            lat_stds.append(ls)
            ax6.bar(r-1, lm, yerr=ls, color=color,
                    edgecolor=EDGE, linewidth=0.8, capsize=5,
                    error_kw={'ecolor': EDGE, 'linewidth': 1.2})
            ax6.text(r-1, lm + ls + 0.1, f'{lm:.1f}ms',
                     ha='center', fontsize=8, fontweight='bold')
        ax6.set_title(f'{mode} — {N_RUNS} Runs E2E Latency', fontweight='bold')
        ax6.set_xticks(range(N_RUNS))
        ax6.set_xticklabels([f'Run {i+1}' for i in range(N_RUNS)])
        ax6.set_ylabel('ms')

        measure_data = get_phase(data, 'measure')
        summary[mode] = {
            'cpu_mean'    : np.mean(means) if means else 0,
            'cpu_std'     : np.std(means)  if means else 0,
            'warmup_sec'  : w_len,
            'temp_max'    : max(get_vals(data, 'temp')) if get_vals(data, 'temp') else 0,
            'e2e_mean'    : np.mean(get_vals(measure_data, 'e2e_ms'))      if get_vals(measure_data, 'e2e_ms')      else 0,
            'e2e_std'     : np.std(get_vals(measure_data, 'e2e_ms'))       if get_vals(measure_data, 'e2e_ms')      else 0,
            'acq_mean'    : np.mean(get_vals(measure_data, 'acq_ms'))      if get_vals(measure_data, 'acq_ms')      else 0,
            'process_mean': np.mean(get_vals(measure_data, 'process_ms'))  if get_vals(measure_data, 'process_ms')  else 0,
            'transport_mean': np.mean(get_vals(measure_data, 'transport_ms')) if get_vals(measure_data, 'transport_ms') else 0,
            'decision_mean' : np.mean(get_vals(measure_data, 'decision_ms'))  if get_vals(measure_data, 'decision_ms')  else 0,
        }

    # ── Latency Karşılaştırma Bölümü ──
    lat_outer = gridspec.GridSpecFromSubplotSpec(
        1, 3, subplot_spec=outer[len(MODES)],
        wspace=0.4)

    # 1. Stacked Bar: Latency Breakdown per Power Mode
    ax_stack = fig.add_subplot(lat_outer[0])
    x      = np.arange(len(MODES))
    bottom = np.zeros(len(MODES))
    for key, label, lcolor in zip(LAT_KEYS, LAT_LABELS, LAT_COLORS):
        vals = [summary[m][f'{key.replace("_ms","")}_mean'] for m in MODES]
        bars = ax_stack.bar(x, vals, bottom=bottom,
                            label=label, color=lcolor,
                            edgecolor=EDGE, linewidth=0.8, width=0.5)
        for bar, v, b in zip(bars, vals, bottom):
            if v > 1.0:
                ax_stack.text(bar.get_x() + bar.get_width()/2,
                              b + v/2, f'{v:.1f}',
                              ha='center', va='center',
                              fontsize=7, fontweight='bold')
        bottom += np.array(vals)
    ax_stack.set_title('Latency Breakdown\nper Power Mode', fontweight='bold')
    ax_stack.set_xticks(x)
    ax_stack.set_xticklabels(MODES)
    ax_stack.set_ylabel('ms')
    ax_stack.legend(fontsize=7, loc='upper right')

    # 2. E2E Karşılaştırma Bar
    ax_e2e = fig.add_subplot(lat_outer[1])
    e2e_means = [summary[m]['e2e_mean'] for m in MODES]
    e2e_stds  = [summary[m]['e2e_std']  for m in MODES]
    best_e2e  = int(np.argmin(e2e_means))
    for i, (mode, color) in enumerate(zip(MODES, COLORS)):
        ec = '#E63946' if i == best_e2e else EDGE
        lw = 2.5       if i == best_e2e else 0.8
        ax_e2e.bar(i, e2e_means[i], yerr=e2e_stds[i],
                   color=color, edgecolor=ec, linewidth=lw,
                   capsize=5, width=0.5,
                   error_kw={'ecolor': EDGE, 'linewidth': 1.2})
        ax_e2e.text(i, e2e_means[i] + e2e_stds[i] + 0.5,
                    f'{e2e_means[i]:.1f}ms',
                    ha='center', fontsize=8, fontweight='bold')
    ax_e2e.set_title('E2E Latency\nper Power Mode (mean ± std)', fontweight='bold')
    ax_e2e.set_xticks(range(len(MODES)))
    ax_e2e.set_xticklabels(MODES)
    ax_e2e.set_ylabel('ms')

    # 3. Per-Stage Grouped Bar: her aşama için 3 mod
    ax_stage = fig.add_subplot(lat_outer[2])
    x_stage = np.arange(len(LAT_KEYS))
    w       = 0.25
    for mi, (mode, color) in enumerate(zip(MODES, COLORS)):
        vals = [summary[mode][f'{k.replace("_ms","")}_mean'] for k in LAT_KEYS]
        bars = ax_stage.bar(x_stage + mi*w, vals,
                            width=w, label=mode,
                            color=color, edgecolor=EDGE, linewidth=0.8)
        for bar, v in zip(bars, vals):
            if v > 0.5:
                ax_stage.text(bar.get_x() + bar.get_width()/2,
                              bar.get_height() + 0.2,
                              f'{v:.1f}', ha='center', fontsize=7)
    ax_stage.set_title('Per-Stage Latency\nAcross Power Modes', fontweight='bold')
    ax_stage.set_xticks(x_stage + w)
    ax_stage.set_xticklabels(LAT_LABELS, fontsize=8)
    ax_stage.set_ylabel('ms')
    ax_stage.legend(fontsize=7)

    # ── Summary Table ──
    ax_t = fig.add_subplot(outer[len(MODES) + 1])
    ax_t.axis('off')
    ax_t.set_title(
        f'Summary Table  |  mean ± std across {N_RUNS} runs  |  green = best per metric',
        fontweight='bold', fontsize=9, pad=15)

    rows = ['CPU Mean %', 'CPU Std %', 'Warmup (s)', 'Max Temp (°C)',
            'E2E Mean (ms)', 'E2E Std (ms)',
            'Acq Mean (ms)', 'Process Mean (ms)',
            'Transport Mean (ms)', 'Decision Mean (ms)']
    keys = ['cpu_mean', 'cpu_std', 'warmup_sec', 'temp_max',
            'e2e_mean', 'e2e_std',
            'acq_mean', 'process_mean',
            'transport_mean', 'decision_mean']

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