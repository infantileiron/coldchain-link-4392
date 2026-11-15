from datetime import datetime,timezone
from src.models.entities import Probe,TempPoint,TempBatch,Sample,Shipment,Meta
def norm_ts(dt):
 '''带时区的时刻统一转 UTC 后按无时区存储；无时区的按原样存储。'''
 if dt.tzinfo is not None:return dt.astimezone(timezone.utc).replace(tzinfo=None)
 return dt
def get_gen(s):
 row=s.get(Meta,'log_gen')
 return int(row.value) if row else 0
def bump_gen(s):
 row=s.get(Meta,'log_gen')
 if row is None:
  row=Meta(key='log_gen',value='0');s.add(row);s.flush()
 row.value=str(int(row.value)+1)
 return int(row.value)
def mark_probe_pending(s,probe_code):
 ids=[sh.id for sh in s.query(Shipment).filter_by(probe=probe_code).all()]
 if not ids:return 0
 n=0
 for smp in s.query(Sample).filter(Sample.shipment_id.in_(ids),Sample.source=='auto').all():
  smp.calc_state='pending';smp.calc_error='';n+=1
 return n
def sync_shipment_samples(s,ship):
 '''班次探头或计算配置变化后，同步样本来源并标待重算；返回待重算数。'''
 n=0
 for smp in s.query(Sample).filter_by(shipment_id=ship.id).all():
  if ship.probe:
   if smp.source!='auto':smp.source='auto';smp.exposure=None;smp.excursions=None;smp.pub_version=None
   smp.calc_state='pending';smp.calc_error='';n+=1
  elif smp.source!='manual':smp.source='manual';smp.calc_state=None
 return n
def import_batch(s,probe_code,revision,points):
 '''接收一批温度日志。points: [(ts,temp)]（已归一化时区）。
 较低修订忽略；同号修订温度分歧拒收整批；更高修订替换并触发重算。'''
 now=datetime.now(timezone.utc).isoformat()
 seen={}
 for ts,temp in points:
  if ts in seen and seen[ts]!=temp:
   note=f'批次内部冲突：{ts.isoformat()} 出现两个温度'
   s.add(TempBatch(probe=probe_code,revision=revision,state='rejected',points_count=len(points),note=note,received=now))
   return {'state':'rejected','note':note,'changed':False}
  seen[ts]=temp
 pts=sorted(seen.items())
 probe=s.query(Probe).filter_by(code=probe_code).first()
 if probe is None:
  probe=Probe(code=probe_code,current_rev=0);s.add(probe);s.flush()
 cur=probe.current_rev
 if revision<cur:
  note=f'低于当前修订 {cur}，整批忽略'
  s.add(TempBatch(probe=probe_code,revision=revision,state='ignored',points_count=len(pts),note=note,received=now))
  return {'state':'ignored','note':note,'changed':False,'current_rev':cur}
 if revision==cur:
  existing={p.ts:p.temp for p in s.query(TempPoint).filter_by(probe=probe_code,revision=cur)}
  for ts,temp in pts:
   if ts in existing and abs(existing[ts]-temp)>1e-6:
    note=f'与已接收修订 {cur} 在 {ts.isoformat()} 温度分歧，整批拒收'
    s.add(TempBatch(probe=probe_code,revision=revision,state='rejected',points_count=len(pts),note=note,received=now))
    return {'state':'rejected','note':note,'changed':False,'current_rev':cur}
  new_pts=[(ts,t) for ts,t in pts if ts not in existing]
  if not new_pts:
   note='与已接收日志完全一致，无变化'
   s.add(TempBatch(probe=probe_code,revision=revision,state='applied',points_count=0,note=note,received=now))
   return {'state':'applied','note':note,'changed':False,'current_rev':cur}
  for ts,temp in new_pts:s.add(TempPoint(probe=probe_code,revision=cur,ts=ts,temp=temp))
  note=f'同修订合并 {len(new_pts)} 个新时刻'
 else:
  for ts,temp in pts:s.add(TempPoint(probe=probe_code,revision=revision,ts=ts,temp=temp))
  probe.current_rev=revision
  note=f'修订 {revision} 替换修订 {cur}' if cur else f'首次接收修订 {revision}'
 n=mark_probe_pending(s,probe_code)
 bump_gen(s)
 s.add(TempBatch(probe=probe_code,revision=revision,state='applied',points_count=len(pts),note=f'{note}；{n} 个样本待重算',received=now))
 return {'state':'applied','note':note,'changed':True,'current_rev':max(cur,revision),'pending':n}
