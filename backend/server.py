import argparse
import os
import asyncio
import json
import os
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Date
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sse_starlette.sse import EventSourceResponse
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "db.sqlite3")))
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

SECRET_KEY = "ai-marketing-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer(auto_error=False)
import psycopg2
os.makedirs("/data", exist_ok=True)
os.makedirs("/data", exist_ok=True)
DATABASE_URL = f"sqlite:////data/db.sqlite3"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


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
        {"campaign_id": campaigns[0].id, "title": "Summer Kickoff Blog Post", "content_type": "blog", "status": "published", "body": "Welcome to our summer campaign! Discover how we're bringing fresh energy to our brand this season.", "scheduled_at": datetime.utcnow() - timedelta(days=20), "published_at": datetime.utcnow() - timedelta(days=20)},
        {"campaign_id": campaigns[0].id, "title": "Twitter Thread: Summer Tips", "content_type": "social_twitter", "status": "scheduled", "body": "🌞 Thread: 5 summer marketing tips that actually work. 1/ Start with audience research...", "scheduled_at": datetime.utcnow() + timedelta(days=3)},
        {"campaign_id": campaigns[0].id, "title": "LinkedIn Brand Story", "content_type": "social_linkedin", "status": "review", "body": "Our journey started with a simple idea: make marketing smarter with AI.", "scheduled_at": datetime.utcnow() + timedelta(days=7)},
        {"campaign_id": campaigns[1].id, "title": "Product Launch Email", "content_type": "email", "status": "draft", "body": "Subject: Introducing our newest innovation. We're thrilled to announce...", "scheduled_at": datetime.utcnow() + timedelta(days=14)},
        {"campaign_id": campaigns[1].id, "title": "Launch Day Newsletter", "content_type": "newsletter", "status": "draft", "body": "This week in AI Marketing: Product launch preview, team updates, and exclusive early access.", "scheduled_at": datetime.utcnow() + timedelta(days=21)},
        {"campaign_id": campaigns[2].id, "title": "Holiday Gift Guide Blog", "content_type": "blog", "status": "published", "body": "The ultimate holiday gift guide for marketing professionals. Curated picks for every budget.", "scheduled_at": datetime.utcnow() - timedelta(days=45), "published_at": datetime.utcnow() - timedelta(days=45)},
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
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"name": user.name, "email": user.email},
    }


