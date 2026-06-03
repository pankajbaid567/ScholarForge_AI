from datetime import datetime
import enum
import uuid
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Enum, JSON, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class DocumentStatus(enum.Enum):
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"

class MessageRole(enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    content_hash = Column(String, unique=True, nullable=False)
    status = Column(Enum(DocumentStatus), nullable=False, default=DocumentStatus.PENDING)
    metadata_ = Column("metadata", JSONB, default={})  # Renamed attribute to metadata_
    created_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(String, nullable=False)
    token_count = Column(Integer, nullable=False)
    metadata_ = Column("metadata", JSONB, default={})

    document = relationship("Document", back_populates="chunks")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), index=True, nullable=True) # Optional for MVP
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    history = relationship("ConversationHistory", back_populates="session", cascade="all, delete-orphan", order_by="ConversationHistory.created_at")

class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(String, nullable=False)
    context_used = Column(JSONB, default=[]) # List of chunk UUIDs
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="history")
    evaluation = relationship("Evaluation", back_populates="message", uselist=False)

class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("conversation_history.id", ondelete="CASCADE"), nullable=False, unique=True)
    faithfulness = Column(Float, nullable=True)
    answer_rel = Column(Float, nullable=True)
    context_rec = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("ConversationHistory", back_populates="evaluation")

class HumanFeedback(Base):
    __tablename__ = "human_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("conversation_history.id", ondelete="CASCADE"), nullable=False, unique=True)
    vote = Column(Integer, nullable=False) # 1 for upvote, -1 for downvote
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
