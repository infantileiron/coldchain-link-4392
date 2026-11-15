import sys
sys.path.insert(0, '/workspace/backend')
from datetime import datetime, timedelta
from src.services.tempcalc import compute_window

T0 = datetime(2026, 11, 14, 8, 0, 0)
def pts(spec):
    return [(T0 + timedelta(minutes=off), temp) for off, temp in spec]
def run(points, span, thr=4.0, gap=10):
    return compute_window(points, T0, T0 + timedelta(minutes=span), thr, gap)

fails = []
def check(name, got, want):
    if got != want:
        fails.append(f'{name}: got {got!r} want {want!r}')

# 1 读数保持到下一时刻：08:10 的 6°C 保持到 08:20
r = run(pts([(0, 2.0), (10, 6.0), (20, 2.0)]), 30)
check('保持-超温分钟', r['over_minutes'], 10.0)
check('保持-段数', r['segments'], 1)
check('保持-峰值', r['over_segments'][0]['peak'], 6.0)
check('保持-无缺测', r['gap_minutes'], 0.0)
check('保持-实测', r['measured_minutes'], 30.0)

# 2 窗口前读数向后保持：07:55=6 覆盖到 08:05，之后 08:05=2 覆盖 10 分钟，尾部缺测
r = run([(T0 - timedelta(minutes=5), 6.0), (T0 + timedelta(minutes=5), 2.0)], 30)
check('前读数-超温', r['over_minutes'], 5.0)
check('前读数-缺测', r['gap_minutes'], 15.0)
check('前读数-实测', r['measured_minutes'], 15.0)

# 3 缺测超过设定间隔单列，不计正常也不计超温
r = run(pts([(0, 2.0), (30, 2.0)]), 60)
check('缺测-分钟', r['gap_minutes'], 40.0)
check('缺测-实测', r['measured_minutes'], 20.0)
check('缺测-超温', r['over_minutes'], 0.0)
check('缺测-段数', len(r['gaps']), 2)

# 4 被缺测隔开的两段超温分别计数；相邻同向读数合并为一段
# 08:05 的读数保持 10 分钟到 08:15，故第一段 08:00-08:15 共 15 分钟
r = run(pts([(0, 6.0), (5, 6.5), (30, 5.0), (35, 2.0)]), 60)
check('分段-段数', r['segments'], 2)
check('分段-超温分钟', r['over_minutes'], 20.0)
check('分段-第一段时长', r['over_segments'][0]['minutes'], 15.0)
check('分段-第二段时长', r['over_segments'][1]['minutes'], 5.0)
check('分段-缺测', r['gap_minutes'], 30.0)
check('分段-总量守恒', round(r['measured_minutes'] + r['gap_minutes'], 2), r['window']['total_minutes'])

# 5 完全无读数：整窗缺测
r = run([], 60)
check('空-缺测', r['gap_minutes'], 60.0)
check('空-超温', r['over_minutes'], 0.0)
check('空-段数', r['segments'], 0)

# 6 阈值边界：等于阈值不算超温
r = run(pts([(0, 4.0), (10, 4.01)]), 20)
check('边界-超温分钟', r['over_minutes'], 10.0)
check('边界-段数', r['segments'], 1)

# 7 窗口结束时刻的读数不产生覆盖
r = run(pts([(60, 9.0)]), 60)
check('末点-超温', r['over_minutes'], 0.0)
check('末点-缺测', r['gap_minutes'], 60.0)

# 8 结束早于开始报错
try:
    compute_window([], T0, T0, 4.0, 10)
    fails.append('反向窗口未报错')
except ValueError:
    pass

# 9 自定义缺测间隔：gap=30 时 25 分钟空档不算缺测
r = run(pts([(0, 2.0), (25, 2.0)]), 30, gap=30)
check('宽间隔-缺测', r['gap_minutes'], 0.0)
check('宽间隔-实测', r['measured_minutes'], 30.0)

if fails:
    print('\n'.join(fails)); sys.exit(1)
print('TEMPCALC_ALL_OK')
