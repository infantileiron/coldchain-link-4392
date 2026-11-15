import os, sys, json, pathlib
os.environ['DATABASE_URL'] = 'sqlite:////tmp/smoke.db'
os.environ['JWT_SECRET'] = 'smoke-secret'
os.environ['REDIS_URL'] = 'redis://localhost:6399/0'
sys.path.insert(0, '/workspace/backend')
pathlib.Path('/tmp/smoke.db').unlink(missing_ok=True)

import redis
class FakeRedis:
    def __init__(self): self.queues = {}
    def rpush(self, k, v): self.queues.setdefault(k, []).append(v); return len(self.queues[k])
    def ping(self): return True
FAKE = FakeRedis()
redis.Redis.from_url = lambda *a, **k: FAKE

from fastapi.testclient import TestClient
from src.config.database import Base, engine, Session
from src.models.entities import User, Sample, Shipment, Probe, TempPoint, TempBatch, Publication
from src.utils.security import hash_password
from src.services import recalc as recalc_mod
from src.services.logs import bump_gen

Base.metadata.create_all(engine)
with Session() as s:
    for role in ('admin', 'analyst', 'viewer'):
        s.add(User(email=role + '@demo.local', role=role, password=hash_password('Demo123!')))
    s.commit()

from src.main import app

FAILS = []
def check(name, cond, extra=''):
    if not cond:
        FAILS.append(f'{name} {extra}')
        print('FAIL', name, extra)
    else:
        print('ok  ', name)

LOG1 = [('2026-11-14T07:55:00Z', 2.0)] + [(f'2026-11-14T08:{m:02d}:00Z', 2.0) for m in range(0, 31, 5)] \
    + [('2026-11-14T08:35:00Z', 5.0), ('2026-11-14T08:40:00Z', 5.5), ('2026-11-14T08:45:00Z', 6.0),
       ('2026-11-14T08:50:00Z', 2.0), ('2026-11-14T08:55:00Z', 2.0),
       ('2026-11-14T09:30:00Z', 7.0), ('2026-11-14T09:35:00Z', 7.0)] \
    + [(f'2026-11-14T09:{m:02d}:00Z', 2.0) for m in range(40, 60, 5)] + [('2026-11-14T10:00:00Z', 2.0)]
LOG2 = [p for p in LOG1 if p[0] != '2026-11-14T09:40:00Z'] \
    + [('2026-11-14T09:35:00Z', 7.5), ('2026-11-14T09:40:00Z', 7.0)]
LOG2 = sorted({ts: t for ts, t in LOG2}.items())

