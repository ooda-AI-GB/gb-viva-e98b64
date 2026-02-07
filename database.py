from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum
from datetime import date, timedelta
import random

DATABASE_URL = "sqlite:///./data/expenses.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ExpenseStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class ExpenseCategory(str, enum.Enum):
    TRAVEL = "travel"
    MEALS = "meals"
    SUPPLIES = "supplies"
    OTHER = "other"

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    amount = Column(Float)
    category = Column(Enum(ExpenseCategory))
    date = Column(Date)
    description = Column(String)
    receipt_reference = Column(String, nullable=True)
    status = Column(Enum(ExpenseStatus), default=ExpenseStatus.PENDING)

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(Expense).count() == 0:
        seed_data(db)
    db.close()

def seed_data(db):
    users = ["employee1", "employee2", "manager"]
    categories = list(ExpenseCategory)
    statuses = list(ExpenseStatus)
    
    for i in range(15):
        expense = Expense(
            username=random.choice(users[:2]),
            amount=round(random.uniform(10.0, 500.0), 2),
            category=random.choice(categories),
            date=date.today() - timedelta(days=random.randint(0, 60)),
            description=f"Sample expense #{i+1}",
            receipt_reference=f"RECEIPT-00{i+1}",
            status=random.choice(statuses)
        )
        db.add(expense)
    
    db.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