@app.post("/api/v1/auth/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    return {"message": "User registered successfully", "email": user.email}


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/campaigns")
def list_campaigns(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [campaign_to_dict(c) for c in campaigns]


@app.post("/api/v1/campaigns")
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = Campaign(
        name=body.name,
        description=body.description,
        status=body.status,
        start_date=date.fromisoformat(body.start_date) if body.start_date else None,
        end_date=date.fromisoformat(body.end_date) if body.end_date else None,
        brand_voice=json.dumps(body.brand_voice or {}),
        goals=json.dumps(body.goals or []),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return campaign_to_dict(c)


@app.get("/api/v1/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign_to_dict(c)


@app.put("/api/v1/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, body: CampaignUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if body.name is not None:
        c.name = body.name
    if body.description is not None:
        c.description = body.description
    if body.status is not None:
        c.status = body.status
    if body.start_date is not None:
        c.start_date = date.fromisoformat(body.start_date) if body.start_date else None
    if body.end_date is not None:
        c.end_date = date.fromisoformat(body.end_date) if body.end_date else None
    if body.brand_voice is not None:
        c.brand_voice = json.dumps(body.brand_voice)
    if body.goals is not None:
        c.goals = json.dumps(body.goals)
    c.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(c)
    return campaign_to_dict(c)


@app.delete("/api/v1/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(c)
    db.commit()
    return {"message": "Campaign deleted"}


@app.post("/api/v1/campaigns/{campaign_id}/run")
def run_campaign(campaign_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for agent_name in ["strategy", "research", "writing", "design", "distribution"]:
        log = AgentLog(
            campaign_id=campaign_id,
            agent_name=agent_name,
            status="running",
            tokens_used=0,
            cost_usd=0.0,
            started_at=datetime.utcnow(),
        )
        db.add(log)
        agent_runtime_state[agent_name]["status"] = "running"
        agent_runtime_state[agent_name]["last_run"] = datetime.utcnow().isoformat()
    db.commit()
    return {"status": "started"}


@app.get("/api/v1/content")
def list_content(
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(ContentPiece)
    if search:
        q = q.filter(ContentPiece.title.ilike(f"%{search}%"))
    if type:
        q = q.filter(ContentPiece.content_type == type)
    if status:
        q = q.filter(ContentPiece.status == status)
    items = q.order_by(ContentPiece.created_at.desc()).all()
    return [content_to_dict(c) for c in items]


@app.get("/api/v1/content/{content_id}")
def get_content(content_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Content not found")
    return content_to_dict(c)


@app.put("/api/v1/content/{content_id}")
def update_content(content_id: int, body: ContentUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Content not found")
    if body.title is not None:
        c.title = body.title
    if body.content_type is not None:
        c.content_type = body.content_type
    if body.status is not None:
        c.status = body.status
    if body.body is not None:
        c.body = body.body
    if body.meta is not None:
        c.meta = json.dumps(body.meta)
    if body.image_url is not None:
        c.image_url = body.image_url
    if body.scheduled_at is not None:
        c.scheduled_at = datetime.fromisoformat(body.scheduled_at) if body.scheduled_at else None
    db.commit()
    db.refresh(c)
    return content_to_dict(c)


@app.post("/api/v1/content/{content_id}/publish")
def publish_content(content_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Content not found")
    c.status = "published"
    c.published_at = datetime.utcnow()
    db.commit()
    db.refresh(c)
    return content_to_dict(c)


@app.post("/api/v1/content/{content_id}/schedule")
def schedule_content(content_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(ContentPiece).filter(ContentPiece.id == content_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Content not found")
    c.status = "scheduled"
    if not c.scheduled_at:
        c.scheduled_at = datetime.utcnow() + timedelta(days=1)
    db.commit()
    db.refresh(c)
    return content_to_dict(c)


@app.get("/api/v1/agents/status")
def agents_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    agents = []
    for name in ["strategy", "research", "writing", "design", "distribution"]:
        latest = (
            db.query(AgentLog)
            .filter(AgentLog.agent_name == name)
            .order_by(AgentLog.started_at.desc())
            .first()
        )
        runtime = agent_runtime_state.get(name, {})
        agents.append({
            "name": name,
            "status": runtime.get("status") or (latest.status if latest else "idle"),
            "last_run": runtime.get("last_run") or (latest.started_at.isoformat() if latest and latest.started_at else None),
            "tokens_used": latest.tokens_used if latest else 0,
            "cost_usd": latest.cost_usd if latest else 0.0,
        })
    return agents


def _run_agent(agent_name: str, db: Session):
    log = AgentLog(
        agent_name=agent_name,
        status="running",
        tokens_used=0,
        cost_usd=0.0,
        started_at=datetime.utcnow(),
    )
    db.add(log)
    db.commit()
    agent_runtime_state[agent_name]["status"] = "running"
    agent_runtime_state[agent_name]["last_run"] = datetime.utcnow().isoformat()
    return {"status": "running"}


@app.post("/api/v1/agents/strategy/run")
def run_strategy(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _run_agent("strategy", db)


@app.post("/api/v1/agents/research/run")
def run_research(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _run_agent("research", db)


@app.post("/api/v1/agents/writing/run")
def run_writing(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _run_agent("writing", db)


@app.post("/api/v1/agents/design/run")
def run_design(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _run_agent("design", db)


@app.post("/api/v1/agents/distribution/run")
def run_distribution(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _run_agent("distribution", db)


def get_user_from_token(token: str, db: Session) -> User:
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


@app.get("/api/v1/agents/logs")
async def agent_logs(
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials:
        user = get_current_user(credentials, db)
    elif token:
        user = get_user_from_token(token, db)
    else:
        raise HTTPException(status_code=401, detail="Not authenticated")

    accept = request.headers.get("accept", "")
    if "text/event-stream" not in accept and request.query_params.get("stream") != "true":
        logs = db.query(AgentLog).order_by(AgentLog.started_at.desc()).limit(10).all()
        return [agent_log_to_dict(log) for log in logs]

    async def event_generator():
        messages = [
            "Strategy agent analyzing campaign goals...",
            "Research agent gathering market data...",
            "Writing agent generating blog draft...",
            "Design agent creating visual assets...",
            "Distribution agent scheduling social posts...",
            "Strategy agent completed goal analysis.",
            "Research agent found 12 competitor insights.",
            "Writing agent produced 850-word article.",
            "Design agent exported banner images.",
            "Distribution agent queued 5 social posts.",
        ]
        idx = 0
        while True:
            if await request.is_disconnected():
                break
            msg = messages[idx % len(messages)]
            ts = datetime.utcnow().isoformat()
            data = json.dumps({"message": msg, "timestamp": ts, "agent": ["strategy", "research", "writing", "design", "distribution"][idx % 5]})
            yield {"event": "log", "data": data}
            idx += 1
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())


@app.get("/api/v1/analytics/overview")
def analytics_overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    snapshots = db.query(AnalyticsSnapshot).all()
    total_views = sum(s.views for s in snapshots)
    total_clicks = sum(s.clicks for s in snapshots)
    total_shares = sum(s.shares for s in snapshots)
    conversions = sum(s.conversions for s in snapshots)

    daily_map = {}
    for s in snapshots:
        key = s.snapshot_date.isoformat()
        if key not in daily_map:
            daily_map[key] = {"date": key, "views": 0, "clicks": 0, "shares": 0, "conversions": 0}
        daily_map[key]["views"] += s.views
        daily_map[key]["clicks"] += s.clicks
        daily_map[key]["shares"] += s.shares
        daily_map[key]["conversions"] += s.conversions

    daily_data = sorted(daily_map.values(), key=lambda x: x["date"])
    if not daily_data:
        for i in range(30):
            d = (date.today() - timedelta(days=29 - i)).isoformat()
            daily_data.append({"date": d, "views": 0, "clicks": 0, "shares": 0, "conversions": 0})

    return {
        "total_views": total_views,
        "total_clicks": total_clicks,
        "total_shares": total_shares,
        "conversions": conversions,
        "daily_data": daily_data,
    }


@app.get("/api/v1/analytics/channels")
def analytics_channels(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    platforms = ["hubspot", "buffer", "email", "social"]
    result = {}
    for p in platforms:
        snaps = db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.platform == p).all()
        result[p] = {
            "views": sum(s.views for s in snaps),
            "clicks": sum(s.clicks for s in snaps),
        }
    return result


@app.get("/api/v1/integrations")
def list_integrations(user: User = Depends(get_current_user)):
    return [
        {
            "key": key,
            "name": val["name"],
            "description": val["description"],
            "connected": val["connected"],
        }
        for key, val in integrations_state.items()
    ]


@app.post("/api/v1/integrations/{name}/connect")
def connect_integration(name: str, user: User = Depends(get_current_user)):
    if name not in integrations_state:
        raise HTTPException(status_code=404, detail="Integration not found")
    integrations_state[name]["connected"] = True
    return {"name": name, "connected": True}


@app.post("/api/v1/integrations/{name}/disconnect")
def disconnect_integration(name: str, user: User = Depends(get_current_user)):
    if name not in integrations_state:
        raise HTTPException(status_code=404, detail="Integration not found")
    integrations_state[name]["connected"] = False
    return {"name": name, "connected": False}


def setup_static_routes():
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/login")
        async def serve_login():
            return FileResponse(str(index_path))

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            file_path = FRONTEND_DIST / full_path
            if full_path and file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(index_path))
    else:
        @app.get("/")
        async def fallback_root():
            return HTMLResponse(content=FALLBACK_HTML)


setup_static_routes()


def main():
    parser = argparse.ArgumentParser(description="AI Marketing Automation Server")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    port = int(os.environ.get("PORT", args.port))

    print(f"  [OK] AI Marketing Automation running at http://127.0.0.1:{port}")
    print(f"  [OK] API docs at http://127.0.0.1:{port}/docs")
    print(f"  [OK] Open http://127.0.0.1:{port} in your browser")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
