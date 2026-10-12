import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from cachetools import TTLCache
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .analytics import Analyzer, label, sentiment, sentiment_detail
from .config import CACHE_TTL, CORS_ORIGINS, SEED_ON_START
from .db import (
    AnalyticsEvent,
    Base,
    Comment,
    Content,
    Interaction,
    RecommendationFeedback,
    SessionLocal,
    TrendingTopic,
    User,
    UserInterest,
    engine,
)
from .recommender import Recommender
from .security import (
    create_token,
    decode_token,
    hash_password,
    password_valid,
    verify_password,
)
from .seed import SAMPLE, SAMPLE_COMMENTS

# ============================================================
# PATHS & TEMPLATES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ============================================================
# RECOMMENDATION / ANALYTICS ENGINE
# ============================================================


class Brain:
    """Thread-safe Manager for NLP Analyzer and Hybrid Recommender."""

    def __init__(self):
        self.lock = threading.RLock()
        self.an: Analyzer | None = None
        self.rec: Recommender | None = None
        self.last_trained: datetime | None = None
        self.cache = TTLCache(maxsize=1024, ttl=CACHE_TTL)

    def train(self, db: Session):
        with self.lock:
            rows = list(db.scalars(select(Content).order_by(Content.id)))
            if not rows:
                self.an = None
                self.rec = None
                return

            documents = [(r.id, r.title, r.body) for r in rows]
            self.an = Analyzer().fit(documents)

            for i, r in enumerate(rows):
                if len(self.an.doc_topic) > i:
                    r.topic = int(self.an.doc_topic[i])
                r.keywords = ", ".join(self.an.keywords(i, n=5))
                r.sentiment = sentiment(r.title + ". " + r.body)

            db.commit()
            self.last_trained = datetime.now(timezone.utc)
            self.refresh(db)

    def refresh(self, db: Session):
        with self.lock:
            if self.an is None or not self.an.ids:
                return

            # Fetch all interactions
            interactions = db.execute(
                select(
                    Interaction.user_id,
                    Interaction.content_id,
                    Interaction.kind,
                    Interaction.duration_seconds,
                )
            ).all()

            # Fetch all user interests
            interests_rows = db.execute(
                select(UserInterest.user_id, UserInterest.interest)
            ).all()
            user_interests: dict[int, list[str]] = {}
            for uid, interest in interests_rows:
                user_interests.setdefault(uid, []).append(interest)

            # Fetch all user recommendation feedback
            feedback_rows = db.execute(
                select(
                    RecommendationFeedback.user_id,
                    RecommendationFeedback.content_id,
                    RecommendationFeedback.feedback,
                )
            ).all()
            user_feedback: dict[int, dict[int, str]] = {}
            for uid, cid, fb in feedback_rows:
                user_feedback.setdefault(uid, {})[cid] = fb

            self.rec = Recommender(
                analyzer=self.an,
                ids=self.an.ids,
                interactions=interactions,
                user_interests=user_interests,
                user_feedback=user_feedback,
            )
            self.cache.clear()


brain = Brain()


