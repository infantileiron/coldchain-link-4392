import os, sys, pathlib, json
os.environ['DATABASE_URL'] = 'sqlite:////tmp/smoke_worker.db'
os.environ['JWT_SECRET'] = 'w' * 32
os.environ['REDIS_URL'] = 'redis://fake/0'
sys.path.insert(0, '/workspace/backend')
pathlib.Path('/tmp/smoke_worker.db').unlink(missing_ok=True)
for f in pathlib.Path('/tmp').glob('pub-*.json'): f.unlink()
for f in pathlib.Path('/tmp').glob('study-*.json'): f.unlink()

import redis
class FakeRedis:
    def __init__(self): self.q = {}
    def rpush(self, k, v): self.q.setdefault(k, []).append(str(v)); return len(self.q[k])
    def blpop(self, keys, timeout=3):
        for k in keys:
            if self.q.get(k): return (k.encode(), self.q[k].pop(0).encode())
        raise KeyboardInterrupt()
    def ping(self): return True
FAKE = FakeRedis()
redis.Redis.from_url = lambda *a, **k: FAKE

import pathlib as pl
_orig_write = pl.Path.write_text
def redirected(self, *a, **k):
    p = pl.Path('/tmp') / ('study-' + self.name if self.name.endswith('.json') and not self.name.startswith('pub-') else self.name) \
        if str(self).startswith('/artifacts/') else self
    return _orig_write(p, *a, **k)
pl.Path.write_text = redirected

from src.config.database import Base, engine, Session
from src.models.entities import Shipment, Sample, Probe, TempPoint, Study, Publication
from datetime import datetime, timedelta
Base.metadata.create_all(engine)
with Session() as s:
    ship = Shipment(code='W-01', route='r1', zone='冷藏', driver='d', probe='P-W',
                    depart_at=datetime(2026, 11, 14, 8, 0), arrive_at=datetime(2026, 11, 14, 9, 0))
    s.add(ship); s.flush()
    s.add(Probe(code='P-W', current_rev=1))
    t0 = datetime(2026, 11, 14, 7, 55)
    for i in range(14):
        temp = 6.0 if 3 <= i < 6 else 2.0
        s.add(TempPoint(probe='P-W', revision=1, ts=t0 + timedelta(minutes=5 * i), temp=temp))
    s.add(Sample(shipment_id=ship.id, code='W-01-S', loss=3.0, source='auto', calc_state='pending'))
    for i, (ex, lo) in enumerate([(10, 2.1), (20, 3.2), (30, 4.1), (40, 5.0)]):
        s.add(Sample(shipment_id=ship.id, code=f'W-M{i}', exposure=ex, excursions=1, loss=lo))
    s.add(Study(name='worker 研究', zone='冷藏', feature='exposure', state='queued',
                result={'snapshot': [{'exposure': 10, 'loss': 2.0}, {'exposure': 20, 'loss': 3.0},
                                     {'exposure': 30, 'loss': 4.0}, {'exposure': 40, 'loss': 5.0}], 'pub_version': None}))
    s.commit()

try:
    import src.worker  # noqa: F401  模块级循环；队列排空后由假 Redis 抛出 KeyboardInterrupt 退出
except KeyboardInterrupt:
    pass

FAILS = []
def check(name, cond, extra=''):
    if not cond: FAILS.append(name); print('FAIL', name, extra)
    else: print('ok  ', name)

with Session() as s:
    smp = s.query(Sample).filter_by(code='W-01-S').first()
    check('worker 重算发布', smp.calc_state == 'published' and smp.pub_version == 1, str(smp.calc_state))
    check('worker 超温分钟', smp.exposure == 15.0, str(smp.exposure))
    check('worker 段数', smp.excursions == 1)
    check('发布版本行', s.query(Publication).count() == 1)
    st = s.query(Study).first()
    check('研究完成', st.state == 'done', st.error)
    check('研究 pearson=1', abs(st.result['pearson'] - 1.0) < 1e-6, str(st.result.get('pearson')))
    STUDY_ID = st.id
check('发布证据文件', pathlib.Path('/tmp/pub-1.json').exists())
check('研究证据文件', pathlib.Path(f'/tmp/study-{STUDY_ID}.json').exists())
print('WORKER_OK' if not FAILS else 'WORKER_FAILED')
sys.exit(1 if FAILS else 0)
