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
import matplotlib.gridspec as gridspec
from matplotlib import rcParams

# ── Academic style ──
rcParams.update({
    'font.family'      : 'serif',
    'font.size'        : 9,
    'axes.titlesize'   : 10,
    'axes.labelsize'   : 9,
    'axes.grid'        : True,
    'grid.color'       : '#EEEEEE',
    'grid.linewidth'   : 0.8,
    'figure.facecolor' : 'white',
    'axes.facecolor'   : 'white',
    'axes.spines.top'  : False,
    'axes.spines.right': False,
})

# ── Pastel palette ──
CA, CB, CC = '#AEC6CF', '#FFD1A9', '#B5EAD7'
COLORS     = [CA, CB, CC]
EDGE       = '#888888'

METHOD_LABELS = ['A\nDepth Down', 'B\nThermal Up', 'C\nCommon']
METHOD_FULL   = ['Method A\nDepth Down', 'Method B\nThermal Up', 'Method C\nCommon']

# ── Constants ──
TH, TW       = 192, 256
DH, DW       = 480, 848
CH, CW       = 384, 512
TOO_CLOSE    = 50
MAX_VALID    = 300
FRAME_COUNTS = [100, 300, 750, 1500]
MAX_FRAMES   = max(FRAME_COUNTS)
OUT_PATH     = '/workspace/logs/resolution_benchmark.png'


