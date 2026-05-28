import os
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib import rcParams
from datetime import datetime

rcParams.update({
    'font.family': 'serif', 'font.size': 10,
    'axes.titlesize': 11, 'axes.labelsize': 10,
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
EDGE         = '#888888'
N_RUNS       = 5
LOG_DIR      = '/workspace/logs'

OUT_GENERAL  = f'{LOG_DIR}/power_benchmark_general.png'
OUT_LATENCY  = f'{LOG_DIR}/power_latency.png'  # İsim düzeltildi

LAT_KEYS     = ['acq_ms', 'process_ms', 'transport_ms', 'decision_ms']
LAT_LABELS   = ['Acquisition', 'Processing', 'Transport', 'Decision']
LAT_COLORS   = ['#A8D8EA', '#AA96DA', '#FCBAD3', '#FFFFD2']


def load_csv(mode):
    path = f'{LOG_DIR}/power_benchmark_{mode}.csv'
    if not os.path.exists(path): return None
    data = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = {}
            for k, v in row.items():
                try: d[k] = float(v)
                except: d[k] = v
            data.append(d)
    return data

def get_vals(data, key):
    return [d[key] for d in data if d.get(key) not in (None, '', 'None') and not (isinstance(d[key], float) and np.isnan(d[key]))]

def get_phase(data, phase):
    return [d for d in data if d.get('phase') == phase]

def get_run(data, run_idx):
    return [d for d in data if d.get('phase') == 'measure' and int(d.get('run', 0)) == run_idx]

def get_time_series(data, full_data, key):
    if not data or not full_data: return [], []
    t0 = datetime.fromisoformat(full_data[0]['timestamp'])
    times, vals = [], []
    for d in data:
        v = d.get(key)
        if v not in (None, '', 'None') and not (isinstance(v, float) and np.isnan(v)):
            t = (datetime.fromisoformat(d['timestamp']) - t0).total_seconds()
            times.append(t)
            vals.append(float(v))
    return times, vals

def get_phase_times(data, phase, run=None):
    subset = get_run(data, run) if run else get_phase(data, phase)
    if not subset: return 0, 0
    t0 = datetime.fromisoformat(data[0]['timestamp'])
    t_start = (datetime.fromisoformat(subset[0]['timestamp']) - t0).total_seconds()
    t_end = (datetime.fromisoformat(subset[-1]['timestamp']) - t0).total_seconds()
    return t_start, t_end

def calc_stats(vals):
    if not vals: return {'max': 0, 'mean': 0, 'min': 0, 'std': 0}
    return {'max': np.max(vals), 'mean': np.mean(vals), 'min': np.min(vals), 'std': np.std(vals)}

def main():
    missing = [f'{LOG_DIR}/power_benchmark_{m}.csv' for m in MODES if not os.path.exists(f'{LOG_DIR}/power_benchmark_{m}.csv')]
    if missing:
        print(f'Missing files: {missing}')
        return

    all_data = {m: load_csv(m) for m in MODES}
    summary = {}
    run_means = {m: {'cpu': [], 'gpu': [], 'pow': [], 'ram': []} for m in MODES}

    # İstatistikleri Toplama
    for mode in MODES:
        data = all_data[mode]
        measure_data = get_phase(data, 'measure')
        
        for r in range(1, N_RUNS + 1):
            r_data = get_run(data, r)
            run_means[mode]['cpu'].append(np.mean(get_vals(r_data, 'cpu')) if get_vals(r_data, 'cpu') else 0)
            run_means[mode]['gpu'].append(np.mean(get_vals(r_data, 'gpu')) if get_vals(r_data, 'gpu') else 0)
            run_means[mode]['pow'].append(np.mean(get_vals(r_data, 'power_mw')) if get_vals(r_data, 'power_mw') else 0)
            run_means[mode]['ram'].append(np.mean(get_vals(r_data, 'ram_used')) if get_vals(r_data, 'ram_used') else 0)

        
        summary[mode] = {
            'cpu':  calc_stats(get_vals(measure_data, 'cpu')),
            'gpu':  calc_stats(get_vals(measure_data, 'gpu')),
            'ram':  calc_stats(get_vals(measure_data, 'ram_used')),
            'pow':  calc_stats(get_vals(measure_data, 'power_mw')),
            'temp': calc_stats(get_vals(data, 'temp')), # Tüm test sürecindeki (ısınma dahil) sıcaklık profili
            
            # Gecikme verileri 
            'e2e_mean'      : np.mean(get_vals(measure_data, 'e2e_ms')) if get_vals(measure_data, 'e2e_ms') else 0,
            'e2e_std'       : np.std(get_vals(measure_data, 'e2e_ms')) if get_vals(measure_data, 'e2e_ms') else 0,
            'acq_mean'      : np.mean(get_vals(measure_data, 'acq_ms')) if get_vals(measure_data, 'acq_ms') else 0,
            'process_mean'  : np.mean(get_vals(measure_data, 'process_ms')) if get_vals(measure_data, 'process_ms') else 0,
            'transport_mean': np.mean(get_vals(measure_data, 'transport_ms')) if get_vals(measure_data, 'transport_ms') else 0,
            'decision_mean' : np.mean(get_vals(measure_data, 'decision_ms')) if get_vals(measure_data, 'decision_ms') else 0,
        }

#figure 1
    fig1 = plt.figure(figsize=(24, 25))
    outer1 = gridspec.GridSpec(5, 1, figure=fig1, hspace=0.5, height_ratios=[2.5, 2.5, 2.5, 2.5, 4.0])
    fig1.suptitle('Power Mode Benchmark — Hardware & Resource Utilization\nJetson Orin Nano (7W, 15W, 25W)', fontsize=16, fontweight='bold', y=0.92)

    metrics_def = [
        ('cpu', 'CPU (%)', '#34495E'), ('gpu', 'GPU (%)', '#9B59B6'), 
        ('ram_used', 'RAM (MB)', '#2980B9'), ('power_mw', 'Power (mW)', '#F39C12'), 
        ('temp', 'Temp (°C)', '#C0392B')
    ]

    for mi, mode in enumerate(MODES):
        data = all_data[mode]
        inner = gridspec.GridSpecFromSubplotSpec(1, 5, subplot_spec=outer1[mi], wspace=0.3)
        
        ws, we = get_phase_times(data, 'warmup')
        cs, ce = get_phase_times(data, 'cooldown')
        runs_times = [get_phase_times(data, 'measure', r) for r in range(1, N_RUNS+1)]

        for col, (m_key, m_label, m_color) in enumerate(metrics_def):
            ax = fig1.add_subplot(inner[col])
            t_vals, y_vals = get_time_series(data, data, m_key)
            ax.plot(t_vals, y_vals, color=m_color, linewidth=1.2)
            
            ax.axvspan(ws, we, alpha=0.15, color=C_WARMUP, label='Warmup' if col==0 else "")
            for i, (rs, re) in enumerate(runs_times):
                ax.axvspan(rs, re, alpha=0.15, color=C_MEASURE, label='Measure' if col==0 and i==0 else "")
            if ce > cs:
                ax.axvspan(cs, ce, alpha=0.15, color=C_COOLDOWN, label='Cooldown' if col==0 else "")
                
            ax.set_title(f'{mode} — {m_label}', fontweight='bold')
            ax.set_xlabel('Time (s)')
            if col == 0: ax.legend(fontsize=8, loc='upper left')

    inner_bar = gridspec.GridSpecFromSubplotSpec(1, 4, subplot_spec=outer1[3], wspace=0.3)
    bar_metrics = [('cpu', 'Mean CPU (%)'), ('gpu', 'Mean GPU (%)'), ('pow', 'Mean Power (mW)'), ('ram', 'Mean RAM (MB)')]
    
    x = np.arange(N_RUNS)
    w = 0.25
    for i, (b_key, b_label) in enumerate(bar_metrics):
        ax = fig1.add_subplot(inner_bar[i])
        for mi, (mode, color) in enumerate(zip(MODES, COLORS)):
            ax.bar(x + mi*w - w, run_means[mode][b_key], width=w, label=mode, color=color, edgecolor=EDGE, linewidth=0.8)
        ax.set_title(f'{b_label} per Run', fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([f'Run {r}' for r in range(1, N_RUNS+1)])
        if i == 0: ax.legend()

    
    ax_t1 = fig1.add_subplot(outer1[4])
    ax_t1.axis('off')
    ax_t1.set_title('Detailed Hardware Statistical Analysis (Measure Phase)', fontweight='bold', fontsize=12, pad=15)
    
    metrics_info = [
        ('cpu', 'CPU (%)'),
        ('gpu', 'GPU (%)'),
        ('ram', 'RAM (MB)'),
        ('pow', 'Power (mW)'),
        ('temp', 'Temp (°C)')
    ]
    stat_keys = ['max', 'mean', 'min', 'std']
    stat_labels = ['Max', 'Avg', 'Min', 'Std Dev']

    rows1 = []
    tdata1 = []
    cell_colors1 = []

    for m_key, m_label in metrics_info:
        for s_key, s_label in zip(stat_keys, stat_labels):
            rows1.append(f"{m_label} - {s_label}")
            row_data = [f"{summary[mode][m_key][s_key]:.2f}" for mode in MODES]
            tdata1.append(row_data)
            
            rc = ['#FFFFFF'] * 3
            try:
                nums = [float(val) for val in row_data]
                
                best_idx = int(np.argmin(nums))
                rc[best_idx] = '#D4EDDA'
            except:
                pass
            cell_colors1.append(rc)

    tbl1 = ax_t1.table(cellText=tdata1, rowLabels=rows1, colLabels=MODES, cellLoc='center', loc='center', cellColours=cell_colors1)
    tbl1.auto_set_font_size(False)
    tbl1.set_fontsize(10)
    tbl1.scale(1, 1.4) 
    
    
    for (r, c), cell in tbl1.get_celld().items():
        cell.set_edgecolor('#CCCCCC')
        if r == 0: 
            cell.set_facecolor('#E8F0FE')
            cell.set_text_props(fontweight='bold')
        if c == -1: 
            cell.set_facecolor('#F5F5F5')
            cell.set_text_props(fontweight='bold')
            if (r - 1) % 4 == 0:  
                cell.set_facecolor('#EFEFEF')

    fig1.savefig(OUT_GENERAL, dpi=150, bbox_inches='tight', facecolor='white')
    print(f'General Hardware report saved: {OUT_GENERAL}')

   #figure 2
    fig2 = plt.figure(figsize=(16, 10))
    outer2 = gridspec.GridSpec(2, 1, figure=fig2, hspace=0.4, height_ratios=[2, 1])
    fig2.suptitle('Pipeline Latency Breakdown\nAlgorithm & Transport Analysis', fontsize=14, fontweight='bold', y=0.95)

    inner_lat = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=outer2[0], wspace=0.3)

    # 1. Stacked Bar (Kümülatif Gecikme)
    ax_stack = fig2.add_subplot(inner_lat[0])
    x_lat = np.arange(len(MODES))
    bottom = np.zeros(len(MODES))
    for key, label, lcolor in zip(LAT_KEYS, LAT_LABELS, LAT_COLORS):
        vals = [summary[m][f'{key.replace("_ms","")}_mean'] for m in MODES]
        bars = ax_stack.bar(x_lat, vals, bottom=bottom, label=label, color=lcolor, edgecolor=EDGE, linewidth=0.8, width=0.5)
        for bar, v, b in zip(bars, vals, bottom):
            if v > 1.0:
                ax_stack.text(bar.get_x() + bar.get_width()/2, b + v/2, f'{v:.1f}', ha='center', va='center', fontsize=8, fontweight='bold')
        bottom += np.array(vals)
    ax_stack.set_title('Stacked Pipeline Breakdown (ms)', fontweight='bold')
    ax_stack.set_xticks(x_lat)
    ax_stack.set_xticklabels(MODES, fontweight='bold')
    ax_stack.set_ylabel('ms')
    ax_stack.legend(fontsize=9, loc='upper right')

    # Grouped Bar 
    ax_group = fig2.add_subplot(inner_lat[1])
    x_stage = np.arange(len(LAT_KEYS))
    w_lat = 0.25
    for mi, (mode, color) in enumerate(zip(MODES, COLORS)):
        vals = [summary[mode][f'{k.replace("_ms","")}_mean'] for k in LAT_KEYS]
        bars = ax_group.bar(x_stage + mi*w_lat - w_lat, vals, width=w_lat, label=mode, color=color, edgecolor=EDGE, linewidth=0.8)
        for bar, v in zip(bars, vals):
            if v > 0.5:
                ax_group.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f'{v:.1f}', ha='center', fontsize=8)
    ax_group.set_title('Per-Stage Comparison Across Power Modes', fontweight='bold')
    ax_group.set_xticks(x_stage)
    ax_group.set_xticklabels(LAT_LABELS, fontweight='bold')
    ax_group.set_ylabel('ms')
    ax_group.legend(fontsize=9)

    
    ax_t2 = fig2.add_subplot(outer2[1])
    ax_t2.axis('off')
    rows2 = ['Total E2E (ms)', 'Acquisition (ms)', 'Processing (Fusion) (ms)', 'Transport (ms)', 'Decision (ms)']
    keys_mean = ['e2e_mean', 'acq_mean', 'process_mean', 'transport_mean', 'decision_mean']
    keys_std  = ['e2e_std', 'acq_std', 'process_std', 'transport_std', 'decision_std']
    
    tdata2 = []
    for km, ks in zip(keys_mean, keys_std):
        row = [f"{summary[m][km]:.2f} ± {summary[m][ks]:.2f}" if km == 'e2e_mean' else f"{summary[m][km]:.2f}" for m in MODES]
        tdata2.append(row)

    tbl2 = ax_t2.table(cellText=tdata2, rowLabels=rows2, colLabels=MODES, cellLoc='center', loc='center')
    tbl2.auto_set_font_size(False)
    tbl2.set_fontsize(11)
    tbl2.scale(1, 2.5)
    for (r, c), cell in tbl2.get_celld().items():
        cell.set_edgecolor('#CCCCCC')
        if r == 0: cell.set_facecolor('#E8F0FE'); cell.set_text_props(fontweight='bold')
        elif c == -1: cell.set_facecolor('#FFF3CD'); cell.set_text_props(fontweight='bold')

    fig2.savefig(OUT_LATENCY, dpi=150, bbox_inches='tight', facecolor='white')
    print(f'Latency Breakdown report saved: {OUT_LATENCY}')

if __name__ == '__main__':
    main()