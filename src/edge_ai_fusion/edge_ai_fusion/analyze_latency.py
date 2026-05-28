import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MultipleLocator
import matplotlib.patches as mpatches
import sys
import os

# ── Renk Paleti (Tez için pastel/akademik) ──────────────────────────────────
COLORS = {
    'acq':   '#A8C8E8',
    'proc':  '#A8D8B9',
    'trans': '#F7C59F',
    'dec':   '#C9B8E8',
    'e2e':   '#F2A7B0',
}
EDGE_COLORS = {k: '#' + ''.join(f'{max(0, int(v[1:][i*2:i*2+2], 16)-40):02X}' for i in range(3))
               for k, v in COLORS.items()}
BG        = '#FAFAFA'
PANEL_BG  = '#FFFFFF'
GRID_CLR  = '#E8E8E8'
TEXT_CLR  = '#2D2D2D'
FONT_BODY = 'DejaVu Sans'

LABELS = {
    'acq':   'Acquisition\n(Acq)',
    'proc':  'Fusion Proc.\n(Proc)',
    'trans': 'Transport/Wait\n(Trans)',
    'dec':   'Decision\n(Dec)',
    'e2e':   'End-to-End\n(E2E)',
}
METRICS = list(LABELS.keys())

# ── Veri yükle ───────────────────────────────────────────────────────────────
def load_data(csv_path):
    df = pd.read_csv(csv_path)
    for m in METRICS:
        df = df[df[m] >= 0]
    return df

# ── İstatistik tablosu ────────────────────────────────────────────────────────
def compute_stats(df):
    rows = []
    for m in METRICS:
        s = df[m]
        rows.append({
            'Metric':      m.upper(),
            'Min (ms)':    f'{s.min():.2f}',
            'Max (ms)':    f'{s.max():.2f}',
            'Mean (ms)':   f'{s.mean():.2f}',
            'Median (ms)': f'{s.median():.2f}',
            'Std Dev':     f'{s.std():.2f}',
            'P95 (ms)':    f'{s.quantile(0.95):.2f}',
            'P99 (ms)':    f'{s.quantile(0.99):.2f}',
            'CV (%)':      f'{(s.std()/s.mean()*100):.1f}',
        })
    return pd.DataFrame(rows)

