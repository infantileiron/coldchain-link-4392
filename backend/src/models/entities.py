from sqlalchemy import Column,Integer,String,Float,JSON,Text,DateTime,UniqueConstraint
from src.config.database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String(100),unique=True);password=Column(String(200));role=Column(String(20))
class Shipment(Base):
 __tablename__='shipments'
 id=Column(Integer,primary_key=True);code=Column(String(60),unique=True);route=Column(String(60));zone=Column(String(20));driver=Column(String(60))
 probe=Column(String(60),nullable=True);depart_at=Column(DateTime,nullable=True);arrive_at=Column(DateTime,nullable=True)
 threshold=Column(Float,nullable=True);max_gap=Column(Integer,nullable=True)
class Sample(Base):
 __tablename__='samples'
 id=Column(Integer,primary_key=True);shipment_id=Column(Integer,index=True);code=Column(String(60),unique=True);exposure=Column(Float,nullable=True);excursions=Column(Integer,nullable=True);loss=Column(Float,nullable=True)
 source=Column(String(10),default='manual');calc_state=Column(String(10),nullable=True);pub_version=Column(Integer,nullable=True);detail=Column(JSON,nullable=True);calc_error=Column(Text,default='')
class Probe(Base):
 __tablename__='probes'
 id=Column(Integer,primary_key=True);code=Column(String(60),unique=True);current_rev=Column(Integer,default=0)
class TempPoint(Base):
 __tablename__='temp_points'
 __table_args__=(UniqueConstraint('probe','revision','ts'),)
 id=Column(Integer,primary_key=True);probe=Column(String(60),index=True);revision=Column(Integer);ts=Column(DateTime);temp=Column(Float)
class TempBatch(Base):
 __tablename__='temp_batches'
 id=Column(Integer,primary_key=True);probe=Column(String(60));revision=Column(Integer);state=Column(String(10));points_count=Column(Integer);note=Column(String(200));received=Column(String(40))
class Publication(Base):
 __tablename__='publications'
 id=Column(Integer,primary_key=True);version=Column(Integer,unique=True);gen=Column(Integer);sample_count=Column(Integer);created=Column(String(40))
class Meta(Base):
 __tablename__='meta'
 key=Column(String(40),primary_key=True);value=Column(String(200))
class Study(Base):
 __tablename__='studies'
 id=Column(Integer,primary_key=True);name=Column(String(100));zone=Column(String(20));feature=Column(String(30));state=Column(String(20),default='queued');result=Column(JSON,nullable=True);error=Column(Text,default='')
class Recommendation(Base):
 __tablename__='recommendations'
 id=Column(Integer,primary_key=True);study_id=Column(Integer);note=Column(Text);owner=Column(String(60));status=Column(String(20),default='draft')
class Audit(Base):
 __tablename__='audits'
 id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(200));created=Column(String(40))
