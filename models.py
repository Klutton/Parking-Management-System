from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime

Base = declarative_base()


class Personnel(Base):
    __tablename__ = 'personnel'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    password = Column(String, nullable=False)  # Assume this is hashed
    department = Column(String, nullable=False)
    room_num = Column(String, nullable=False)
    phone = Column(String, nullable=False, unique=True)


class Vehicle(Base):
    __tablename__ = 'vehicle'
    id = Column(Integer, primary_key=True)
    plate = Column(String, nullable=False, unique=True)
    permissions = Column(String, nullable=False)
    last_in = Column(Integer, ForeignKey('vehicle_access_records.id'), nullable=True)
    last_out = Column(Integer, ForeignKey('vehicle_access_records.id'), nullable=True)
    paid = Column(Boolean, default=False, nullable=True)


class PersonnelParkingRelation(Base):
    __tablename__ = 'personnel_parking_relation'
    id = Column(Integer, primary_key=True)
    personnel_id = Column(Integer, ForeignKey('personnel.id'), nullable=False)
    plate = Column(String, ForeignKey('vehicle.plate'), nullable=False, unique=True)


class ParkingArea(Base):
    __tablename__ = 'parking_areas'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    permissions = Column(Integer, nullable=False)


class VehicleAccessRecord(Base):
    __tablename__ = 'vehicle_access_records'
    id = Column(Integer, primary_key=True)
    plate = Column(String, nullable=False)
    parking_id = Column(Integer, ForeignKey('parking_areas.id'), nullable=False)
    action = Column(Enum('IN', 'OUT', 'DENIED', name='access_action'), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


engine = None


def init(host, port, username, password, dbname):
    db_url = f"sqlalchemy_kingbase+psycopg2://{username}:{password}@{host}:{port}/{dbname}"
    global engine
    engine = create_engine(db_url)
    try:
        engine.connect()
    except Exception as e:
        raise RuntimeError(f"Failed to connect to the database: {e}")

    Base.metadata.create_all(engine)


def get_session():
    if not engine:
        raise RuntimeError("Database engine is not initialized. Call init() first.")
    Session = sessionmaker(bind=engine)
    session = Session()
    return session