# ── Çizim ────────────────────────────────────────────────────────────────────
def plot(df, out_path='benchmark_analysis.png'):
    stats = compute_stats(df)
    n = len(df)

    fig = plt.figure(figsize=(20, 26), facecolor=BG)
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.975, 'Edge AI Pipeline — Latency Benchmark Analysis',
             ha='center', va='top', fontsize=22, fontweight='bold',
             color=TEXT_CLR, fontfamily=FONT_BODY)
    fig.text(0.5, 0.962, f'N = {n:,} samples  |  5 pipeline stages',
             ha='center', va='top', fontsize=12, color='#777777', fontfamily=FONT_BODY)

    gs = gridspec.GridSpec(4, 3, figure=fig,
                           top=0.95, bottom=0.02,
                           hspace=0.42, wspace=0.32,
                           left=0.07, right=0.97)

    # ── 1. Violin Plot ────────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.set_facecolor(PANEL_BG)
    data_list = [df[m].values for m in METRICS]
    parts = ax1.violinplot(data_list, positions=range(len(METRICS)),
                           showmedians=True, showextrema=True, widths=0.65)
    for pc, m in zip(parts['bodies'], METRICS):
        pc.set_facecolor(COLORS[m])
        pc.set_edgecolor(EDGE_COLORS[m])
        pc.set_alpha(0.85)
    parts['cmedians'].set_colors('#333333')
    parts['cmedians'].set_linewidth(2)
    for part in ['cbars', 'cmins', 'cmaxes']:
        parts[part].set_colors('#888888')
    ax1.set_xticks(range(len(METRICS)))
    ax1.set_xticklabels([LABELS[m] for m in METRICS], fontsize=10, color=TEXT_CLR)
    ax1.set_ylabel('Latency (ms)', fontsize=11, color=TEXT_CLR)
    ax1.set_title('Distribution — Violin Plot', fontsize=13, fontweight='bold',
                  color=TEXT_CLR, pad=10)
    ax1.yaxis.grid(True, color=GRID_CLR, linewidth=0.8)
    ax1.set_axisbelow(True)
    ax1.spines[['top', 'right']].set_visible(False)

    # ── 2. Box Plot ───────────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.set_facecolor(PANEL_BG)
    bp = ax2.boxplot(data_list, patch_artist=True, notch=False,
                     medianprops=dict(color='#333333', linewidth=2),
                     whiskerprops=dict(color='#888888'),
                     capprops=dict(color='#888888'),
                     flierprops=dict(marker='o', markersize=2, alpha=0.3, linestyle='none'))
    for patch, m in zip(bp['boxes'], METRICS):
        patch.set_facecolor(COLORS[m])
        patch.set_edgecolor(EDGE_COLORS[m])
        patch.set_alpha(0.85)
    ax2.set_xticks(range(1, len(METRICS)+1))
    ax2.set_xticklabels([m.upper() for m in METRICS], fontsize=9, color=TEXT_CLR)
    ax2.set_ylabel('Latency (ms)', fontsize=11, color=TEXT_CLR)
    ax2.set_title('Box Plot', fontsize=13, fontweight='bold', color=TEXT_CLR, pad=10)
    ax2.yaxis.grid(True, color=GRID_CLR, linewidth=0.8)
    ax2.set_axisbelow(True)
    ax2.spines[['top', 'right']].set_visible(False)

    # ── 3. Zaman Serisi ───────────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, :])
    ax3.set_facecolor(PANEL_BG)
    x = np.arange(n)
    win = max(1, n // 200)
    for m in METRICS:
        smooth = df[m].rolling(win, center=True).mean().values
        ax3.plot(x, smooth, color=COLORS[m], linewidth=1.6, label=m.upper(), alpha=0.9)
    ax3.set_xlabel('Sample Index', fontsize=11, color=TEXT_CLR)
    ax3.set_ylabel('Latency (ms)', fontsize=11, color=TEXT_CLR)
    ax3.set_title(f'Time-Series (rolling mean, window={win})', fontsize=13,
                  fontweight='bold', color=TEXT_CLR, pad=10)
    ax3.legend(loc='upper right', framealpha=0.7, fontsize=9)
    ax3.yaxis.grid(True, color=GRID_CLR, linewidth=0.8)
    ax3.set_axisbelow(True)
    ax3.spines[['top', 'right']].set_visible(False)

    # ── 4. CDF ───────────────────────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[2, :2])
    ax4.set_facecolor(PANEL_BG)
    for m in METRICS:
        s = np.sort(df[m].values)
        cdf = np.arange(1, len(s)+1) / len(s)
        ax4.plot(s, cdf, color=COLORS[m], linewidth=2, label=m.upper())
    ax4.axhline(0.95, color='#AAAAAA', linestyle='--', linewidth=1, label='P95')
    ax4.axhline(0.99, color='#CCAAAA', linestyle=':', linewidth=1, label='P99')
    ax4.set_xlabel('Latency (ms)', fontsize=11, color=TEXT_CLR)
    ax4.set_ylabel('Cumulative Probability', fontsize=11, color=TEXT_CLR)
    ax4.set_title('Cumulative Distribution Function (CDF)', fontsize=13,
                  fontweight='bold', color=TEXT_CLR, pad=10)
    ax4.legend(fontsize=9, framealpha=0.7)
    ax4.yaxis.grid(True, color=GRID_CLR, linewidth=0.8)
    ax4.set_axisbelow(True)
    ax4.spines[['top', 'right']].set_visible(False)

    # ── 5. Stacked Bar ────────────────────────────────────────────────────────
    ax5 = fig.add_subplot(gs[2, 2])
    ax5.set_facecolor(PANEL_BG)
    stage_metrics = ['acq', 'proc', 'trans', 'dec']
    means = [df[m].mean() for m in stage_metrics]
    bottom = 0
    for m, val in zip(stage_metrics, means):
        ax5.bar(0, val, bottom=bottom, color=COLORS[m], edgecolor=EDGE_COLORS[m],
                width=0.5, label=m.upper(), alpha=0.9)
        ax5.text(0, bottom + val/2, f'{val:.1f} ms', ha='center', va='center',
                 fontsize=9, color=TEXT_CLR, fontweight='bold')
        bottom += val
    e2e_mean = df['e2e'].mean()
    ax5.axhline(e2e_mean, color=COLORS['e2e'], linestyle='--', linewidth=1.5,
                label=f'E2E mean: {e2e_mean:.1f} ms')
    ax5.set_xticks([])
    ax5.set_ylabel('Latency (ms)', fontsize=11, color=TEXT_CLR)
    ax5.set_title('Mean Stage\nBreakdown', fontsize=13,
                  fontweight='bold', color=TEXT_CLR, pad=10)
    ax5.legend(fontsize=8, framealpha=0.7, loc='upper right')
    ax5.yaxis.grid(True, color=GRID_CLR, linewidth=0.8)
    ax5.set_axisbelow(True)
    ax5.spines[['top', 'right']].set_visible(False)

    # ── 6. İstatistik Tablosu ─────────────────────────────────────────────────
    ax6 = fig.add_subplot(gs[3, :])
    ax6.set_facecolor(PANEL_BG)
    ax6.axis('off')
    col_labels = list(stats.columns)
    cell_text  = stats.values.tolist()
    tbl = ax6.table(cellText=cell_text, colLabels=col_labels,
                    loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 2.2)
    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor('#4A6FA5')
        tbl[0, j].set_text_props(color='white', fontweight='bold')
    for i, m in enumerate(METRICS):
        tbl[i+1, 0].set_facecolor(COLORS[m])
        tbl[i+1, 0].set_text_props(fontweight='bold')
        for j in range(1, len(col_labels)):
            tbl[i+1, j].set_facecolor('#F7F9FC' if i % 2 == 0 else PANEL_BG)
    ax6.set_title('Descriptive Statistics Summary', fontsize=13,
                  fontweight='bold', color=TEXT_CLR, pad=14, loc='left', x=0.01)

    plt.savefig(out_path, dpi=180, bbox_inches='tight', facecolor=BG, edgecolor='none')
    plt.close()
    print(f'✓ Saved → {out_path}')


def _make_demo_df():
    rng = np.random.default_rng(42)
    N = 1200
    acq   = rng.gamma(3, 2.5, N)
    proc  = rng.gamma(5, 1.8, N)
    trans = rng.exponential(1.2, N)
    dec   = rng.gamma(4, 1.5, N)
    e2e   = acq + proc + trans + dec + rng.normal(0, 0.5, N)
    return pd.DataFrame(dict(
        timestamp=np.arange(N) * int(1e8),
        acq=acq, proc=proc, trans=trans, dec=dec, e2e=e2e
    ))


# ── ROS2 node entry point ─────────────────────────────────────────────────────
def main(args=None):
    """
    ROS2 entry point.
    Kullanım (ros2 run):  ros2 run <paket> analyze_latency
    CSV yolu ve çıktı yolu environment variable ile ayarlanabilir:
        BENCHMARK_CSV=/workspace/logs/benchmark.csv
        BENCHMARK_OUT=/workspace/logs/benchmark_analysis.png
    """
    csv_path = os.environ.get('BENCHMARK_CSV', '/workspace/logs/benchmark.csv')
    out_path = os.environ.get('BENCHMARK_OUT', '/workspace/logs/benchmark_analysis.png')

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if not os.path.exists(csv_path):
        print(f'[WARN] {csv_path} bulunamadı — demo verisi kullanılıyor.')
        df = _make_demo_df()
    else:
        print(f'[INFO] CSV yükleniyor: {csv_path}')
        df = load_data(csv_path)

    print(f'[INFO] {len(df):,} satır işleniyor...')
    plot(df, out_path)


# ── Standalone script entry point ────────────────────────────────────────────
if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('BENCHMARK_CSV', 'benchmark.csv')
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('BENCHMARK_OUT', 'benchmark_analysis.png')

    if not os.path.exists(csv_path):
        print(f'⚠  {csv_path} bulunamadı — demo verisi üretiliyor...')
        df = _make_demo_df()
    else:
        df = load_data(csv_path)

    plot(df, out_path)