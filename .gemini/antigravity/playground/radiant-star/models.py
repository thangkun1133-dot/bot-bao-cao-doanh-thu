from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, Float, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    group_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String(255))
    added_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Group(group_id={self.group_id}, name={self.name})>"


class Revenue(Base):
    __tablename__ = 'revenues'

    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.now)
    note = Column(String(255), nullable=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(100), nullable=True)
    full_name = Column(String(200), nullable=True)
    group_id = Column(BigInteger, nullable=True)   # None = private chat
    invoice_path = Column(String(500), nullable=True)
    source = Column(String(20), default='manual')  # 'manual' or 'invoice'

    def __repr__(self):
        return f"<Revenue(amount={self.amount}, date={self.date}, source={self.source})>"
