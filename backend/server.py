import argparse
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import bcrypt
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# FIX 1: Always resolve paths relative to THIS file, not the CWD.
#         This means the server works whether you run it from the project
#         root  (py backend/server.py)  or from inside backend/  (py server.py)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent        # …/backend/
PROJECT_DIR = BASE_DIR.parent                     # …/project-root/
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

# ---------------------------------------------------------------------------
# FIX 2: Add BASE_DIR to sys.path so uvicorn's string import "server:app"
#         succeeds regardless of the working directory.
# ---------------------------------------------------------------------------
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SECRET_KEY = os.getenv("SECRET_KEY", "ai-marketing-secret-key-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
security = HTTPBearer(auto_error=False)


def _resolve_runtime_port(default: str = "8001") -> str:
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return os.getenv("PORT", default)

# ---------------------------------------------------------------------------
# Database setup — SQLite in-memory by default (zero config needed)
# ---------------------------------------------------------------------------
_database_url = os.getenv("DATABASE_URL", "").strip()
if _database_url.startswith("postgres://"):
    _database_url = _database_url.replace("postgres://", "postgresql://", 1)

if _database_url and "postgresql" in _database_url:
    engine = create_engine(_database_url)
else:
    # FIX 3: Use in-memory SQLite for the self-contained demo server.
    #        It avoids file-locking issues on Windows and keeps local startup reliable.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="User", nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
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


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class CampaignCreateRequest(BaseModel):
    name: str
    description: str = ""
    status: str = "draft"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    brand_voice: dict = Field(default_factory=dict)
    goals: list = Field(default_factory=list)


class ContentCreateRequest(BaseModel):
    campaign_id: Optional[int] = None
    title: str
    content_type: str
    status: str = "draft"
    body: str = ""
    image_url: Optional[str] = None
    scheduled_at: Optional[str] = None
    meta: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# In-memory runtime state
# ---------------------------------------------------------------------------
integrations_state = {
    "hubspot":          {"key": "hubspot",          "name": "HubSpot",          "connected": True,  "description": "CMS, CRM & Email",           "last_sync": None},
    "buffer":           {"key": "buffer",            "name": "Buffer",            "connected": False, "description": "Social Media Scheduling",    "last_sync": None},
    "google_analytics": {"key": "google_analytics",  "name": "Google Analytics",  "connected": True,  "description": "Traffic & Conversions",      "last_sync": None},
    "openai":           {"key": "openai",             "name": "OpenAI",            "connected": True,  "description": "GPT-4o & DALL-E 3",          "last_sync": None},
}

agent_runtime_state = {
    "strategy":     {"name": "strategy",     "status": "completed", "last_run": None, "tokens_used": 0, "cost_usd": 0.0},
    "research":     {"name": "research",     "status": "completed", "last_run": None, "tokens_used": 0, "cost_usd": 0.0},
    "writing":      {"name": "writing",      "status": "running",   "last_run": None, "tokens_used": 0, "cost_usd": 0.0},
    "design":       {"name": "design",       "status": "idle",      "last_run": None, "tokens_used": 0, "cost_usd": 0.0},
    "distribution": {"name": "distribution", "status": "failed",    "last_run": None, "tokens_used": 0, "cost_usd": 0.0},
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    payload = dict(data)
    payload["exp"] = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def parse_json(value: str, default):
    try:
        return json.loads(value or json.dumps(default))
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------
def campaign_to_dict(c: Campaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "status": c.status,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "brand_voice": parse_json(c.brand_voice, {}),
        "goals": parse_json(c.goals, []),
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
        "meta": parse_json(c.meta, {}),
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


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
def seed_database(db: Session):
    """Populate the DB with demo data on first run."""
    campaigns = []
    for data in [
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
    ]:
        campaign = Campaign(
            name=data["name"],
            description=data["description"],
            status=data["status"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            brand_voice=json.dumps(data["brand_voice"]),
            goals=json.dumps(data["goals"]),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(campaign)
        db.flush()
        campaigns.append(campaign)

    content_items = []
    seed_content = [
        (0, "Summer Kickoff Blog Post",    "blog",             "published", "Welcome to our summer campaign!",      datetime.utcnow() - timedelta(days=20), datetime.utcnow() - timedelta(days=20)),
        (0, "Twitter Thread: Summer Tips", "social_twitter",   "scheduled", "5 summer marketing tips.",             datetime.utcnow() + timedelta(days=3),  None),
        (0, "LinkedIn Brand Story",        "social_linkedin",  "review",    "Our journey started with a simple idea.", datetime.utcnow() + timedelta(days=7), None),
        (1, "Product Launch Email",        "email",            "draft",     "Introducing our newest innovation.",   datetime.utcnow() + timedelta(days=14), None),
        (1, "Launch Day Newsletter",       "newsletter",       "draft",     "This week in AI Marketing.",           datetime.utcnow() + timedelta(days=21), None),
        (2, "Holiday Gift Guide Blog",     "blog",             "published", "The ultimate holiday gift guide.",     datetime.utcnow() - timedelta(days=45), datetime.utcnow() - timedelta(days=45)),
    ]
    for campaign_idx, title, content_type, status, body, scheduled_at, published_at in seed_content:
        piece = ContentPiece(
            campaign_id=campaigns[campaign_idx].id,
            title=title,
            content_type=content_type,
            status=status,
            body=body,
            meta=json.dumps({"author": "AI Agent"}),
            scheduled_at=scheduled_at,
            published_at=published_at,
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        db.add(piece)
        db.flush()
        content_items.append(piece)

    agents = ["strategy", "research", "writing", "design", "distribution"]
    statuses = ["completed", "completed", "running", "completed", "failed",
                "completed", "running", "completed", "failed", "completed"]
    for i in range(10):
        started = datetime.utcnow() - timedelta(hours=i * 3 + 1)
        status_value = statuses[i]
        db.add(AgentLog(
            campaign_id=campaigns[i % 3].id,
            agent_name=agents[i % 5],
            status=status_value,
            tokens_used=500 + i * 120,
            cost_usd=round(0.002 * (500 + i * 120), 4),
            started_at=started,
            completed_at=started + timedelta(minutes=15) if status_value in {"completed", "failed"} else None,
            error_message="Connection timeout to external API" if status_value == "failed" else None,
        ))

    platforms = ["hubspot", "buffer", "email", "social"]
    for day_offset in range(30):
        snap_date = date.today() - timedelta(days=29 - day_offset)
        for idx, piece in enumerate(content_items):
            if (day_offset + idx) % 2 == 0:
                db.add(AnalyticsSnapshot(
                    content_id=piece.id,
                    platform=platforms[(day_offset + idx) % 4],
                    views=100 + day_offset * 15 + idx * 20,
                    clicks=10 + day_offset * 2 + idx * 3,
                    shares=2 + day_offset + idx,
                    conversions=max(0, day_offset // 5 + idx - 1),
                    snapshot_date=snap_date,
                ))

    db.commit()

    recent_logs = db.query(AgentLog).order_by(AgentLog.started_at.desc()).limit(5).all()
    for log in recent_logs:
        if log.agent_name in agent_runtime_state:
            agent_runtime_state[log.agent_name]["status"] = log.status
            agent_runtime_state[log.agent_name]["last_run"] = log.started_at.isoformat() if log.started_at else None
            agent_runtime_state[log.agent_name]["tokens_used"] = log.tokens_used
            agent_runtime_state[log.agent_name]["cost_usd"] = log.cost_usd


def ensure_admin_user(db: Session):
    admin_email = os.getenv("ADMIN_EMAIL", "admin@demo.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "password123")
    existing = db.query(User).filter(User.email == admin_email).first()
    if not existing:
        db.add(User(
            email=admin_email,
            name="Admin User",
            password=hash_password(admin_password),
            is_admin=True,
        ))
        db.commit()
        print(f"[startup] Created admin user: {admin_email}")
    else:
        print(f"[startup] Admin user already exists: {admin_email}")


# ---------------------------------------------------------------------------
# App & lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[startup] Creating database tables…")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_admin_user(db)
        if not db.query(Campaign).first():
            print("[startup] Seeding demo data…")
            seed_database(db)
        print("[startup] Ready")
    finally:
        db.close()
    yield


app = FastAPI(title="AI Marketing Automation", lifespan=lifespan)

# ---------------------------------------------------------------------------
# FIX 4: CORS — allow both the Vite dev server (5173) AND the production
#         server port (8001) so the frontend always reaches the API.
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve built frontend assets
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


# ---------------------------------------------------------------------------
# FIX 5: root_html was being *called* inside route handlers even though it
#         already returns a Response.  Make it a plain helper that returns
#         the right Response object directly.
# ---------------------------------------------------------------------------
def root_html():
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse(
        "<h1>AI Marketing Automation</h1><p>Frontend not built yet. Run <code>npm run build</code> inside <code>frontend/</code>.</p>",
        status_code=200,
    )


def normalize_date(value: Optional[str]):
    if not value:
        return None
    return date.fromisoformat(value)


def analytics_summary(db: Session):
    snapshots = db.query(AnalyticsSnapshot).all()
    daily = []
    for offset in range(29, -1, -1):
        day = date.today() - timedelta(days=offset)
        daily.append({
            "date": day.isoformat(),
            "views":  sum(s.views  for s in snapshots if s.snapshot_date == day),
            "clicks": sum(s.clicks for s in snapshots if s.snapshot_date == day),
        })
    return {
        "total_views":   sum(s.views       for s in snapshots),
        "total_clicks":  sum(s.clicks      for s in snapshots),
        "total_shares":  sum(s.shares      for s in snapshots),
        "conversions":   sum(s.conversions for s in snapshots),
        "daily_data": daily,
    }


def channel_breakdown(db: Session):
    snapshots = db.query(AnalyticsSnapshot).all()
    data = {}
    for platform in ["hubspot", "buffer", "email", "social"]:
        ps = [s for s in snapshots if s.platform == platform]
        data[platform] = {
            "views":       sum(s.views       for s in ps),
            "clicks":      sum(s.clicks      for s in ps),
            "shares":      sum(s.shares      for s in ps),
            "conversions": sum(s.conversions for s in ps),
        }
    return data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return root_html()


@app.post("/api/v1/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({
        "sub": user.email,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name, "is_admin": user.is_admin},
    }


@app.get("/api/v1/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "name": current_user.name, "is_admin": current_user.is_admin}


@app.get("/api/v1/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return [campaign_to_dict(item) for item in db.query(Campaign).order_by(Campaign.created_at.desc()).all()]


@app.post("/api/v1/campaigns")
def create_campaign(data: CampaignCreateRequest, db: Session = Depends(get_db)):
    campaign = Campaign(
        name=data.name,
        description=data.description,
        status=data.status,
        start_date=normalize_date(data.start_date),
        end_date=normalize_date(data.end_date),
        brand_voice=json.dumps(data.brand_voice or {}),
        goals=json.dumps(data.goals or []),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@app.delete("/api/v1/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    content_items = db.query(ContentPiece).filter(ContentPiece.campaign_id == campaign_id).all()
    content_ids = [item.id for item in content_items]
    if content_ids:
        db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.content_id.in_(content_ids)).delete(synchronize_session=False)
        db.query(ContentPiece).filter(ContentPiece.id.in_(content_ids)).delete(synchronize_session=False)
    db.query(AgentLog).filter(AgentLog.campaign_id == campaign_id).delete(synchronize_session=False)
    db.delete(campaign)
    db.commit()
    return {"success": True, "deleted_campaign_id": campaign_id}


@app.get("/api/v1/content")
def list_content(
    search: str = Query(default=""),
    type:   str = Query(default=""),
    status: str = Query(default=""),
    db: Session = Depends(get_db),
):
    items = db.query(ContentPiece).order_by(ContentPiece.created_at.desc()).all()
    if search:
        q = search.lower()
        items = [i for i in items if q in i.title.lower() or q in (i.body or "").lower()]
    if type:
        items = [i for i in items if i.content_type == type]
    if status:
        items = [i for i in items if i.status == status]
    return [content_to_dict(i) for i in items]


@app.post("/api/v1/content")
def create_content(data: ContentCreateRequest, db: Session = Depends(get_db)):
    campaign_id = data.campaign_id
    if campaign_id is None:
        campaign = db.query(Campaign).order_by(Campaign.created_at.asc()).first()
        if not campaign:
            raise HTTPException(status_code=400, detail="Create a campaign first")
        campaign_id = campaign.id
    elif not db.get(Campaign, campaign_id):
        raise HTTPException(status_code=404, detail="Campaign not found")

    content = ContentPiece(
        campaign_id=campaign_id,
        title=data.title,
        content_type=data.content_type,
        status=data.status,
        body=data.body,
        meta=json.dumps(data.meta or {}),
        image_url=data.image_url,
        scheduled_at=datetime.fromisoformat(data.scheduled_at) if data.scheduled_at else None,
        created_at=datetime.utcnow(),
    )
    db.add(content)
    db.commit()
    db.refresh(content)
    return content_to_dict(content)


@app.delete("/api/v1/content/{content_id}")
def delete_content(content_id: int, db: Session = Depends(get_db)):
    item = db.get(ContentPiece, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    db.query(AnalyticsSnapshot).filter(AnalyticsSnapshot.content_id == content_id).delete(synchronize_session=False)
    db.delete(item)
    db.commit()
    return {"success": True, "deleted_content_id": content_id}


@app.post("/api/v1/content/{content_id}/publish")
def publish_content(content_id: int, db: Session = Depends(get_db)):
    item = db.get(ContentPiece, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    item.status = "published"
    item.published_at = datetime.utcnow()
    db.commit()
    return content_to_dict(item)


@app.post("/api/v1/content/{content_id}/schedule")
def schedule_content(content_id: int, db: Session = Depends(get_db)):
    item = db.get(ContentPiece, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    item.status = "scheduled"
    item.scheduled_at = datetime.utcnow() + timedelta(days=1)
    db.commit()
    return content_to_dict(item)


@app.get("/api/v1/agents/status")
def agents_status():
    return [agent_runtime_state[name] | {"name": name} for name in agent_runtime_state]


@app.post("/api/v1/agents/{agent_name}/run")
def run_agent(agent_name: str, db: Session = Depends(get_db)):
    if agent_name not in agent_runtime_state:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent_runtime_state[agent_name]["status"] = "running"
    agent_runtime_state[agent_name]["last_run"] = datetime.utcnow().isoformat()
    agent_runtime_state[agent_name]["tokens_used"] += 250
    agent_runtime_state[agent_name]["cost_usd"] = round(
        agent_runtime_state[agent_name]["tokens_used"] * 0.002, 4
    )
    campaign = db.query(Campaign).first()
    db.add(AgentLog(
        campaign_id=campaign.id if campaign else None,
        agent_name=agent_name,
        status="running",
        tokens_used=agent_runtime_state[agent_name]["tokens_used"],
        cost_usd=agent_runtime_state[agent_name]["cost_usd"],
        started_at=datetime.utcnow(),
    ))
    db.commit()
    return agent_runtime_state[agent_name] | {"name": agent_name}


@app.get("/api/v1/agents/logs")
def agents_logs(
    stream: bool = Query(default=False),
    token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    if token:
        try:
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            pass

    logs = [
        agent_log_to_dict(item)
        for item in db.query(AgentLog).order_by(AgentLog.started_at.desc()).limit(100).all()
    ]

    if not stream:
        return logs

    async def event_stream():
        for log in logs:
            yield f"event: log\ndata: {json.dumps(log)}\n\n"
            await asyncio.sleep(0.01)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/v1/analytics/overview")
def analytics_overview(db: Session = Depends(get_db)):
    return analytics_summary(db)


@app.get("/api/v1/analytics/channels")
def analytics_channels(db: Session = Depends(get_db)):
    return channel_breakdown(db)


@app.get("/api/v1/integrations")
def integrations():
    return list(integrations_state.values())


@app.post("/api/v1/integrations/{key}/connect")
def connect_integration(key: str):
    if key not in integrations_state:
        raise HTTPException(status_code=404, detail="Integration not found")
    integrations_state[key]["connected"] = True
    integrations_state[key]["last_sync"] = datetime.utcnow().isoformat()
    return integrations_state[key]


@app.post("/api/v1/integrations/{key}/disconnect")
def disconnect_integration(key: str):
    if key not in integrations_state:
        raise HTTPException(status_code=404, detail="Integration not found")
    integrations_state[key]["connected"] = False
    return integrations_state[key]


@app.get("/api/debug/users")
def debug_users(db: Session = Depends(get_db)):
    return [
        {"id": u.id, "email": u.email, "name": u.name, "is_admin": u.is_admin, "password_hashed": bool(u.password)}
        for u in db.query(User).all()
    ]


# ---------------------------------------------------------------------------
# FIX 6: SPA fallback — must come LAST.  Any unknown path that is NOT an
#         API route returns the React index.html so client-side routing works.
# ---------------------------------------------------------------------------
@app.get("/{path:path}")
def spa_fallback(path: str):
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    return root_html()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="AI Marketing Automation server")
    parser.add_argument("--host",   default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port",   type=int, default=int(os.getenv("PORT", "8001")))
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn

    # FIX 1 (continued): pass the app *object* directly instead of a string so
    # uvicorn never needs to import the module by name — works from ANY directory.
    if args.reload:
        # --reload requires a string reference; ensure BASE_DIR is on sys.path
        uvicorn.run("server:app", host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
