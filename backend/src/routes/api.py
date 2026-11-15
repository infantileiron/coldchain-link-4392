import os,json
import redis
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy.exc import IntegrityError
from src.config.database import db
from src.models.entities import User,Shipment,Sample,Study,Recommendation,Audit,Probe,TempPoint,TempBatch,Publication
from src.schemas.business import Login,ShipmentInput,SampleInput,LogBatchInput,StudyInput,RecommendationInput
from src.middlewares.auth import current,editor,admin
from src.utils.security import verify,token
from src.services.business import audit,dump
from src.services.logs import import_batch,norm_ts,bump_gen,sync_shipment_samples
from src.controllers.business import get_shipment,ensure_study,study_rows,pending_block_count,current_pub_version
router=APIRouter()
def enqueue(queue):
 try:redis.Redis.from_url(os.environ['REDIS_URL']).rpush(queue,1);return True
 except redis.RedisError:return False
@router.post('/auth/login')
def login(data:Login,s=Depends(db)):
 u=s.query(User).filter_by(email=data.email).first()
 if not u or not verify(data.password,u.password):raise HTTPException(401,'账号或密码错误')
 return {'token':token(u),'user':dump(u)}
@router.get('/me')
def me(u=Depends(current)):return dump(u)
@router.get('/shipments')
def ships(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Shipment).all()]
@router.post('/shipments')
def ship(data:ShipmentInput,u=Depends(editor),s=Depends(db)):
 r=Shipment(**data.model_dump());s.add(r)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'班次编号重复')
 audit(s,u,'创建班次 '+r.code);return dump(r)
@router.get('/samples')
def samples(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Sample).all()]
@router.post('/samples')
def sample(data:SampleInput,u=Depends(editor),s=Depends(db)):
 ship=get_shipment(s,data.shipment_id);r=Sample(**data.model_dump())
 if ship.probe:r.source='auto';r.exposure=None;r.excursions=None;r.calc_state='pending'
 s.add(r)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'样本编号重复')
 if ship.probe:enqueue('recalc')
 audit(s,u,'录入样本 '+r.code);return dump(r)
@router.get('/probes')
def probes(u=Depends(current),s=Depends(db)):
 return [{'id':p.id,'code':p.code,'current_rev':p.current_rev,'points':s.query(TempPoint).filter_by(probe=p.code,revision=p.current_rev).count()} for p in s.query(Probe).all()]
@router.get('/logs')
def logs(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(TempBatch).order_by(TempBatch.id.desc()).limit(100)]
@router.post('/logs')
def import_logs(data:LogBatchInput,u=Depends(editor),s=Depends(db)):
 pts=[(norm_ts(p.ts),p.temp) for p in data.points]
 result=import_batch(s,data.probe.strip(),data.revision,pts)
 s.commit()
 queued=enqueue('recalc') if result.get('changed') else False
 audit(s,u,f"导入温度日志 {data.probe} 修订{data.revision}：{result['state']}")
 if result['state']=='rejected':raise HTTPException(409,result['note'])
 return {**result,'queued':queued}
@router.post('/recalc')
def recalc(u=Depends(editor),s=Depends(db)):
 reset=0
 for smp in s.query(Sample).filter_by(calc_state='failed').all():smp.calc_state='pending';smp.calc_error='';reset+=1
 pending=s.query(Sample).filter_by(calc_state='pending').count();s.commit()
 queued=enqueue('recalc') if pending else False
 audit(s,u,f'手动重算（待发布 {pending}）');return {'pending':pending,'reset':reset,'queued':queued}
@router.get('/publications')
def pubs(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Publication).order_by(Publication.version.desc()).limit(50)]
@router.get('/studies')
def studies(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Study).order_by(Study.id.desc()).all()]
@router.post('/studies')
def study(data:StudyInput,u=Depends(editor),s=Depends(db)):
 blocked=pending_block_count(s)
 if blocked:raise HTTPException(409,f'存在 {blocked} 个待重算或失败的样本，全部发布后才能新建研究')
 rows=study_rows(s,data.zone);r=Study(**data.model_dump(),result={'snapshot':rows,'pub_version':current_pub_version(s)});s.add(r);s.commit()
 try:redis.Redis.from_url(os.environ['REDIS_URL']).rpush('studies',r.id)
 except redis.RedisError:
  r.state='failed';r.error='队列暂不可用，请重新创建研究';s.commit();raise HTTPException(503,r.error)
 audit(s,u,'提交研究 '+str(r.id));return dump(r)
@router.get('/studies/{i}')
def detail(i:int,u=Depends(current),s=Depends(db)):return dump(ensure_study(s,i))
@router.get('/studies/{i}/export')
def export(i:int,u=Depends(current),s=Depends(db)):
 r=ensure_study(s,i)
 if r.state!='done':raise HTTPException(409,'研究未成功完成')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="coldchain-link-{i}.json"'})
@router.get('/recommendations')
def recs(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Recommendation).order_by(Recommendation.id.desc()).all()]
@router.post('/recommendations')
def rec(data:RecommendationInput,u=Depends(editor),s=Depends(db)):
 if ensure_study(s,data.study_id).state!='done':raise HTTPException(409,'仅已完成研究可以起草建议')
 r=Recommendation(**data.model_dump());s.add(r);s.commit();audit(s,u,'起草建议 '+str(r.id));return dump(r)
@router.post('/recommendations/{i}/approve')
def approve(i:int,u=Depends(admin),s=Depends(db)):
 r=s.get(Recommendation,i)
 if not r:raise HTTPException(404,'建议不存在')
 r.status='approved';s.commit();audit(s,u,'签核建议 '+str(i));return dump(r)
@router.get('/audits')
def audits(u=Depends(admin),s=Depends(db)):return [dump(r) for r in s.query(Audit).order_by(Audit.id.desc()).limit(100)]

@router.put('/shipments/{i}')
def edit_ship(i:int,data:ShipmentInput,u=Depends(editor),s=Depends(db)):
 row=s.get(Shipment,i)
 if not row:raise HTTPException(404,'班次不存在')
 before=(row.probe,row.depart_at,row.arrive_at,row.threshold,row.max_gap,row.zone)
 for k,v in data.model_dump().items():setattr(row,k,v)
 after=(row.probe,row.depart_at,row.arrive_at,row.threshold,row.max_gap,row.zone)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'班次编号重复')
 n=0
 if before!=after:
  n=sync_shipment_samples(s,row)
  if n:bump_gen(s);s.commit();enqueue('recalc')
 audit(s,u,'修改班次 '+str(i)+(f'；{n} 个样本待重算' if n else ''));return dump(row)
@router.put('/samples/{i}')
def edit_sample(i:int,data:SampleInput,u=Depends(editor),s=Depends(db)):
 row=s.get(Sample,i)
 if not row:raise HTTPException(404,'样本不存在')
 ship=get_shipment(s,data.shipment_id)
 was_auto=row.source=='auto';moved=row.shipment_id!=data.shipment_id
 payload=data.model_dump()
 if ship.probe:payload.pop('exposure');payload.pop('excursions')
 for k,v in payload.items():setattr(row,k,v)
 recalc_needed=False
 if ship.probe:
  row.source='auto'
  if moved or not was_auto:
   row.exposure=None;row.excursions=None;row.pub_version=None;row.calc_state='pending';row.calc_error='';recalc_needed=True
 else:row.source='manual';row.calc_state=None
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'样本编号重复')
 if recalc_needed:enqueue('recalc')
 audit(s,u,'修改样本 '+str(i));return dump(row)
