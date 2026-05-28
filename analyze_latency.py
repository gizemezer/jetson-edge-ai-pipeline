import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Akademik Stil Ayarları
plt.style.use('ggplot')
plt.rcParams.update({'font.size': 12, 'font.family': 'serif'})

df = pd.read_csv('logs/benchmark.csv')

# İstatistikleri hesapla
metrics = ['acq', 'proc', 'trans', 'dec', 'e2e']
stats = df[metrics].describe().transpose()[['mean', 'min', 'max', 'std']]
stats.rename(columns={'mean': 'Avg', 'min': 'Min', 'max': 'Max', 'std': 'Std'}, inplace=True)

# %TD (Total Distribution) hesapla
stats['%TD'] = (stats['Avg'] / stats['Avg']['e2e']) * 100

# 1. GRAFİK ÜRETİMİ (2x2 Grid)
fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(2, 2)

# Grafik A: Latency Kırılımı (Bar)
ax1 = fig.add_subplot(gs[0, 0])
stats.drop('e2e')['Avg'].plot(kind='bar', yerr=stats.drop('e2e')['Std'], capsize=4, 
                              color=['#4e79a7', '#f28e2b', '#e15759', '#76b7b2'], ax=ax1)
ax1.set_title('Pipeline Latency Breakdown (ms)', fontweight='bold')
ax1.set_ylabel('Latency (ms)')

# Grafik B: End-to-End Zaman Çizelgesi (Timeline)
ax2 = fig.add_subplot(gs[0, 1])
df['e2e'].plot(color='#59a14f', ax=ax2, alpha=0.7)
ax2.set_title('E2E Latency Stability Over Time', fontweight='bold')
ax2.set_ylabel('ms')

# 2. TABLO ÜRETİMİ
ax3 = fig.add_subplot(gs[1, :])
ax3.axis('off')
table = ax3.table(cellText=stats.round(2).values, colLabels=stats.columns, 
                  rowLabels=stats.index, cellLoc='center', loc='center')
table.scale(1, 1.5)

plt.tight_layout()
plt.savefig('/workspace/logs/thesis_final_results.png', dpi=300)
print("Report saved as 'latency_mock.png'")
















