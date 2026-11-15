import os,random
from datetime import datetime,timedelta,timezone
from src.config.database import Base,engine,Session
from src.models.entities import User,Shipment,Sample,Probe,TempPoint,TempBatch
from src.utils.security import hash_password
def demo_logs(rng):
 '''两条探头的演示日志：P-01 冷藏含两段超温与一段缺测；P-02 冷冻含一段超温。'''
 p1=[];t0=datetime(2026,11,14,7,55)
 for i in range(27):
  off=i*5
  if 70<=off<95:continue
  temp=2.4+rng.uniform(-.4,.4)
  if 35<=off<60:temp=5.3+rng.uniform(-.2,.4)
  if 100<=off<115:temp=6.1+rng.uniform(-.2,.3)
  p1.append((t0+timedelta(minutes=off),round(temp,2)))
 p2=[];t0=datetime(2026,11,14,8,50)
 for i in range(21):
  off=i*10
  temp=-21+rng.uniform(-.5,.5)
  if 90<=off<=120:temp=-16.4+rng.uniform(-.3,.3)
  p2.append((t0+timedelta(minutes=off),round(temp,2)))
 return [('P-01',1,p1),('P-02',1,p2)]
def seed():
 Base.metadata.create_all(engine);rng=random.Random(3102)
 with Session() as s:
  for role in ('admin','analyst','viewer'):
   email=role+'@demo.local'
   if not s.query(User).filter_by(email=email).first():s.add(User(email=email,role=role,password=hash_password('Demo123!')))
  s.commit()
  for i in range(60):
   code=f'XD-1115-{i+1:03}'
   ship=s.query(Shipment).filter_by(code=code).first()
   if not ship:
    ship=Shipment(code=code,route=f'鲜达线路 {i%12+1:02}',zone=('冷藏' if i<30 else '冷冻' if i<50 else '常温对照'),driver=f'驾驶员{i%12+1}');s.add(ship);s.flush()
   exposure=round(rng.uniform(3,85),1);loss=round(min(100,1+exposure*.11+rng.uniform(-.9,.9)),2)
   if i>=50:exposure=20
   if not s.query(Sample).filter_by(code=code+'-S').first():s.add(Sample(shipment_id=ship.id,code=code+'-S',exposure=None if i in (5,37) else exposure,excursions=int(exposure/10),loss=loss))
  now=datetime.now(timezone.utc).isoformat()
  for code,rev,points in demo_logs(rng):
   if not s.query(Probe).filter_by(code=code).first():
    s.add(Probe(code=code,current_rev=rev))
    for ts,temp in points:s.add(TempPoint(probe=code,revision=rev,ts=ts,temp=temp))
    s.add(TempBatch(probe=code,revision=rev,state='applied',points_count=len(points),note='演示初始日志',received=now))
  autos=[('XD-1115-T01','鲜达线路 03','冷藏','驾驶员3','P-01','2026-11-14T08:00:00','2026-11-14T10:00:00',3.4),
   ('XD-1115-T02','鲜达线路 07','冷冻','驾驶员7','P-02','2026-11-14T09:00:00','2026-11-14T12:00:00',1.6)]
  for code,route,zone,driver,probe,dep,arr,loss in autos:
   ship=s.query(Shipment).filter_by(code=code).first()
   if not ship:
    ship=Shipment(code=code,route=route,zone=zone,driver=driver,probe=probe,depart_at=datetime.fromisoformat(dep),arrive_at=datetime.fromisoformat(arr));s.add(ship);s.flush()
   if not s.query(Sample).filter_by(code=code+'-S').first():s.add(Sample(shipment_id=ship.id,code=code+'-S',loss=loss,source='auto',calc_state='pending'))
  s.commit();print({'shipments':s.query(Shipment).count(),'samples':s.query(Sample).count(),'users':s.query(User).count(),'probes':s.query(Probe).count()})
 try:
  import redis
  redis.Redis.from_url(os.environ.get('REDIS_URL','redis://localhost:6379/0')).rpush('recalc',1)
 except Exception:pass
if __name__=='__main__':seed()