class ResolutionNode(Node):
    def __init__(self):
        super().__init__('resolution_node')
        self.subscription = self.create_subscription(
            FusedData, '/fused/output_v2', self.callback, 10)
        self.results     = {'a': [], 'b': [], 'c': []}
        self.frame_count = 0
        self.get_logger().info(
            f'ResolutionNode started. Collecting {MAX_FRAMES} frames...')

    def categorize(self, d):
        c = np.zeros_like(d, dtype=np.uint8)
        c[d < TOO_CLOSE] = 0
        c[(d >= TOO_CLOSE) & (d <= MAX_VALID)] = 1
        c[d > MAX_VALID] = 2
        return c

    def cls_accuracy(self, orig, resampled):
        back     = cv2.resize(resampled, (DW, DH), interpolation=cv2.INTER_NEAREST)
        co, cb   = self.categorize(orig), self.categorize(back)
        accuracy = np.sum(co == cb) / co.size * 100
        return {
            'accuracy'          : float(accuracy),
            'tooclose_to_valid' : int(np.sum((co == 0) & (cb == 1))),
            'tooclose_to_far'   : int(np.sum((co == 0) & (cb == 2))),
            'valid_to_tooclose' : int(np.sum((co == 1) & (cb == 0))),
            'valid_to_far'      : int(np.sum((co == 1) & (cb == 2))),
            'far_to_valid'      : int(np.sum((co == 2) & (cb == 1))),
            'far_to_tooclose'   : int(np.sum((co == 2) & (cb == 0))),
        }

    def rmse(self, orig, resampled):
        back = cv2.resize(resampled, (TW, TH), interpolation=cv2.INTER_LINEAR)
        return float(np.sqrt(np.mean((orig - back) ** 2)))

    def depth_metrics(self, d):
        return (int(np.sum(d < TOO_CLOSE)),
                int(np.sum((d >= TOO_CLOSE) & (d <= MAX_VALID))),
                int(np.sum(d > MAX_VALID)))

    def avg(self, results, key, n=None):
        r = results[:n] if n else results
        return round(sum(x[key] for x in r) / len(r), 4)

    def std(self, results, key, n=None):
        r = results[:n] if n else results
        return round(float(np.std([x[key] for x in r])), 4)

    def stable_at(self, results, key, threshold=0.05):
        values = [self.avg(results, key, n) for n in FRAME_COUNTS]
        for i in range(1, len(values)):
            if values[i-1] == 0:
                continue
            if abs(values[i] - values[i-1]) / abs(values[i-1]) < threshold:
                return FRAME_COUNTS[i]
        return FRAME_COUNTS[-1]

    def method_a(self, t, d):
        t0   = time.perf_counter()
        down = cv2.resize(d, (TW, TH), interpolation=cv2.INTER_NEAREST)
        ms   = (time.perf_counter() - t0) * 1000
        oc, ov, _ = self.depth_metrics(d)
        dc, dv, _ = self.depth_metrics(down)
        return {'time_ms': ms, 'lost_valid': ov - dv,
                'thermal_rmse': 0.0, **self.cls_accuracy(d, down)}

    def method_b(self, t, d):
        t0 = time.perf_counter()
        up = cv2.resize(t, (DW, DH), interpolation=cv2.INTER_LINEAR)
        ms = (time.perf_counter() - t0) * 1000
        return {'time_ms': ms, 'lost_valid': 0,
                'thermal_rmse': self.rmse(t, up),
                'accuracy': 100.0, 'tooclose_to_valid': 0,
                'tooclose_to_far': 0, 'valid_to_tooclose': 0,
                'valid_to_far': 0, 'far_to_valid': 0, 'far_to_tooclose': 0}

    def method_c(self, t, d):
        t0  = time.perf_counter()
        tc  = cv2.resize(t, (CW, CH), interpolation=cv2.INTER_LINEAR)
        dc  = cv2.resize(d, (CW, CH), interpolation=cv2.INTER_NEAREST)
        ms  = (time.perf_counter() - t0) * 1000
        oc, ov, _ = self.depth_metrics(d)
        cc, cv_, _ = self.depth_metrics(dc)
        return {'time_ms': ms, 'lost_valid': ov - cv_,
                'thermal_rmse': self.rmse(t, tc),
                **self.cls_accuracy(d, dc)}

    def callback(self, msg: FusedData):
        if self.frame_count >= MAX_FRAMES:
            return
        t = np.frombuffer(msg.thermal.data, dtype=np.float32).reshape(
            msg.thermal.height, msg.thermal.width)
        d = np.frombuffer(msg.depth.data, dtype=np.uint16).reshape(
            msg.depth.height, msg.depth.width)
        self.results['a'].append(self.method_a(t, d))
        self.results['b'].append(self.method_b(t, d))
        self.results['c'].append(self.method_c(t, d))
        self.frame_count += 1
        if self.frame_count in FRAME_COUNTS:
            self.get_logger().info(
                f'Collected {self.frame_count}/{MAX_FRAMES} frames...')
        if self.frame_count == MAX_FRAMES:
            self.generate_report()
            raise SystemExit
           

    def generate_report(self):
        self.get_logger().info('Generating report...')
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

        METRICS = [
            ('time_ms',      'Processing Time',           'ms', False),
            ('lost_valid',   'Lost Valid Pixels (3-150cm)', 'px', False),
            ('thermal_rmse', 'Thermal RMSE',              '°C', False),
            ('accuracy',     'Classification Accuracy',   '%',  True),
        ]

        stable = {}
        finals = {}
        for key, _, _, _ in METRICS:
            stable[key] = {m: self.stable_at(self.results[m], key) for m in 'abc'}
            finals[key] = {
                m: {
                    'avg': self.avg(self.results[m], key, stable[key][m]),
                    'std': self.std(self.results[m], key, stable[key][m]),
                }
                for m in 'abc'
            }

        conv = {
            key: {m: [self.avg(self.results[m], key, n) for n in FRAME_COUNTS]
                  for m in 'abc'}
            for key, *_ in METRICS
        }
        conv_std = {
            key: {m: [self.std(self.results[m], key, n) for n in FRAME_COUNTS]
                  for m in 'abc'}
            for key, *_ in METRICS
        }

        err_keys = ['tooclose_to_valid', 'tooclose_to_far',
                    'valid_to_tooclose', 'valid_to_far',
                    'far_to_valid',      'far_to_tooclose']
        err_avgs = {k: [self.avg(self.results[m], k) for m in 'abc']
                    for k in err_keys}

        # ── Figure ──
        fig = plt.figure(figsize=(14, 24))
        outer = gridspec.GridSpec(
            5, 1, figure=fig, hspace=0.6,
            height_ratios=[1, 1, 1, 1, 1.6])

        fig.suptitle(
            'Resolution Alignment Benchmark\n'
            'Thermal UTi721M (256×192, 25 Hz)  vs.  '
            'Depth D435 (1280×720, 30 Hz)',
            fontsize=12, fontweight='bold', y=1.01, color='#1a1a1a')

        x  = np.arange(3)
        xi = np.arange(len(FRAME_COUNTS))

        for row_idx, (key, label, unit, higher) in enumerate(METRICS):
            inner = gridspec.GridSpecFromSubplotSpec(
                1, 2, subplot_spec=outer[row_idx],
                wspace=0.35, width_ratios=[1, 1.6])

            # Bar chart
            ax_bar = fig.add_subplot(inner[0])
            vals   = [finals[key][m]['avg'] for m in 'abc']
            errs   = [finals[key][m]['std'] for m in 'abc']
            sfs    = [stable[key][m] for m in 'abc']

            bars = ax_bar.bar(x, vals, color=COLORS, edgecolor=EDGE,
                              linewidth=0.8, width=0.5,
                              yerr=errs, capsize=4,
                              error_kw={'ecolor': EDGE, 'linewidth': 1})

            best = int(np.argmax(vals) if higher else np.argmin(vals))
            bars[best].set_edgecolor('#E63946')
            bars[best].set_linewidth(2.5)

            for b, v, sf in zip(bars, vals, sfs):
                ax_bar.text(b.get_x() + b.get_width()/2,
                            b.get_height() + max(vals) * 0.04,
                            f'{v:.3f}', ha='center', fontsize=8,
                            fontweight='bold', color='#333333')
                ax_bar.text(b.get_x() + b.get_width()/2,
                            -max(vals) * 0.15,
                            f'n={sf}', ha='center', fontsize=7,
                            color='#666666', style='italic')

            ax_bar.set_title(f'{label} ({unit})', fontweight='bold', pad=6)
            ax_bar.set_ylabel(unit)
            ax_bar.set_xticks(x)
            ax_bar.set_xticklabels(METHOD_LABELS, fontsize=8)
            ax_bar.set_ylim(bottom=-max(vals) * 0.2 if max(vals) > 0 else -0.1)

            # Convergence
            ax_conv = fig.add_subplot(inner[1])
            for m, color, mlabel in zip('abc', COLORS,
                                        ['Method A', 'Method B', 'Method C']):
                means  = conv[key][m]
                stds   = conv_std[key][m]
                sf     = stable[key][m]
                sf_idx = FRAME_COUNTS.index(sf)

                ax_conv.plot(xi, means, color=color, marker='o',
                             linewidth=2, label=mlabel,
                             markeredgecolor=EDGE, markeredgewidth=0.8)
                ax_conv.fill_between(
                    xi,
                    [a - s for a, s in zip(means, stds)],
                    [a + s for a, s in zip(means, stds)],
                    color=color, alpha=0.2)
                ax_conv.hlines(
                    y=means[sf_idx],
                    xmin=sf_idx, xmax=len(FRAME_COUNTS) - 1,
                    colors=color, linestyles='dotted', linewidth=1.5)

            ax_conv.set_title(f'Convergence — {label}', fontweight='bold', pad=6)
            ax_conv.set_ylabel(unit)
            ax_conv.set_xticks(xi)
            ax_conv.set_xticklabels(FRAME_COUNTS)
            ax_conv.set_xlabel('Frame Count')
            ax_conv.legend(fontsize=8, framealpha=0.9)

        # ── Summary table ──
        ax_t = fig.add_subplot(outer[4])
        ax_t.axis('off')
        ax_t.set_title(
            'Summary Table  |  mean ± std  |  n = stable frame count  '
            '|  green = best per metric',
            fontweight='bold', fontsize=9, pad=15)

        tdata   = []
        rlabels = []
        for key, label, unit, higher in METRICS:
            row = []
            for m in 'abc':
                a  = finals[key][m]['avg']
                s  = finals[key][m]['std']
                sf = stable[key][m]
                row.append(f'{a:.3f} ± {s:.3f}\n(n={sf})')
            tdata.append(row)
            rlabels.append(f'{label}\n({unit})')

        err_labels_short = [
            'Too Close→Valid', 'Too Close→Far',
            'Valid→Too Close', 'Valid→Far',
            'Far→Valid',       'Far→Too Close',
        ]
        for ek, el in zip(err_keys, err_labels_short):
            tdata.append([f'{err_avgs[ek][i]:.1f}' for i in range(3)])
            rlabels.append(f'{el}\n(px)')

        cell_colors = []
        for i, (_, _, _, higher) in enumerate(METRICS):
            rc = ['#FFFFFF'] * 3
            try:
                nums     = [float(tdata[i][j].split()[0]) for j in range(3)]
                best     = int(np.argmax(nums) if higher else np.argmin(nums))
                rc[best] = '#D4EDDA'
            except Exception:
                pass
            cell_colors.append(rc)
        for _ in err_keys:
            cell_colors.append(['#FFF9F0'] * 3)

        tbl = ax_t.table(
            cellText    = tdata,
            rowLabels   = rlabels,
            colLabels   = METHOD_FULL,
            cellLoc     = 'center',
            loc         = 'center',
            cellColours = cell_colors,
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        tbl.scale(1, 2.1)

        for (r, c), cell in tbl.get_celld().items():
            cell.set_edgecolor('#CCCCCC')
            if r == 0:
                cell.set_facecolor('#E8F0FE')
                cell.set_text_props(fontweight='bold', fontsize=9)
            if c == -1:
                cell.set_facecolor('#F5F5F5')
                cell.set_text_props(fontweight='bold', fontsize=8)

        plt.savefig(OUT_PATH, dpi=150, bbox_inches='tight', facecolor='white')
        self.get_logger().info(f'Report saved: {OUT_PATH}')


def main(args=None):
    rclpy.init(args=args)
    node = ResolutionNode()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()