# ============================================================
# APPLICATION LIFESPAN & SEEDING
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema exists
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        content_count = db.scalar(select(func.count(Content.id))) or 0

        # Seed content dataset
        if SEED_ON_START and content_count == 0:
            sample_rows = []
            for item in SAMPLE:
                title, body, category, content_type, author, image_url, source_url = item
                # Realistic base metrics for visual demonstration
                s_score = sentiment(title + ". " + body)
                sample_rows.append(
                    Content(
                        title=title,
                        body=body,
                        category=category,
                        content_type=content_type,
                        author=author,
                        image_url=image_url,
                        source_url=source_url,
                        views=120,
                        likes=24,
                        comments_count=2,
                        shares=8,
                        saves=15,
                        avg_watch_seconds=42.0 if content_type == "video" else 15.0,
                        completion_rate=78.5 if content_type == "video" else 65.0,
                        scroll_depth=85.0 if content_type == "article" else 50.0,
                        sentiment=s_score,
                    )
                )
            db.add_all(sample_rows)
            db.commit()

        # Seed Default Admin Account
        admin = db.scalar(select(User).where(User.email == "admin@intellirec.local"))
        if not admin:
            admin = User(
                name="System Administrator",
                email="admin@intellirec.local",
                password_hash=hash_password("Admin@2026!"),
                role="ADMIN",
            )
            db.add(admin)
            db.flush()
            for int_tag in ["AI", "Machine Learning", "Enterprise Systems", "Cloud"]:
                db.add(UserInterest(user_id=admin.id, interest=int_tag))
            db.commit()

        # Seed Demo User 1: Sarah (Data Science & AI)
        user_sarah = db.scalar(
            select(User).where(User.email == "sarah.data@intellirec.local")
        )
        if not user_sarah:
            user_sarah = User(
                name="Sarah Chen",
                email="sarah.data@intellirec.local",
                password_hash=hash_password("User@2026!"),
                role="USER",
            )
            db.add(user_sarah)
            db.flush()
            for int_tag in ["AI", "Data Science", "Machine Learning", "NLP"]:
                db.add(UserInterest(user_id=user_sarah.id, interest=int_tag))
            db.commit()

        # Seed Demo User 2: Alex (Cloud & Engineering)
        user_alex = db.scalar(
            select(User).where(User.email == "alex.dev@intellirec.local")
        )
        if not user_alex:
            user_alex = User(
                name="Alex Rivera",
                email="alex.dev@intellirec.local",
                password_hash=hash_password("User@2026!"),
                role="USER",
            )
            db.add(user_alex)
            db.flush()
            for int_tag in [
                "Cloud",
                "Cybersecurity",
                "Enterprise Systems",
                "Web Development",
            ]:
                db.add(UserInterest(user_id=user_alex.id, interest=int_tag))
            db.commit()

        # Seed initial comments & interactions if empty
        comments_count = db.scalar(select(func.count(Comment.id))) or 0
        if comments_count == 0:
            first_contents = list(db.scalars(select(Content).limit(8)))
            demo_users = [admin, user_sarah, user_alex]

            for idx, c_item in enumerate(first_contents):
                cmt_text, _ = SAMPLE_COMMENTS[idx % len(SAMPLE_COMMENTS)]
                c_user = demo_users[idx % len(demo_users)]
                s_score = sentiment(cmt_text)
                db.add(
                    Comment(
                        user_id=c_user.id,
                        content_id=c_item.id,
                        text=cmt_text,
                        sentiment=s_score,
                        sentiment_label=label(s_score),
                    )
                )
                # Seed diverse interactions for collaborative signals
                db.add(
                    Interaction(
                        user_id=c_user.id,
                        content_id=c_item.id,
                        kind="view",
                        duration_seconds=45,
                    )
                )
                db.add(
                    Interaction(
                        user_id=c_user.id,
                        content_id=c_item.id,
                        kind="like",
                    )
                )
                if idx % 2 == 0:
                    db.add(
                        Interaction(
                            user_id=c_user.id,
                            content_id=c_item.id,
                            kind="save",
                        )
                    )
            db.commit()

        # Train recommendation & NLP models
        brain.train(db)

    yield


# ============================================================
# FASTAPI APPLICATION SETUP
# ============================================================

