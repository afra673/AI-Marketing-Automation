import os
<<<<<<< HEAD
=======
import asyncio
import json
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
>>>>>>> bf44866 (Final fix)
import bcrypt
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel

<<<<<<< HEAD
# ── Database Setup ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# Fix for Railway PostgreSQL URLs (they use postgres:// but SQLAlchemy needs postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
=======
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

SECRET_KEY = "ai-marketing-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer(auto_error=False)

# Database setup
_raw_url = os.environ.get("DATABASE_URL", "")
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)

if _raw_url and "postgresql" in _raw_url:
    engine = create_engine(_raw_url)
else:
    DB_PATH = BASE_DIR / "db.sqlite3"
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

>>>>>>> bf44866 (Final fix)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ── Models ──────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    is_admin = Column(Boolean, default=False)

<<<<<<< HEAD
# ── Startup: Auto-create tables + seed admin ────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
=======

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(String, default="draft")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    brand_voice = Column(Text, default="{}")
    goals = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    content_pieces = relationship("ContentPiece", back_populates="campaign")
    agent_logs = relationship("AgentLog", back_populates="campaign")


class ContentPiece(Base):
    __tablename__ = "content_pieces"
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    title = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    status = Column(String, default="draft")
    body = Column(Text, default="")
    meta = Column(Text, default="{}")
    image_url = Column(String, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    campaign = relationship("Campaign", back_populates="content_pieces")
    analytics = relationship("AnalyticsSnapshot", back_populates="content")


class AgentLog(Base):
    __tablename__ = "agent_logs"
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    agent_name = Column(String, nullable=False)
    status = Column(String, default="running")
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    campaign = relationship("Campaign", back_populates="agent_logs")


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(Integer, ForeignKey("content_pieces.id"), nullable=False)
    platform = Column(String, nullable=False)
    views = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    snapshot_date = Column(Date, nullable=False)
    content = relationship("ContentPiece", back_populates="analytics")


integrations_state = {
    "hubspot": {"name": "HubSpot", "connected": True, "description": "CMS, CRM & Email"},
    "buffer": {"name": "Buffer", "connected": False, "description": "Social Media Scheduling"},
    "google_analytics": {"name": "Google Analytics", "connected": True, "description": "Traffic & Conversions"},
    "openai": {"name": "OpenAI", "connected": True, "description": "GPT-4o & DALL-E 3"},
}

agent_runtime_state = {
    "strategy": {"status": "completed", "last_run": None, "tokens_used": 0},
    "research": {"status": "completed", "last_run": None, "tokens_used": 0},
    "writing": {"status": "running", "last_run": None, "tokens_used": 0},
    "design": {"status": "idle", "last_run": None, "tokens_used": 0},
    "distribution": {"status": "failed", "last_run": None, "tokens_used": 0},
}


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class CampaignCreate(BaseModel):
    name: str
    description: str = ""
    status: str = "draft"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    brand_voice: Optional[dict] = None
    goals: Optional[list] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    brand_voice: Optional[dict] = None
    goals: Optional[list] = None


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    content_type: Optional[str] = None
    status: Optional[str] = None
    body: Optional[str] = None
    meta: Optional[dict] = None
    image_url: Optional[str] = None
    scheduled_at: Optional[str] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def campaign_to_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "status": c.status,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "brand_voice": json.loads(c.brand_voice or "{}"),
        "goals": json.loads(c.goals or "[]"),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def content_to_dict(c: ContentPiece) -> dict:
    return {
        "id": c.id,
        "campaign_id": c.campaign_id,
        "title": c.title,
        "content_type": c.content_type,
        "status": c.status,
        "body": c.body,
        "meta": json.loads(c.meta or "{}"),
        "image_url": c.image_url,
        "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
        "published_at": c.published_at.isoformat() if c.published_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def agent_log_to_dict(log: AgentLog) -> dict:
    return {
        "id": log.id,
        "campaign_id": log.campaign_id,
        "agent_name": log.agent_name,
        "status": log.status,
        "tokens_used": log.tokens_used,
        "cost_usd": log.cost_usd,
        "started_at": log.started_at.isoformat() if log.started_at else None,
        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
        "error_message": log.error_message,
    }


def seed_database(db: Session):
    if db.query(User).filter(User.email == "admin@demo.com").first():
        return

    user = User(
        email="admin@demo.com",
        password_hash=hash_password("password123"),
        name="Admin User",
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()

    campaigns_data = [
        {
            "name": "Summer Brand Awareness",
            "description": "Increase brand visibility across social channels during summer season.",
            "status": "active",
            "start_date": date.today() - timedelta(days=30),
            "end_date": date.today() + timedelta(days=60),
            "brand_voice": {"tone": "energetic", "style": "casual"},
            "goals": ["brand awareness", "social engagement"],
        },
        {
            "name": "Product Launch Q3",
            "description": "Launch new product line with coordinated multi-channel campaign.",
            "status": "draft",
            "start_date": date.today() + timedelta(days=14),
            "end_date": date.today() + timedelta(days=90),
            "brand_voice": {"tone": "professional", "style": "authoritative"},
            "goals": ["product launch", "lead generation"],
        },
        {
            "name": "Holiday Email Series",
            "description": "Seasonal email nurture series for holiday promotions.",
            "status": "completed",
            "start_date": date.today() - timedelta(days=120),
            "end_date": date.today() - timedelta(days=30),
            "brand_voice": {"tone": "warm", "style": "festive"},
            "goals": ["email conversions", "customer retention"],
        },
    ]

    campaigns = []
    for cd in campaigns_data:
        c = Campaign(
            name=cd["name"],
            description=cd["description"],
            status=cd["status"],
            start_date=cd["start_date"],
            end_date=cd["end_date"],
            brand_voice=json.dumps(cd["brand_voice"]),
            goals=json.dumps(cd["goals"]),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(c)
        db.flush()
        campaigns.append(c)

    content_data = [
        {"campaign_id": campaigns[0].id, "title": "Summer Kickoff Blog Post", "content_type": "blog", "status": "published", "body": "Welcome to our summer campaign!", "scheduled_at": datetime.utcnow() - timedelta(days=20), "published_at": datetime.utcnow() - timedelta(days=20)},
        {"campaign_id": campaigns[0].id, "title": "Twitter Thread: Summer Tips", "content_type": "social_twitter", "status": "scheduled", "body": "5 summer marketing tips.", "scheduled_at": datetime.utcnow() + timedelta(days=3)},
        {"campaign_id": campaigns[0].id, "title": "LinkedIn Brand Story", "content_type": "social_linkedin", "status": "review", "body": "Our journey started with a simple idea.", "scheduled_at": datetime.utcnow() + timedelta(days=7)},
        {"campaign_id": campaigns[1].id, "title": "Product Launch Email", "content_type": "email", "status": "draft", "body": "Introducing our newest innovation.", "scheduled_at": datetime.utcnow() + timedelta(days=14)},
        {"campaign_id": campaigns[1].id, "title": "Launch Day Newsletter", "content_type": "newsletter", "status": "draft", "body": "This week in AI Marketing.", "scheduled_at": datetime.utcnow() + timedelta(days=21)},
        {"campaign_id": campaigns[2].id, "title": "Holiday Gift Guide Blog", "content_type": "blog", "status": "published", "body": "The ultimate holiday gift guide.", "scheduled_at": datetime.utcnow() - timedelta(days=45), "published_at": datetime.utcnow() - timedelta(days=45)},
    ]

    content_pieces = []
    for cd in content_data:
        cp = ContentPiece(
            campaign_id=cd["campaign_id"],
            title=cd["title"],
            content_type=cd["content_type"],
            status=cd["status"],
            body=cd["body"],
            meta=json.dumps({"author": "AI Agent"}),
            scheduled_at=cd.get("scheduled_at"),
            published_at=cd.get("published_at"),
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        db.add(cp)
        db.flush()
        content_pieces.append(cp)

    agent_names = ["strategy", "research", "writing", "design", "distribution"]
    agent_statuses = ["completed", "completed", "running", "completed", "failed", "completed", "running", "completed", "failed", "completed"]
    for i in range(10):
        started = datetime.utcnow() - timedelta(hours=i * 3 + 1)
        status_val = agent_statuses[i]
        completed = started + timedelta(minutes=15) if status_val in ("completed", "failed") else None
        log = AgentLog(
            campaign_id=campaigns[i % 3].id,
            agent_name=agent_names[i % 5],
            status=status_val,
            tokens_used=500 + i * 120,
            cost_usd=round(0.002 * (500 + i * 120), 4),
            started_at=started,
            completed_at=completed,
            error_message="Connection timeout to external API" if status_val == "failed" else None,
        )
        db.add(log)

    platforms = ["hubspot", "buffer", "email", "social"]
    for day_offset in range(30):
        snap_date = date.today() - timedelta(days=29 - day_offset)
        for j, cp in enumerate(content_pieces):
            if (day_offset + j) % 2 == 0:
                platform = platforms[(day_offset + j) % 4]
                snap = AnalyticsSnapshot(
                    content_id=cp.id,
                    platform=platform,
                    views=100 + day_offset * 15 + j * 20,
                    clicks=10 + day_offset * 2 + j * 3,
                    shares=2 + day_offset + j,
                    conversions=max(0, day_offset // 5 + j - 1),
                    snapshot_date=snap_date,
                )
                db.add(snap)

    db.commit()

    logs = db.query(AgentLog).order_by(AgentLog.started_at.desc()).limit(5).all()
    for log in logs:
        if log.agent_name in agent_runtime_state:
            agent_runtime_state[log.agent_name]["status"] = log.status
            agent_runtime_state[log.agent_name]["last_run"] = log.started_at.isoformat()
            agent_runtime_state[log.agent_name]["tokens_used"] = log.tokens_used


FALLBACK_HTML = """<!DOCTYPE html>
<html>
<head><title>AI Marketing Automation</title></head>
<body style="background:#0f172a;color:#f1f5f9;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column">
<h1>AI Marketing Automation</h1>
<p>Build the frontend first:</p>
<code style="background:#1e293b;padding:16px;border-radius:8px;display:block">cd frontend && npm install && npm run build</code>
<p>Then restart the server.</p>
</body>
</html>"""

app = FastAPI(title="AI Marketing Automation")


@app.on_event("startup")
def on_startup():
>>>>>>> bf44866 (Final fix)
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