with TestClient(app) as c:
    r = c.post('/auth/login', json={'email': 'analyst@demo.local', 'password': 'Demo123!'})
    check('登录', r.status_code == 200)
    H = {'Authorization': 'Bearer ' + r.json()['token']}
    r = c.post('/auth/login', json={'email': 'viewer@demo.local', 'password': 'Demo123!'})
    HV = {'Authorization': 'Bearer ' + r.json()['token']}

    r = c.post('/shipments', json={'code': 'T-01', 'route': '线路 01', 'zone': '冷藏', 'driver': '王某',
                                   'probe': 'P-01', 'depart_at': '2026-11-14T08:00:00', 'arrive_at': '2026-11-14T10:00:00'}, headers=H)
    check('创建探头班次', r.status_code == 200, r.text)
    SHIP = r.json()['id']
    r = c.post('/shipments', json={'code': 'M-01', 'route': '线路 02', 'zone': '冷藏', 'driver': '李某'}, headers=H)
    check('创建手填班次', r.status_code == 200)
    MSHIP = r.json()['id']

    r = c.post('/samples', json={'shipment_id': SHIP, 'code': 'T-01-S', 'loss': 3.4, 'exposure': 99}, headers=H)
    check('探头样本转为待重算', r.status_code == 200 and r.json()['source'] == 'auto' and r.json()['calc_state'] == 'pending' and r.json()['exposure'] is None, r.text)
    TSAMPLE = r.json()['id']
    r = c.post('/samples', json={'shipment_id': MSHIP, 'code': 'M-01-S', 'loss': 2.2, 'exposure': 30, 'excursions': 2}, headers=H)
    check('手填样本保持手填', r.status_code == 200 and r.json()['source'] == 'manual' and r.json()['exposure'] == 30, r.text)

    r = c.post('/studies', json={'name': '阻断验证', 'zone': '冷藏', 'feature': 'exposure'}, headers=H)
    check('待重算时拒绝新建研究', r.status_code == 409, r.text)

    r = c.post('/logs', json={'probe': 'P-01', 'revision': 1, 'points': [{'ts': ts, 'temp': t} for ts, t in LOG1]}, headers=H)
    check('导入修订1', r.status_code == 200 and r.json()['state'] == 'applied' and r.json()['queued'], r.text)
    check('导入触发重算队列', len(FAKE.queues.get('recalc', [])) >= 1)

    with Session() as s:
        summary = recalc_mod.run_recalc(s)
    check('首次发布 v1', summary.get('published') == 1, str(summary))
    r = c.get('/samples', headers=H)
    auto = next(x for x in r.json() if x['code'] == 'T-01-S')
    check('v1 超温分钟=25', auto['exposure'] == 25.0, str(auto['exposure']))
    check('v1 超温段数=2', auto['excursions'] == 2)
    check('v1 已发布', auto['calc_state'] == 'published' and auto['pub_version'] == 1)
    d = auto['detail']
    check('v1 缺测25分钟单列', d['gap_minutes'] == 25.0 and len(d['gaps']) == 1, json.dumps(d['gaps']))
    check('v1 总量守恒', d['measured_minutes'] + d['gap_minutes'] == d['window']['total_minutes'] == 120.0)
    check('v1 逐段求和', sum(x['minutes'] for x in d['over_segments']) == d['over_minutes'])
    check('v1 峰值', max(x['peak'] for x in d['over_segments']) == 7.0)

    r = c.post('/studies', json={'name': 'v1 研究', 'zone': '冷藏', 'feature': 'exposure'}, headers=H)
    check('发布后允许新建研究', r.status_code == 200, r.text)
    res = r.json()['result']
    check('研究记录发布版本', res['pub_version'] == 1)
    autos = [x for x in res['snapshot'] if x['source'] == 'auto']
    manuals = [x for x in res['snapshot'] if x['source'] == 'manual']
    check('快照自动样本同版本', len(autos) == 1 and all(x['pub_version'] == 1 for x in autos))
    check('快照含手填样本', len(manuals) == 1 and manuals[0]['exposure'] == 30)
    check('快照不含明细', 'detail' not in res['snapshot'][0])

    r = c.post('/logs', json={'probe': 'P-01', 'revision': 1, 'points': [{'ts': ts, 'temp': t} for ts, t in LOG1]}, headers=H)
    check('同号同内容幂等', r.status_code == 200 and r.json()['state'] == 'applied' and not r.json()['changed'], r.text)
    r = c.post('/logs', json={'probe': 'P-01', 'revision': 0, 'points': [{'ts': '2026-11-14T08:00:00Z', 'temp': 9.9}]}, headers=H)
    check('较低修订忽略', r.status_code == 200 and r.json()['state'] == 'ignored' and r.json()['current_rev'] == 1, r.text)
    conflict = [{'ts': ts, 'temp': (t + 3 if ts == '2026-11-14T08:35:00Z' else t)} for ts, t in LOG1]
    r = c.post('/logs', json={'probe': 'P-01', 'revision': 1, 'points': conflict}, headers=H)
    check('同号温度分歧拒收', r.status_code == 409, r.text)
    with Session() as s:
        b = s.query(TempBatch).filter_by(state='rejected').order_by(TempBatch.id.desc()).first()
        check('拒收留痕', b is not None and '分歧' in b.note)
        from datetime import datetime as dt
        p = s.query(TempPoint).filter_by(probe='P-01', revision=1, ts=dt(2026, 11, 14, 8, 35)).first()
        check('拒收不改数据', p.temp == 5.0)
    r = c.post('/logs', json={'probe': 'P-01', 'revision': 1,
                              'points': [{'ts': '2026-11-14T08:00:00Z', 'temp': 2.0}, {'ts': '2026-11-14T08:00:00Z', 'temp': 9.0}]}, headers=H)
    check('批次内部冲突拒收', r.status_code == 409, r.text)

    r = c.post('/logs', json={'probe': 'P-01', 'revision': 2, 'points': [{'ts': ts, 'temp': t} for ts, t in LOG2]}, headers=H)
    check('导入修订2触发待重算', r.status_code == 200 and r.json()['state'] == 'applied' and r.json()['pending'] >= 1, r.text)
    r = c.post('/studies', json={'name': '阻断验证2', 'zone': '冷藏', 'feature': 'exposure'}, headers=H)
    check('更正后发布前拒绝新建研究', r.status_code == 409, r.text)

    orig = recalc_mod.compute_sample
    def sabotaged(s, smp, gen):
        d = orig(s, smp, gen)
        bump_gen(s); s.commit()
        return d
    recalc_mod.compute_sample = sabotaged
    with Session() as s:
        summary = recalc_mod.run_recalc(s)
    recalc_mod.compute_sample = orig
    check('并发更正拒绝过期计算', summary.get('stale') is True, str(summary))
    with Session() as s:
        check('过期计算不发布', s.query(Publication).count() == 1)
        check('样本保持待重算', s.get(Sample, TSAMPLE).calc_state == 'pending')

    with Session() as s:
        summary = recalc_mod.run_recalc(s)
    check('重算后发布 v2', summary.get('published') == 2, str(summary))
    r = c.get('/samples', headers=H)
    auto = next(x for x in r.json() if x['code'] == 'T-01-S')
    check('v2 采用修订2结果', auto['exposure'] == 30.0 and auto['detail']['revision'] == 2 and auto['pub_version'] == 2, str(auto['exposure']))
    with Session() as s:
        check('旧修订点保留备查', s.query(TempPoint).filter_by(probe='P-01', revision=1).count() > 0)

    r = c.post('/shipments', json={'code': 'B-01', 'route': '线路 03', 'zone': '冷藏', 'driver': '赵某', 'probe': 'P-09'}, headers=H)
    check('创建缺配置班次', r.status_code == 200)
    BSHIP = r.json()['id']
    r = c.post('/samples', json={'shipment_id': BSHIP, 'code': 'B-01-S', 'loss': 1.0}, headers=H)
    check('缺配置样本待重算', r.status_code == 200 and r.json()['calc_state'] == 'pending')
    with Session() as s:
        summary = recalc_mod.run_recalc(s)
    check('坏班次导致整批不发布', summary.get('published') is None and 'failed' in summary, str(summary))
    r = c.get('/samples', headers=H)
    bad = next(x for x in r.json() if x['code'] == 'B-01-S')
    check('失败样本标注原因', bad['calc_state'] == 'failed' and '运输起止' in bad['calc_error'], str(bad['calc_error']))
    auto = next(x for x in r.json() if x['code'] == 'T-01-S')
    check('失败保留旧版', auto['calc_state'] == 'published' and auto['pub_version'] == 2 and auto['exposure'] == 30.0)
    with Session() as s:
        check('失败不产生新版本', s.query(Publication).count() == 2)
    r = c.post('/studies', json={'name': '阻断验证3', 'zone': '冷藏', 'feature': 'exposure'}, headers=H)
    check('失败未修复前拒绝新建研究', r.status_code == 409, r.text)

    r = c.put(f'/shipments/{BSHIP}', json={'code': 'B-01', 'route': '线路 03', 'zone': '冷藏', 'driver': '赵某', 'probe': 'P-09',
                                           'depart_at': '2026-11-14T08:00:00', 'arrive_at': '2026-11-14T09:00:00'}, headers=H)
    check('补齐班次配置', r.status_code == 200, r.text)
    r = c.post('/logs', json={'probe': 'P-09', 'revision': 1,
                              'points': [{'ts': f'2026-11-14T08:{m:02d}:00Z', 'temp': 2.0} for m in range(0, 60, 10)]
                                        + [{'ts': '2026-11-14T09:00:00Z', 'temp': 2.0}]}, headers=H)
    check('导入 P-09 日志', r.status_code == 200, r.text)
    r = c.post('/recalc', headers=H)
    check('手动重算受理', r.status_code == 200 and r.json()['pending'] >= 1, r.text)
    with Session() as s:
        summary = recalc_mod.run_recalc(s)
    check('修复后发布 v3', summary.get('published') == 3, str(summary))
    r = c.get('/samples', headers=H)
    bad = next(x for x in r.json() if x['code'] == 'B-01-S')
    check('修复样本已发布', bad['calc_state'] == 'published' and bad['pub_version'] == 3 and bad['exposure'] == 0.0, str(bad['exposure']))
    auto = next(x for x in r.json() if x['code'] == 'T-01-S')
    check('未变更样本随版本前进', auto['pub_version'] == 3 and auto['exposure'] == 30.0)

    r = c.post('/studies', json={'name': 'v3 研究', 'zone': '冷藏', 'feature': 'exposure'}, headers=H)
    check('v3 后允许新建研究', r.status_code == 200, r.text)
    res = r.json()['result']
    autos = [x for x in res['snapshot'] if x['source'] == 'auto']
    check('研究记录同一发布版本', res['pub_version'] == 3 and all(x['pub_version'] == 3 for x in autos) and len(autos) == 2)

    r = c.put(f'/samples/{TSAMPLE}', json={'shipment_id': SHIP, 'code': 'T-01-S', 'loss': 4.4, 'exposure': 99, 'excursions': 9}, headers=H)
    check('探头样本忽略手填暴露', r.status_code == 200 and r.json()['exposure'] == 30.0 and r.json()['loss'] == 4.4, r.text)

    r = c.post('/logs', json={'probe': 'P-01', 'revision': 3, 'points': [{'ts': '2026-11-14T08:00:00Z', 'temp': 2.0}]}, headers=HV)
    check('观察员禁止导入', r.status_code == 403, r.text)
    r = c.get('/logs', headers=HV)
    check('观察员可读批次', r.status_code == 200 and any(b['state'] == 'rejected' for b in r.json()))
    r = c.get('/probes', headers=HV)
    check('探头清单', r.status_code == 200 and any(p['code'] == 'P-01' and p['current_rev'] == 2 for p in r.json()), r.text)
    r = c.get('/publications', headers=HV)
    check('发布版本清单', r.status_code == 200 and [p['version'] for p in r.json()] == [3, 2, 1], r.text)

print('SMOKE_OK' if not FAILS else 'SMOKE_FAILED')
sys.exit(1 if FAILS else 0)