app = FastAPI(
    title="IntelliRec — Web Content Intelligence & Recommendation Engine",
    description="Final-Year Integrated ASTMA, Enterprise Systems, and IT Project Management Platform",
    version="2.5.0",
    lifespan=lifespan,
    docs_url=None,       # Disable Swagger UI (/docs)
    redoc_url=None,      # Disable ReDoc (/redoc)
    openapi_url=None,    # Disable OpenAPI schema (/openapi.json)
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AUTHENTICATION & DEPENDENCIES
# ============================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def auth_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    user = None
    if payload:
        subject = payload.get("sub", "")
        if str(subject).isdigit():
            user = db.get(User, int(subject))

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid credentials. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def admin_user(user: User = Depends(auth_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required for this resource.",
        )
    return user


# ============================================================
# SCHEMAS
# ============================================================


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    interests: list[str] = Field(default_factory=list)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str):
        if not password_valid(v):
            raise ValueError(
                "Password must be at least 8 characters long and contain uppercase, lowercase, a number, and a special character."
            )
        return v


class ContentIn(BaseModel):
    title: str = Field(min_length=5, max_length=300)
    body: str = Field(min_length=20)
    category: str = Field(min_length=2, max_length=80)
    content_type: str = Field(default="article")
    author: str = Field(default="IntelliRec Editorial")
    image_url: str | None = None
    source_url: str | None = None


class InteractionIn(BaseModel):
    content_id: int
    kind: str
    duration_seconds: int = Field(default=0, ge=0, le=86400)


class CommentIn(BaseModel):
    content_id: int
    text: str = Field(min_length=2, max_length=3000)


class FeedbackIn(BaseModel):
    content_id: int
    feedback: str


class InterestIn(BaseModel):
    interests: list[str]


class TextAnalyzeIn(BaseModel):
    text: str = Field(min_length=2)


class UserStatusIn(BaseModel):
    is_active: bool


# ============================================================
# RESPONSE FORMATTER
# ============================================================


def cview(
    content: Content,
    score: float | None = None,
    why: dict | None = None,
    is_saved: bool = False,
    is_liked: bool = False,
) -> dict:
    """Format Content model into consistent, rich presentation JSON."""
    views = max(content.views or 0, 0)
    likes = max(content.likes or 0, 0)
    comments = max(content.comments_count or 0, 0)
    shares = max(content.shares or 0, 0)
    saves = max(content.saves or 0, 0)

    engagement_sum = likes + comments + shares + saves
    engagement_rate = (engagement_sum / views * 100) if views > 0 else 0.0

    return {
        "id": content.id,
        "title": content.title,
        "body": content.body,
        "category": content.category,
        "content_type": content.content_type,
        "author": content.author,
        "image_url": content.image_url,
        "source_url": content.source_url,
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": saves,
        "engagement_rate": round(engagement_rate, 2),
        "sentiment": round(content.sentiment or 0.0, 3),
        "sentiment_label": label(content.sentiment or 0.0),
        "topic": content.topic if content.topic is not None else -1,
        "keywords": content.keywords or "",
        "avg_watch_seconds": round(content.avg_watch_seconds or 0.0, 1),
        "completion_rate": round(content.completion_rate or 0.0, 1),
        "scroll_depth": round(content.scroll_depth or 0.0, 1),
        "created_at": (
            content.created_at.isoformat() if content.created_at else None
        ),
        "score": score,
        "why": why,
        "is_saved": is_saved,
        "is_liked": is_liked,
    }


# ============================================================
# HTML WEB ROUTES
# ============================================================


@app.get("/", response_class=HTMLResponse)
def web_home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/app", response_class=HTMLResponse)
def web_app(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.get("/admin", response_class=HTMLResponse)
def web_admin(request: Request):
    # Direct access redirects to app dashboard with admin tab hash
    return RedirectResponse(url="/app#admin")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "IntelliRec Intelligence Engine",
        "version": "2.5.0",
        "model_trained": brain.last_trained.isoformat()
        if brain.last_trained
        else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# AUTHENTICATION API
# ============================================================


@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = str(body.email).lower().strip()
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user = User(
        name=body.name.strip(),
        email=email,
        password_hash=hash_password(body.password),
        role="USER",
    )
    db.add(user)
    db.flush()

    # Add normalized interests
    seen_interests = set()
    for raw_interest in body.interests:
        clean_int = raw_interest.strip()
        if clean_int and clean_int.lower() not in seen_interests:
            seen_interests.add(clean_int.lower())
            db.add(UserInterest(user_id=user.id, interest=clean_int))

    db.commit()
    brain.refresh(db)

    token = create_token(user.id, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "interests": list(seen_interests),
        },
    }


@app.post("/api/v1/auth/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = form.username.lower().strip()
    user = db.scalar(select(User).where(User.email == email))

    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Please contact an administrator.",
        )

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    interests = [
        x.interest
        for x in db.scalars(
            select(UserInterest).where(UserInterest.user_id == user.id)
        )
    ]

    return {
        "access_token": create_token(user.id, user.role),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "interests": interests,
        },
    }


