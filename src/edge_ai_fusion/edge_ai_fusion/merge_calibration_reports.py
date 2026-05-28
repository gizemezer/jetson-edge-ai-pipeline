import os
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams

# ── Akademik Tez Formatı ──
rcParams.update({
    'font.family': 'serif', 'font.size': 10,
    'axes.titlesize': 11, 'axes.labelsize': 10,
    'axes.grid': True, 'grid.color': '#EEEEEE',
    'grid.linewidth': 0.8, 'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.spines.top': False, 'axes.spines.right': False,
})

MODES        = ['7W', '15W', '25W']
COLORS       = ['#AEC6CF', '#B5EAD7', '#FFD1A9'] # 7W (Mavi), 15W (Yeşil), 25W (Turuncu)
LOG_DIR      = '/workspace/logs'

def load_csv(mode):
    path = f'{LOG_DIR}/calibration_data_{mode}.csv'
    if not os.path.exists(path):
        return None
    
    data = {'elapsed_sec': [], 'cpu': [], 'ram_used': [], 'power_mw': [], 'temp': [], 'latency_ms': []}
    
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                data['elapsed_sec'].append(float(row['elapsed_sec']))
                data['cpu'].append(float(row['cpu']))
                data['ram_used'].append(float(row['ram_used']))
                data['power_mw'].append(float(row['power_mw']))
                data['temp'].append(float(row['temp']))
                
                lat = float(row['latency_ms']) if row['latency_ms'] and row['latency_ms'] != 'None' else 0.0
                data['latency_ms'].append(lat)
            except (ValueError, KeyError):
                continue
                
    for k in data:
        data[k] = np.array(data[k])
    return data

def main():
    # ── Verileri Yükle ──
    data_all = {mode: load_csv(mode) for mode in MODES}

    # =========================================================================
    # 1. BÖLÜM: SADE ÇİZGİ GRAFİKLERİ (calibration_graphs.png)
    # =========================================================================
    metrics_to_plot = [
        ('cpu', 'CPU Usage (%)'),
        ('ram_used', 'RAM Used (MB)'),
        ('power_mw', 'Power (mW)'),
        ('temp', 'Temperature (°C)'),
        ('latency_ms', 'Latency (ms)')
    ]

    fig, axes = plt.subplots(5, 3, figsize=(15, 14), gridspec_kw={'hspace': 0.4, 'wspace': 0.3})
    fig.suptitle('Hardware Calibration (Raw Metrics)', fontsize=16, fontweight='bold', y=0.95)

    for col_idx, mode in enumerate(MODES):
        d = data_all[mode]
        if d is None or len(d['elapsed_sec']) == 0:
            continue
            
        time_sec = d['elapsed_sec']
        color = COLORS[col_idx]
        
        for row_idx, (key, ylabel) in enumerate(metrics_to_plot):
            ax = axes[row_idx, col_idx]
            ax.plot(time_sec, d[key], color=color, linewidth=1.5)
            ax.set_title(f'{mode} - {key.replace("_", " ").upper()}', fontweight='bold')
            ax.set_xlabel('Time (s)')
            ax.set_ylabel(ylabel)
            
            # Gecikme grafiğinde çok uç değerler grafiği bozmasın diye %99'luk limiti alıyoruz
            if key == 'latency_ms' and len(d[key]) > 0:
                y_max = np.percentile(d[key], 99) * 1.2
                if y_max > 0: ax.set_ylim(0, y_max)

    graphs_path = f'{LOG_DIR}/calibration_graphs.png'
    plt.savefig(graphs_path, dpi=300, bbox_inches='tight')
    plt.close()

    # =========================================================================
    # 2. BÖLÜM: SADE VE DETAYLI İSTATİSTİK TABLOSU (calibration_table.png)
    # =========================================================================
    metrics_for_table = [
        ('cpu', 'CPU', '%', '.2f'),
        ('ram_used', 'RAM', 'MB', '.0f'),
        ('power_mw', 'Power', 'mW', '.0f'),
        ('temp', 'Temp', '°C', '.2f'),
        ('latency_ms', 'Latency', 'ms', '.2f')
    ]

    tdata = []
    row_labels = []

    # Her metrik için Mean, Std, CV hesapla
    for key, name, unit, fmt in metrics_for_table:
        r_mean, r_std, r_cv = [], [], []
        
        for mode in MODES:
            d = data_all[mode]
            if d is not None and len(d['elapsed_sec']) > 0:
                steady_idx = d['elapsed_sec'] >= 300
                if np.any(steady_idx):
                    arr = d[key][steady_idx]
                    mean_val = np.mean(arr)
                    std_val = np.std(arr)
                    cv_val = (std_val / mean_val * 100) if mean_val > 0 else 0
                    
                    r_mean.append(format(mean_val, fmt))
                    r_std.append(format(std_val, fmt))
                    r_cv.append(f"{cv_val:.2f}")
                else:
                    r_mean.append("N/A"); r_std.append("N/A"); r_cv.append("N/A")
            else:
                r_mean.append("N/A"); r_std.append("N/A"); r_cv.append("N/A")

        tdata.extend([r_mean, r_std, r_cv])
        row_labels.extend([f'{name} Mean ({unit})', f'{name} Std ({unit})', f'{name} CV (%)'])

    # Tabloyu Çizdir
    fig_tb, ax_tb = plt.subplots(figsize=(8, 8))
    ax_tb.axis('off')

    # Senin attığın ekran görüntüsündeki gibi rowLabels kullanarak sol tarafı gölgeli yapıyoruz
    tbl = ax_tb.table(
        cellText=tdata,
        rowLabels=row_labels,
        colLabels=MODES,
        cellLoc='center',
        loc='center',
        bbox=[0.3, 0, 0.7, 1] # Tablonun ekrana oturma alanı
    )
    
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    
    # Başlıkların kalın olması için
    for (r, c), cell in tbl.get_celld().items():
        if r == 0 or c == -1:
            cell.set_text_props(fontweight='bold')

    table_path = f'{LOG_DIR}/calibration_table.png'
    plt.savefig(table_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"[BAŞARILI] Grafikler oluşturuldu: {graphs_path}")
    print(f"[BAŞARILI] Tablo oluşturuldu: {table_path}")

if __name__ == '__main__':
    main()