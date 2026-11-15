import os, sys, pathlib
os.environ['DATABASE_URL'] = 'sqlite:////tmp/smoke_seed.db'
os.environ['JWT_SECRET'] = 's' * 32
os.environ['REDIS_URL'] = 'redis://localhost:6399/0'
sys.path.insert(0, '/workspace/backend')
pathlib.Path('/tmp/smoke_seed.db').unlink(missing_ok=True)
from scripts.seed_demo import seed
from src.config.database import Session
from src.models.entities import Sample, Probe
from src.services.recalc import run_recalc

seed()
FAILS = []
def check(name, cond, extra=''):
    if not cond: FAILS.append(name); print('FAIL', name, extra)
    else: print('ok  ', name)

with Session() as s:
    check('种子完成', s.query(Sample).count() == 62 and s.query(Probe).count() == 2)
    check('自动样本待重算', s.query(Sample).filter_by(source='auto', calc_state='pending').count() == 2)
    summary = run_recalc(s)
    check('种子首次发布', summary.get('published') == 1, str(summary))
    t1 = s.query(Sample).filter_by(code='XD-1115-T01-S').first()
    t2 = s.query(Sample).filter_by(code='XD-1115-T02-S').first()
    check('T01 超温40分钟2段', t1.exposure == 40.0 and t1.excursions == 2, f'{t1.exposure}/{t1.excursions}')
    check('T01 缺测20分钟', t1.detail['gap_minutes'] == 20.0, str(t1.detail['gap_minutes']))
    check('T01 总量守恒', t1.detail['measured_minutes'] + t1.detail['gap_minutes'] == 120.0)
    check('T02 超温40分钟1段', t2.exposure == 40.0 and t2.excursions == 1, f'{t2.exposure}/{t2.excursions}')
    check('T02 无缺测', t2.detail['gap_minutes'] == 0.0)
seed()  # 幂等：重复执行不覆盖
with Session() as s:
    t1 = s.query(Sample).filter_by(code='XD-1115-T01-S').first()
    check('重复种子不覆盖', t1.exposure == 40.0 and t1.pub_version == 1)
print('SEED_OK' if not FAILS else 'SEED_FAILED')
sys.exit(1 if FAILS else 0)