@app.get("/api/v1/auth/me")
def me(user: User = Depends(auth_user), db: Session = Depends(get_db)):
    interests = [
        x.interest
        for x in db.scalars(
            select(UserInterest).where(UserInterest.user_id == user.id)
        )
    ]
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "interests": interests,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ============================================================
# CONTENT DISCOVERY & CATALOG API
# ============================================================


@app.get("/api/v1/content/categories")
def content_categories(db: Session = Depends(get_db)):
    """Return all distinct categories with associated content item counts."""
    rows = db.execute(
        select(Content.category, func.count(Content.id))
        .group_by(Content.category)
        .order_by(desc(func.count(Content.id)))
    ).all()
    return [{"category": r[0], "count": r[1]} for r in rows]


@app.get("/api/v1/content")
def contents(
    category: str | None = None,
    content_type: str | None = None,
    search: str | None = None,
    sort_by: str = Query("newest"),
    limit: int = Query(40, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Content)

    if category and category.lower() != "all":
        query = query.where(Content.category == category)

    if content_type and content_type.lower() != "all":
        query = query.where(Content.content_type == content_type)

    if sort_by == "popular":
        query = query.order_by(desc(Content.views))
    elif sort_by == "engagement":
        query = query.order_by(desc(Content.likes + Content.comments_count))
    elif sort_by == "sentiment":
        query = query.order_by(desc(Content.sentiment))
    else:
        query = query.order_by(desc(Content.created_at))

    rows = list(db.scalars(query.limit(limit)))

    if search:
        st = search.lower().strip()
        rows = [
            r
            for r in rows
            if st
            in (
                f"{r.title} {r.body} {r.category} {r.keywords} {r.author}"
            ).lower()
        ]

    return [cview(r) for r in rows]


@app.get("/api/v1/content/{cid}")
def get_content(
    cid: int,
    db: Session = Depends(get_db),
):
    item = db.get(Content, cid)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content article not found.",
        )
    return cview(item)


@app.get("/api/v1/content/{cid}/similar")
def get_similar_content(cid: int, db: Session = Depends(get_db)):
    """Retrieve top contextual similar content items via TF-IDF cosine similarity."""
    if not brain.rec:
        return []
    similar_items = brain.rec.similar(cid, k=4)
    if not similar_items:
        return []

    ids = [item["id"] for item in similar_items]
    rows = {
        item.id: item
        for item in db.scalars(select(Content).where(Content.id.in_(ids)))
    }

    return [
        cview(rows[item["id"]], score=item["score"], why=item["why"])
        for item in similar_items
        if item["id"] in rows
    ]


@app.post("/api/v1/content", status_code=status.HTTP_201_CREATED)
def add_content(
    body: ContentIn,
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    allowed_types = {"article", "video", "image"}
    if body.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content type must be 'article', 'video', or 'image'.",
        )

    item = Content(
        title=body.title.strip(),
        body=body.body.strip(),
        category=body.category.strip(),
        content_type=body.content_type,
        author=body.author.strip() if body.author else "IntelliRec Editorial",
        image_url=body.image_url,
        source_url=body.source_url,
        views=0,
        likes=0,
        comments_count=0,
        shares=0,
        saves=0,
        sentiment=sentiment(body.title + ". " + body.body),
    )
    db.add(item)
    db.commit()

    # Re-train models to incorporate new content immediately
    brain.train(db)
    return cview(item)


