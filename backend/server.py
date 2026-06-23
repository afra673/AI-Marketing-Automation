import os
import bcrypt
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel

# ── Database Setup ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# Fix for Railway PostgreSQL URLs (they use postgres:// but SQLAlchemy needs postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── Models ──────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    is_admin = Column(Boolean, default=False)

# ── Startup: Auto-create tables + seed admin ────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin_email = os.getenv("ADMIN_EMAIL", "admin@demo.com")
        admin_password = os.getenv("ADMIN_PASSWORD", "password123")
        existing = db.query(User).filter(User.email == admin_email).first()
        if not existing:
            hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
            db.add(User(email=admin_email, password=hashed, is_admin=True))
            db.commit()
    finally:
        db.close()
    yield

# ── App ─────────────────────────────────────────────────────────
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB Dependency ───────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── Schemas ─────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

# ── Routes ──────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "AI Marketing Automation API is running"}

@app.post("/api/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not bcrypt.checkpw(data.password.encode(), user.password.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"message": "Login successful", "email": user.email, "is_admin": user.is_admin}

@app.get("/api/debug/users")
def debug_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {"id": u.id, "email": u.email, "is_admin": u.is_admin, "password_hashed": bool(u.password)}
        for u in users
    ]
