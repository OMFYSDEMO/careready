"""CareReady AI — Phase 1 data models (SQLAlchemy 2.0)."""
from datetime import datetime, date
from sqlalchemy import (Column, Integer, String, Float, Date, DateTime,
                        ForeignKey, Text, Boolean, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./careready.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

KQ_IDS = ["safe", "effective", "caring", "responsive", "wellled"]
KQ_NAMES = {"safe": "Safe", "effective": "Effective", "caring": "Caring",
            "responsive": "Responsive", "wellled": "Well-led"}


class Organisation(Base):
    __tablename__ = "organisations"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    strapline = Column(String, default="")
    plan = Column(String, default="Phase 1")


class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    name = Column(String, nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # Super Admin / Registered Manager / ...
    password_hash = Column(String, nullable=False)
    password_salt = Column(String, nullable=False)


class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    name = Column(String)
    role = Column(String)
    dbs_status = Column(String, default="Current")        # Current / Review required / Expired
    dbs_renewal = Column(Date, nullable=True)
    training_pct = Column(Integer, default=100)
    supervision_status = Column(String, default="Up to date")  # Up to date / Due <date> / Due today / Overdue
    location = relationship("Location")


class ServiceUser(Base):
    __tablename__ = "service_users"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    initials = Column(String)
    name = Column(String)
    careplan_status = Column(String, default="Current")   # Current / Review due <d> / Review overdue (...)
    careplan_state = Column(String, default="green")      # green / amber / red
    risk_note = Column(String, default="")
    location = relationship("Location")


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    ref = Column(String)
    title = Column(String)
    severity = Column(String)   # High / Medium / Low
    status = Column(String)     # Open / Under review / Closed
    occurred = Column(String)   # display string for Phase 1
    location = relationship("Location")


class ComplianceAction(Base):
    __tablename__ = "actions"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    ref = Column(String)
    title = Column(String)
    owner = Column(String)
    due = Column(String)
    priority = Column(String)   # High / Medium / Low
    status = Column(String)     # Not started / In progress / Scheduled / Done
    kq = Column(String, default="wellled")


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    title = Column(String)
    category = Column(String)
    kq = Column(String)                     # safe/effective/caring/responsive/wellled
    status = Column(String)                 # current / expiring / expired / missing
    expiry = Column(Date, nullable=True)
    filename = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    note = Column(String, default="")


class TrendPoint(Base):
    __tablename__ = "trend"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    month = Column(String)   # "Apr"
    value = Column(Integer)


class Activity(Base):
    __tablename__ = "activity"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    text = Column(String)
    when = Column(String)
    colour = Column(String, default="blue")
    created = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))
    text = Column(String)
    when = Column(String)
    colour = Column(String, default="blue")
    read = Column(Boolean, default=False)


def init_db():
    Base.metadata.create_all(engine)