@app.delete("/api/v1/content/{cid}")
def delete_content(
    cid: int,
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    item = db.get(Content, cid)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content item not found.",
        )
    db.delete(item)
    db.commit()
    brain.train(db)
    return {"success": True, "deleted_id": cid}


# ============================================================
# USER PROFILE & INTERESTS
# ============================================================


@app.put("/api/v1/users/interests")
def update_interests(
    body: InterestIn,
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    old_interests = list(
        db.scalars(select(UserInterest).where(UserInterest.user_id == user.id))
    )
    for item in old_interests:
        db.delete(item)

    unique_interests = []
    for x in body.interests:
        clean_tag = x.strip()
        if clean_tag and clean_tag not in unique_interests:
            unique_interests.append(clean_tag)
            db.add(UserInterest(user_id=user.id, interest=clean_tag))

    db.commit()
    brain.refresh(db)
    return {"interests": unique_interests}


@app.get("/api/v1/users/activity")
def get_user_activity(
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    """Fetch genuine user activity timeline of recent interactions."""
    stmt = (
        select(
            Interaction.id,
            Interaction.kind,
            Interaction.duration_seconds,
            Interaction.created_at,
            Content.id.label("content_id"),
            Content.title,
            Content.category,
            Content.content_type,
        )
        .join(Content, Interaction.content_id == Content.id)
        .where(Interaction.user_id == user.id)
        .order_by(desc(Interaction.created_at))
        .limit(30)
    )

    rows = db.execute(stmt).all()
    return [
        {
            "id": r[0],
            "kind": r[1],
            "duration_seconds": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
            "content_id": r[4],
            "title": r[5],
            "category": r[6],
            "content_type": r[7],
        }
        for r in rows
    ]


@app.get("/api/v1/users/saved")
def get_saved_content(
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    """Retrieve all content items bookmarked by the authenticated user."""
    stmt = (
        select(Content)
        .join(
            Interaction,
            (Interaction.content_id == Content.id)
            & (Interaction.user_id == user.id)
            & (Interaction.kind == "save"),
        )
        .order_by(desc(Interaction.created_at))
    )
    rows = list(db.scalars(stmt))
    return [cview(r, is_saved=True) for r in rows]


# ============================================================
# USER INTERACTIONS & ENGAGEMENT API
# ============================================================


@app.post("/api/v1/interactions")
def record_interaction(
    body: InteractionIn,
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    allowed_kinds = {"view", "click", "like", "share", "save"}
    if body.kind not in allowed_kinds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interaction '{body.kind}' is invalid. Allowed: {allowed_kinds}",
        )

    content_item = db.get(Content, body.content_id)
    if not content_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content article not found.",
        )

    # Check for toggle behavior on like / save to prevent duplicates
    if body.kind in {"like", "save"}:
        existing_interaction = db.scalar(
            select(Interaction).where(
                Interaction.user_id == user.id,
                Interaction.content_id == content_item.id,
                Interaction.kind == body.kind,
            )
        )
        if existing_interaction:
            # Toggle off
            db.delete(existing_interaction)
            if body.kind == "like":
                content_item.likes = max(0, content_item.likes - 1)
            elif body.kind == "save":
                content_item.saves = max(0, content_item.saves - 1)
            db.commit()
            brain.refresh(db)
            return {
                "success": True,
                "action": "removed",
                "kind": body.kind,
                "likes": content_item.likes,
                "saves": content_item.saves,
            }

    # Add interaction record
    db.add(
        Interaction(
            user_id=user.id,
            content_id=content_item.id,
            kind=body.kind,
            duration_seconds=body.duration_seconds,
        )
    )

    if body.kind == "view":
        content_item.views = (content_item.views or 0) + 1
        if body.duration_seconds > 0:
            total_sec = (content_item.avg_watch_seconds or 0.0) * max(
                0, content_item.views - 1
            ) + body.duration_seconds
            content_item.avg_watch_seconds = total_sec / content_item.views
    elif body.kind == "like":
        content_item.likes = (content_item.likes or 0) + 1
    elif body.kind == "share":
        content_item.shares = (content_item.shares or 0) + 1
    elif body.kind == "save":
        content_item.saves = (content_item.saves or 0) + 1

    # Log analytics telemetry event
    db.add(
        AnalyticsEvent(
            user_id=user.id,
            content_id=content_item.id,
            event_type=body.kind,
            event_value=str(body.duration_seconds),
            event_metadata={"source": "web_client"},
        )
    )

    db.commit()
    brain.refresh(db)

    return {
        "success": True,
        "action": "added",
        "kind": body.kind,
        "likes": content_item.likes,
        "saves": content_item.saves,
        "views": content_item.views,
        "shares": content_item.shares,
    }


# ============================================================
# COMMENTS API
# ============================================================


@app.get("/api/v1/content/{cid}/comments")
def get_comments(cid: int, db: Session = Depends(get_db)):
    """Retrieve full comment list for content with user display names and sentiment analysis."""
    stmt = (
        select(Comment, User.name)
        .join(User, Comment.user_id == User.id)
        .where(Comment.content_id == cid)
        .order_by(desc(Comment.created_at))
    )
    rows = db.execute(stmt).all()
    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "user_name": uname or "Anonymous",
            "content_id": c.content_id,
            "text": c.text,
            "sentiment": c.sentiment,
            "sentiment_label": c.sentiment_label,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c, uname in rows
    ]


@app.post("/api/v1/comments", status_code=status.HTTP_201_CREATED)
def post_comment(
    body: CommentIn,
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    content_item = db.get(Content, body.content_id)
    if not content_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content article not found.",
        )

    s_detail = sentiment_detail(body.text)
    s_score = s_detail["compound"]
    s_label = s_detail["label"]

    cmt = Comment(
        user_id=user.id,
        content_id=content_item.id,
        text=body.text.strip(),
        sentiment=s_score,
        sentiment_label=s_label,
    )
    content_item.comments_count = (content_item.comments_count or 0) + 1

    # Record as interaction as well
    db.add(cmt)
    db.add(
        Interaction(
            user_id=user.id,
            content_id=content_item.id,
            kind="comment",
            duration_seconds=0,
        )
    )

    db.commit()
    brain.refresh(db)

    return {
        "id": cmt.id,
        "user_name": user.name,
        "text": cmt.text,
        "sentiment": s_score,
        "sentiment_label": s_label,
        "sentiment_detail": s_detail,
        "comments_count": content_item.comments_count,
        "created_at": cmt.created_at.isoformat() if cmt.created_at else None,
    }


# ============================================================
# RECOMMENDATIONS & EXPLAINABILITY API
# ============================================================


@app.get("/api/v1/recommendations")
def recommendations(
    k: int = Query(12, ge=1, le=30),
    category: str | None = None,
    content_type: str | None = None,
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    if not brain.rec:
        return []

    recs = brain.rec.for_user(user.id, k=k * 2)
    ids = [r["id"] for r in recs]

    if not ids:
        return []

    # Batch fetch items
    contents_map = {
        item.id: item
        for item in db.scalars(select(Content).where(Content.id.in_(ids)))
    }

    # Fetch user's saved items to mark active states
    saved_ids = set(
        db.scalars(
            select(Interaction.content_id).where(
                Interaction.user_id == user.id,
                Interaction.kind == "save",
            )
        )
    )
    liked_ids = set(
        db.scalars(
            select(Interaction.content_id).where(
                Interaction.user_id == user.id,
                Interaction.kind == "like",
            )
        )
    )

    out = []
    for r in recs:
        cid = r["id"]
        if cid in contents_map:
            c = contents_map[cid]
            if category and category.lower() != "all" and c.category != category:
                continue
            if (
                content_type
                and content_type.lower() != "all"
                and c.content_type != content_type
            ):
                continue

            out.append(
                cview(
                    c,
                    score=r["score"],
                    why=r["why"],
                    is_saved=cid in saved_ids,
                    is_liked=cid in liked_ids,
                )
            )
            if len(out) >= k:
                break

    return out


@app.get("/api/v1/recommendations/explain/{cid}")
def explain_recommendation(
    cid: int,
    user: User = Depends(auth_user),
):
    """Provide transparent explainability signals and weights for any content item."""
    if not brain.rec:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation engine is initializing.",
        )
    explanation = brain.rec.explain(user.id, cid)
    return explanation


@app.post("/api/v1/recommendations/feedback")
def submit_feedback(
    body: FeedbackIn,
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    allowed_feedback = {"liked", "disliked", "saved", "ignored", "clicked"}
    if body.feedback not in allowed_feedback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid feedback. Allowed: {allowed_feedback}",
        )

    # Upsert feedback
    existing = db.scalar(
        select(RecommendationFeedback).where(
            RecommendationFeedback.user_id == user.id,
            RecommendationFeedback.content_id == body.content_id,
        )
    )
    if existing:
        existing.feedback = body.feedback
    else:
        db.add(
            RecommendationFeedback(
                user_id=user.id,
                content_id=body.content_id,
                feedback=body.feedback,
            )
        )

    db.commit()
    brain.refresh(db)
    return {"success": True, "feedback": body.feedback}


@app.get("/api/v1/trending")
def get_trending_feed(
    k: int = Query(10, ge=1, le=25),
    db: Session = Depends(get_db),
):
    """Return top trending content items and emergent hashtags across the entire platform."""
    if not brain.rec:
        return []

    trend_items = brain.rec.trending(k=k)
    ids = [item["id"] for item in trend_items]
    contents_map = {
        item.id: item
        for item in db.scalars(select(Content).where(Content.id.in_(ids)))
    }

    results = []
    for item in trend_items:
        cid = item["id"]
        if cid in contents_map:
            c = contents_map[cid]
            formatted = cview(c, score=item["score"], why=item["why"])
            formatted["rank"] = item["rank"]
            results.append(formatted)

    return results


# ============================================================
# NLP / ASTMA INTELLIGENCE LAB
# ============================================================


@app.post("/api/v1/analytics/text/analyze")
def analyze_arbitrary_text(
    body: TextAnalyzeIn,
    user: User = Depends(auth_user),
):
    """Live NLP laboratory: extracts sentiment, keywords, and matching topic from any text."""
    text = body.text.strip()
    s_detail = sentiment_detail(text)

    keywords = []
    predicted_topic = 0
    topic_terms = []

    if brain.an:
        keywords = brain.an.terms(text, n=8)
        predicted_topic = brain.an.predict_topic(text)
        if len(brain.an.topic_terms) > predicted_topic:
            topic_terms = brain.an.topic_terms[predicted_topic]

    return {
        "text_length": len(text),
        "sentiment": s_detail,
        "keywords": keywords,
        "predicted_topic": {
            "index": predicted_topic + 1,
            "terms": topic_terms,
        },
    }


# ============================================================
# ADMIN INTELLIGENCE COMMAND CENTER
# ============================================================


@app.get("/api/v1/analytics/overview")
def admin_overview(
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    total_users = db.scalar(select(func.count(User.id))) or 0
    total_content = db.scalar(select(func.count(Content.id))) or 0
    total_views = db.scalar(select(func.sum(Content.views))) or 0
    total_likes = db.scalar(select(func.sum(Content.likes))) or 0
    total_comments = db.scalar(select(func.sum(Content.comments_count))) or 0
    total_shares = db.scalar(select(func.sum(Content.shares))) or 0
    total_saves = db.scalar(select(func.sum(Content.saves))) or 0

    total_engagement = total_likes + total_comments + total_shares + total_saves
    engagement_rate = (
        (total_engagement / total_views * 100) if total_views > 0 else 0.0
    )

    return {
        "users": total_users,
        "content": total_content,
        "views": total_views,
        "likes": total_likes,
        "comments": total_comments,
        "shares": total_shares,
        "saves": total_saves,
        "engagement_rate": round(engagement_rate, 2),
        "last_model_train": brain.last_trained.isoformat()
        if brain.last_trained
        else None,
    }


@app.get("/api/v1/analytics/social")
def admin_social_analytics(
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(
            Content.category,
            func.sum(Content.views),
            func.sum(Content.likes),
            func.sum(Content.comments_count),
            func.sum(Content.shares),
            func.sum(Content.saves),
        )
        .group_by(Content.category)
        .order_by(desc(func.sum(Content.views)))
    ).all()

    return [
        {
            "category": r[0],
            "views": r[1] or 0,
            "likes": r[2] or 0,
            "comments": r[3] or 0,
            "shares": r[4] or 0,
            "saves": r[5] or 0,
        }
        for r in rows
    ]


@app.get("/api/v1/analytics/text")
def admin_text_analytics(
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    by_category = db.execute(
        select(
            Content.category,
            func.avg(Content.sentiment),
            func.count(Content.id),
        ).group_by(Content.category)
    ).all()

    comments_sentiment = db.execute(
        select(
            Comment.sentiment_label,
            func.count(Comment.id),
        ).group_by(Comment.sentiment_label)
    ).all()

    topics = []
    if brain.an and brain.an.topic_terms:
        topics = [
            {
                "topic": idx + 1,
                "keywords": terms,
            }
            for idx, terms in enumerate(brain.an.topic_terms)
        ]

    # Ensure all sentiment labels exist for clean chart rendering
    sent_dict = {r[0]: r[1] for r in comments_sentiment}
    normalized_comments = [
        {"label": "positive", "count": sent_dict.get("positive", 0)},
        {"label": "neutral", "count": sent_dict.get("neutral", 0)},
        {"label": "negative", "count": sent_dict.get("negative", 0)},
    ]

    return {
        "by_category": [
            {
                "category": r[0],
                "avg_sentiment": round(float(r[1] or 0.0), 3),
                "items": r[2],
            }
            for r in by_category
        ],
        "comment_sentiment": normalized_comments,
        "topics": topics,
    }


@app.get("/api/v1/analytics/media")
def admin_media_analytics(
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(
            Content.content_type,
            func.count(Content.id),
            func.sum(Content.views),
            func.avg(Content.avg_watch_seconds),
            func.avg(Content.completion_rate),
            func.avg(Content.scroll_depth),
        ).group_by(Content.content_type)
    ).all()

    return [
        {
            "type": r[0],
            "items": r[1] or 0,
            "views": r[2] or 0,
            "avg_watch_seconds": round(float(r[3] or 0.0), 1),
            "completion_rate": round(float(r[4] or 0.0), 1),
            "scroll_depth": round(float(r[5] or 0.0), 1),
        }
        for r in rows
    ]


@app.get("/api/v1/admin/users")
def admin_list_users(
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    users = list(db.scalars(select(User).order_by(desc(User.created_at))))
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
        }
        for u in users
    ]


@app.patch("/api/v1/admin/users/{uid}/status")
def admin_toggle_user_status(
    uid: int,
    body: UserStatusIn,
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    target = db.get(User, uid)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    if target.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own administrative account.",
        )
    target.is_active = body.is_active
    db.commit()
    return {"success": True, "id": target.id, "is_active": target.is_active}


@app.post("/api/v1/admin/retrain")
def admin_retrain_engine(
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    """Trigger manual retraining of NLP vectorizers, NMF topics, and Recommender signals."""
    brain.train(db)
    return {
        "success": True,
        "message": "Engine retrained and all hybrid signals updated.",
        "trained_at": brain.last_trained.isoformat()
        if brain.last_trained
        else None,
    }