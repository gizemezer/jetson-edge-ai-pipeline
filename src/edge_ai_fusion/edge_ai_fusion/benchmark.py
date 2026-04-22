import rclpy
from rclpy.node import Node
from edge_ai_interfaces.msg import FusedData
import numpy as np
import cv2
import time
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# Resolution constants
THERMAL_H, THERMAL_W = 192, 256
DEPTH_H,   DEPTH_W   = 720, 1280
COMMON_H,  COMMON_W  = 480, 640

# Depth thresholds (mm)
DEPTH_TOO_CLOSE = 50
DEPTH_MAX_VALID = 300

# Thermal thresholds (Celsius)
THERMAL_HOT       = 45.0
THERMAL_DANGEROUS = 65.0

# Convergence analysis frame counts
FRAME_COUNTS = [100, 300, 750, 1500]
MAX_FRAMES   = max(FRAME_COUNTS)
OUTPUT_PATH  = '/workspace/logs/resolution_benchmark.png'

class BenchmarkNode(Node):
    def __init__(self):
        super().__init__('benchmark_node')

        self.subscription = self.create_subscription(
            FusedData, '/fused/output', self.callback, 10)

        # Store all frame results
        self.results_a = []
        self.results_b = []
        self.results_c = []
        self.frame_count = 0

        self.get_logger().info(
            f'BenchmarkNode started. Collecting {MAX_FRAMES} frames...')

    # ─────────────────────────────────────────
    # Metrics
    # ─────────────────────────────────────────
    def depth_metrics(self, depth_arr):
        too_close = int(np.sum(depth_arr < DEPTH_TOO_CLOSE))
        valid     = int(np.sum((depth_arr >= DEPTH_TOO_CLOSE) & (depth_arr <= DEPTH_MAX_VALID)))
        far       = int(np.sum(depth_arr > DEPTH_MAX_VALID))
        return too_close, valid, far

    def thermal_rmse(self, original, resampled):
        resampled_back = cv2.resize(resampled, (THERMAL_W, THERMAL_H),
                                    interpolation=cv2.INTER_LINEAR)
        return float(np.sqrt(np.mean((original - resampled_back) ** 2)))

    # ─────────────────────────────────────────
    # Method A: Depth downsample → 256x192
    # ─────────────────────────────────────────
    def method_a(self, thermal, depth):
        t0         = time.perf_counter()
        depth_down = cv2.resize(depth, (THERMAL_W, THERMAL_H),
                                interpolation=cv2.INTER_NEAREST)
        elapsed    = (time.perf_counter() - t0) * 1000

        o_close, o_valid, _ = self.depth_metrics(depth)
        d_close, d_valid, _ = self.depth_metrics(depth_down)

        return {
            'time_ms'        : elapsed,
            'lost_too_close' : o_close - d_close,
            'lost_valid'     : o_valid - d_valid,
            'thermal_rmse'   : 0.0
        }

    # ─────────────────────────────────────────
    # Method B: Thermal upsample → 1280x720
    # ─────────────────────────────────────────
    def method_b(self, thermal, depth):
        t0         = time.perf_counter()
        thermal_up = cv2.resize(thermal, (DEPTH_W, DEPTH_H),
                                interpolation=cv2.INTER_LINEAR)
        elapsed    = (time.perf_counter() - t0) * 1000

        rmse = self.thermal_rmse(thermal, thermal_up)

        return {
            'time_ms'        : elapsed,
            'lost_too_close' : 0,
            'lost_valid'     : 0,
            'thermal_rmse'   : rmse
        }

    # ─────────────────────────────────────────
    # Method C: Both → 640x480
    # ─────────────────────────────────────────
    def method_c(self, thermal, depth):
        t0             = time.perf_counter()
        thermal_common = cv2.resize(thermal, (COMMON_W, COMMON_H),
                                    interpolation=cv2.INTER_LINEAR)
        depth_common   = cv2.resize(depth, (COMMON_W, COMMON_H),
                                    interpolation=cv2.INTER_NEAREST)
        elapsed        = (time.perf_counter() - t0) * 1000

        o_close, o_valid, _ = self.depth_metrics(depth)
        c_close, c_valid, _ = self.depth_metrics(depth_common)
        rmse                = self.thermal_rmse(thermal, thermal_common)

        return {
            'time_ms'        : elapsed,
            'lost_too_close' : o_close - c_close,
            'lost_valid'     : o_valid - c_valid,
            'thermal_rmse'   : rmse
        }

    # ─────────────────────────────────────────
    # ROS2 callback
    # ─────────────────────────────────────────
    def callback(self, msg: FusedData):
        if self.frame_count >= MAX_FRAMES:
            return

        thermal = np.frombuffer(msg.thermal.data, dtype=np.float32)
        thermal = thermal.reshape((msg.thermal.height, msg.thermal.width))

        depth = np.frombuffer(msg.depth.data, dtype=np.uint16)
        depth = depth.reshape((msg.depth.height, msg.depth.width))

        self.results_a.append(self.method_a(thermal, depth))
        self.results_b.append(self.method_b(thermal, depth))
        self.results_c.append(self.method_c(thermal, depth))

        self.frame_count += 1

        if self.frame_count % 100 == 0:
            self.get_logger().info(f'Collected {self.frame_count}/{MAX_FRAMES} frames...')

        if self.frame_count == MAX_FRAMES:
            self.generate_report()
            raise SystemExit

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────
    def avg(self, results, key):
        return round(sum(r[key] for r in results) / len(results), 4)

    def std(self, results, key):
        vals = [r[key] for r in results]
        return round(float(np.std(vals)), 4)

    def avg_at(self, results, key, n):
        subset = results[:n]
        return round(sum(r[key] for r in subset) / len(subset), 4)

    def std_at(self, results, key, n):
        vals = [r[key] for r in results[:n]]
        return round(float(np.std(vals)), 4)

    # ─────────────────────────────────────────
    # Report
    # ─────────────────────────────────────────
    def generate_report(self):
        self.get_logger().info('Generating report...')
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

        methods      = ['A: Depth\nDownsample', 'B: Thermal\nUpsample', 'C: Common\n640x480']
        colors_bar   = ['#2196F3', '#FF5722', '#4CAF50']
        colors_light = ['#90CAF9', '#FFAB91', '#A5D6A7']

        # Full dataset averages
        avg_time       = [self.avg(self.results_a, 'time_ms'),
                          self.avg(self.results_b, 'time_ms'),
                          self.avg(self.results_c, 'time_ms')]
        avg_lost_close = [self.avg(self.results_a, 'lost_too_close'),
                          self.avg(self.results_b, 'lost_too_close'),
                          self.avg(self.results_c, 'lost_too_close')]
        avg_lost_valid = [self.avg(self.results_a, 'lost_valid'),
                          self.avg(self.results_b, 'lost_valid'),
                          self.avg(self.results_c, 'lost_valid')]
        avg_rmse       = [self.avg(self.results_a, 'thermal_rmse'),
                          self.avg(self.results_b, 'thermal_rmse'),
                          self.avg(self.results_c, 'thermal_rmse')]

        # Convergence data: mean + std per frame count
        conv_mean_a = {k: [self.avg_at(self.results_a, k, n) for n in FRAME_COUNTS]
                       for k in ['time_ms', 'lost_valid', 'thermal_rmse']}
        conv_std_a  = {k: [self.std_at(self.results_a, k, n) for n in FRAME_COUNTS]
                       for k in ['time_ms', 'lost_valid', 'thermal_rmse']}
        conv_mean_b = {k: [self.avg_at(self.results_b, k, n) for n in FRAME_COUNTS]
                       for k in ['time_ms', 'lost_valid', 'thermal_rmse']}
        conv_std_b  = {k: [self.std_at(self.results_b, k, n) for n in FRAME_COUNTS]
                       for k in ['time_ms', 'lost_valid', 'thermal_rmse']}
        conv_mean_c = {k: [self.avg_at(self.results_c, k, n) for n in FRAME_COUNTS]
                       for k in ['time_ms', 'lost_valid', 'thermal_rmse']}
        conv_std_c  = {k: [self.std_at(self.results_c, k, n) for n in FRAME_COUNTS]
                       for k in ['time_ms', 'lost_valid', 'thermal_rmse']}

        fig = plt.figure(figsize=(18, 16))
        fig.patch.set_facecolor('#0f1117')
        gs  = GridSpec(4, 3, figure=fig, hspace=0.6, wspace=0.4)

        fig.suptitle(
            'Resolution Alignment Benchmark — Real Pipeline Data\n'
            'Thermal UTi721M (256×192, 25Hz) vs Depth D435 (1280×720, 30Hz)',
            color='white', fontsize=14, fontweight='bold', y=0.99
        )

        def styled_bar(ax, values, ylabel, title_text):
            bars = ax.bar(methods, values, color=colors_bar,
                          width=0.5, edgecolor='white', linewidth=0.5)
            ax.set_facecolor('#1e1e2e')
            ax.set_title(title_text, color='white', fontsize=9, pad=8)
            ax.set_ylabel(ylabel, color='#aaaaaa', fontsize=8)
            ax.tick_params(colors='white', labelsize=7)
            for spine in ax.spines.values():
                spine.set_edgecolor('#444444')
            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(values) * 0.02,
                        f'{val:.3f}', ha='center', va='bottom',
                        color='white', fontsize=8, fontweight='bold')
            best_idx = int(np.argmin(values))
            bars[best_idx].set_edgecolor('#FFD700')
            bars[best_idx].set_linewidth(2.5)

        def styled_conv(ax, means_list, stds_list, ylabel, title_text):
            x = np.arange(len(FRAME_COUNTS))
            for i, (means, stds, color, label) in enumerate(
                    zip(means_list, stds_list, colors_bar,
                        ['A: Depth Down', 'B: Thermal Up', 'C: Common'])):
                ax.plot(x, means, color=color, marker='o',
                        linewidth=2, label=label)
                ax.fill_between(x,
                                [m - s for m, s in zip(means, stds)],
                                [m + s for m, s in zip(means, stds)],
                                color=color, alpha=0.15)
            ax.set_facecolor('#1e1e2e')
            ax.set_title(title_text, color='white', fontsize=9, pad=8)
            ax.set_ylabel(ylabel, color='#aaaaaa', fontsize=8)
            ax.set_xticks(x)
            ax.set_xticklabels([str(n) for n in FRAME_COUNTS], color='white', fontsize=7)
            ax.set_xlabel('Frame Count', color='#aaaaaa', fontsize=7)
            ax.tick_params(colors='white', labelsize=7)
            ax.legend(fontsize=7, facecolor='#1e1e2e',
                      labelcolor='white', edgecolor='#444444')
            for spine in ax.spines.values():
                spine.set_edgecolor('#444444')

        # ── Row 0: Bar charts ──
        ax0 = fig.add_subplot(gs[0, 0])
        styled_bar(ax0, avg_time, 'ms', 'Avg Processing Time (ms)')

        ax1 = fig.add_subplot(gs[0, 1])
        styled_bar(ax1, avg_lost_valid, 'pixels', 'Lost Pixels: 5–30cm')

        ax2 = fig.add_subplot(gs[0, 2])
        styled_bar(ax2, avg_rmse, '°C', 'Thermal RMSE (°C)')

        # ── Row 1: Convergence — Processing time ──
        ax3 = fig.add_subplot(gs[1, :])
        styled_conv(
            ax3,
            [conv_mean_a['time_ms'], conv_mean_b['time_ms'], conv_mean_c['time_ms']],
            [conv_std_a['time_ms'],  conv_std_b['time_ms'],  conv_std_c['time_ms']],
            'ms', 'Convergence Analysis — Processing Time (mean ± std)'
        )

        # ── Row 2: Convergence — Lost valid pixels ──
        ax4 = fig.add_subplot(gs[2, :2])
        styled_conv(
            ax4,
            [conv_mean_a['lost_valid'], conv_mean_b['lost_valid'], conv_mean_c['lost_valid']],
            [conv_std_a['lost_valid'],  conv_std_b['lost_valid'],  conv_std_c['lost_valid']],
            'pixels', 'Convergence Analysis — Lost Valid Pixels (5–30cm)'
        )

        # ── Row 2: Convergence — Thermal RMSE ──
        ax5 = fig.add_subplot(gs[2, 2])
        styled_conv(
            ax5,
            [conv_mean_a['thermal_rmse'], conv_mean_b['thermal_rmse'], conv_mean_c['thermal_rmse']],
            [conv_std_a['thermal_rmse'],  conv_std_b['thermal_rmse'],  conv_std_c['thermal_rmse']],
            '°C', 'Convergence Analysis — Thermal RMSE'
        )

        # ── Row 3: Summary table ──
        ax6 = fig.add_subplot(gs[3, :])
        ax6.set_facecolor('#1e1e2e')
        ax6.axis('off')

        std_time       = [self.std(self.results_a, 'time_ms'),
                          self.std(self.results_b, 'time_ms'),
                          self.std(self.results_c, 'time_ms')]
        std_lost_valid = [self.std(self.results_a, 'lost_valid'),
                          self.std(self.results_b, 'lost_valid'),
                          self.std(self.results_c, 'lost_valid')]
        std_rmse       = [self.std(self.results_a, 'thermal_rmse'),
                          self.std(self.results_b, 'thermal_rmse'),
                          self.std(self.results_c, 'thermal_rmse')]

        table_data = [
            [f'{avg_time[i]:.3f} ± {std_time[i]:.3f} ms'             for i in range(3)],
            [f'{avg_lost_close[i]:.1f} px'                            for i in range(3)],
            [f'{avg_lost_valid[i]:.1f} ± {std_lost_valid[i]:.1f} px' for i in range(3)],
            [f'{avg_rmse[i]:.4f} ± {std_rmse[i]:.4f} °C'             for i in range(3)],
        ]
        row_labels = ['Avg Time (ms)',
                      'Lost <5cm (px)',
                      'Lost 5–30cm (px)',
                      'Thermal RMSE (°C)']
        col_labels = ['Method A — Depth Downsample\n(1280×720 → 256×192)',
                      'Method B — Thermal Upsample\n(256×192 → 1280×720)',
                      'Method C — Common Resolution\n(Both → 640×480)']

        cell_colors = []
        for row in table_data:
            row_colors = ['#2a2a3e'] * 3
            try:
                numeric        = [float(v.split()[0]) for v in row]
                best           = int(np.argmin(numeric))
                row_colors[best] = '#1a3a1a'
            except Exception:
                pass
            cell_colors.append(row_colors)

        table = ax6.table(
            cellText    = table_data,
            rowLabels   = row_labels,
            colLabels   = col_labels,
            cellLoc     = 'center',
            loc         = 'center',
            cellColours = cell_colors,
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 2.0)

        for (r, c), cell in table.get_celld().items():
            cell.set_edgecolor('#444444')
            cell.set_text_props(color='white')
            if r == 0:
                cell.set_facecolor('#2196F3')
                cell.set_text_props(color='white', fontweight='bold')
            if c == -1:
                cell.set_facecolor('#333355')
                cell.set_text_props(color='#aaaaaa')

        ax6.set_title(
            f'Summary Table — {MAX_FRAMES} Frames  |  mean ± std  |  green = best per row',
            color='white', fontsize=9, pad=10
        )

        plt.savefig(OUTPUT_PATH, dpi=150, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        self.get_logger().info(f'Report saved: {OUTPUT_PATH}')


def main(args=None):
    rclpy.init(args=args)
    node = BenchmarkNode()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()