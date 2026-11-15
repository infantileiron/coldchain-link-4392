from datetime import datetime,timezone
from sqlalchemy import func
from src.constants.enums import ZONE_THRESHOLDS,DEFAULT_MAX_GAP
from src.models.entities import Sample,Shipment,Probe,TempPoint,Publication,Audit,Meta
from src.services.tempcalc import compute_window
from src.services.logs import get_gen
def compute_sample(s,smp,gen):
 ship=s.get(Shipment,smp.shipment_id)
 if ship is None or not ship.probe:raise ValueError('班次未登记探头')
 if not ship.depart_at or not ship.arrive_at:raise ValueError('班次未登记运输起止')
 if ship.arrive_at<=ship.depart_at:raise ValueError('运输结束必须晚于开始')
 probe=s.query(Probe).filter_by(code=ship.probe).first()
 rev=probe.current_rev if probe else 0
 pts=[]
 if probe:pts=[(p.ts,p.temp) for p in s.query(TempPoint).filter_by(probe=ship.probe,revision=rev).order_by(TempPoint.ts)]
 thr=ship.threshold if ship.threshold is not None else ZONE_THRESHOLDS.get(ship.zone,4.0)
 gap=ship.max_gap if ship.max_gap is not None else DEFAULT_MAX_GAP
 detail=compute_window(pts,ship.depart_at,ship.arrive_at,thr,gap)
 detail['probe']=ship.probe;detail['revision']=rev;detail['gen']=gen
 detail['computed_at']=datetime.now(timezone.utc).isoformat()
 return detail
def run_recalc(s):
 '''重算全部待重算样本，全部成功才一起发布为新版本；任一失败保留旧版；
 发布前复核日志世代，并发更正导致世代变化时拒绝本次过期计算。'''
 gen=get_gen(s)
 pendings=s.query(Sample).filter_by(calc_state='pending').all()
 if not pendings:return {'published':None,'pending':0}
 results,failed={},{}
 for smp in pendings:
  try:results[smp.id]=compute_sample(s,smp,gen)
  except Exception as e:failed[smp.id]=str(e)
 if failed:
  for smp in pendings:
   if smp.id in failed:smp.calc_state='failed';smp.calc_error=failed[smp.id]
  s.commit()
  return {'published':None,'failed':failed}
 row=s.query(Meta).filter_by(key='log_gen').with_for_update().first()
 cur=int(row.value) if row else 0
 if cur!=gen:
  s.rollback()
  return {'published':None,'stale':True}
 version=(s.query(func.max(Publication.version)).scalar() or 0)+1
 now=datetime.now(timezone.utc).isoformat()
 for smp in pendings:
  d=results[smp.id]
  smp.exposure=d['over_minutes'];smp.excursions=d['segments']
  smp.detail=d;smp.calc_state='published';smp.calc_error='';smp.pub_version=version
 for smp in s.query(Sample).filter_by(source='auto',calc_state='published').all():smp.pub_version=version
 count=s.query(Sample).filter_by(source='auto').count()
 s.add(Publication(version=version,gen=gen,sample_count=count,created=now))
 s.add(Audit(actor='worker',action=f'发布计算版本 v{version}：重算 {len(pendings)} 个样本',created=now))
 s.commit()
 return {'published':version,'gen':gen,'samples':[smp.id for smp in pendings]}
