from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

# Enums
class SessionStatus(str, enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"

class FindingSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class FindingType(str, enum.Enum):
    VISUAL = "visual"
    FUNCTIONAL = "functional"
    CONSOLE = "console"
    NETWORK = "network"
    ACCESSIBILITY = "accessibility"
    PERFORMANCE = "performance"
    SECURITY = "security"

# Models
class ExplorationSession(Base):
    __tablename__ = 'exploration_sessions'
    
    id = Column(String, primary_key=True, index=True)
    start_url = Column(String, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.IDLE)
    depth = Column(Integer, default=5)
    max_time = Column(Integer, default=300) # seconds
    browser_type = Column(String, default="chromium")
    
    # Metrics
    states_explored = Column(Integer, default=0)
    bugs_found = Column(Integer, default=0)
    coverage_percentage = Column(Float, default=0.0)
    anomalies_detected = Column(Integer, default=0)
    
    # Timing
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    
    # Configuration
    config = Column(JSON, default={})
    
    # Relationships
    findings = relationship("Finding", back_populates="session", cascade="all, delete-orphan")
    paths = relationship("ExplorationPath", back_populates="session", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "start_url": self.start_url,
            "status": self.status.value if self.status else None,
            "depth": self.depth,
            "max_time": self.max_time,
            "browser_type": self.browser_type,
            "states_explored": self.states_explored,
            "bugs_found": self.bugs_found,
            "coverage_percentage": self.coverage_percentage,
            "anomalies_detected": self.anomalies_detected,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "config": self.config
        }


class Finding(Base):
    __tablename__ = 'findings'
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey('exploration_sessions.id'))
    type = Column(Enum(FindingType), nullable=False)
    severity = Column(Enum(FindingSeverity), default=FindingSeverity.MEDIUM)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    url = Column(String, nullable=False)
    reproduction_steps = Column(JSON, default=[])
    screenshot_path = Column(String, nullable=True)
    console_errors = Column(JSON, default=[])
    network_errors = Column(JSON, default=[])
    metadata_ = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ExplorationSession", back_populates="findings")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "type": self.type.value if self.type else None,
            "severity": self.severity.value if self.severity else None,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "reproduction_steps": self.reproduction_steps,
            "screenshot_path": self.screenshot_path,
            "console_errors": self.console_errors,
            "network_errors": self.network_errors,
            "metadata": self.metadata_,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ExplorationPath(Base):
    __tablename__ = 'exploration_paths'
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey('exploration_sessions.id'))
    step_number = Column(Integer, nullable=False)
    action_type = Column(String, nullable=False) # click, type, navigate, hover, scroll, etc.
    action_details = Column(JSON, default={})
    from_url = Column(String, nullable=False)
    to_url = Column(String, nullable=False)
    element_selector = Column(String, nullable=True)
    element_text = Column(String, nullable=True)
    input_value = Column(String, nullable=True)
    screenshot_before = Column(String, nullable=True)
    screenshot_after = Column(String, nullable=True)
    dom_snapshot = Column(JSON, default={})
    console_messages = Column(JSON, default=[])
    network_requests = Column(JSON, default=[])
    duration_ms = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ExplorationSession", back_populates="paths")
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "step_number": self.step_number,
            "action_type": self.action_type,
            "action_details": self.action_details,
            "from_url": self.from_url,
            "to_url": self.to_url,
            "element_selector": self.element_selector,
            "element_text": self.element_text,
            "input_value": self.input_value,
            "screenshot_before": self.screenshot_before,
            "screenshot_after": self.screenshot_after,
            "dom_snapshot": self.dom_snapshot,
            "console_messages": self.console_messages,
            "network_requests": self.network_requests,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class TestCase(Base):
    __tablename__ = 'test_cases'
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey('exploration_sessions.id'), nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, default=[])
    expected_result = Column(Text, nullable=True)
    actual_result = Column(Text, nullable=True)
    status = Column(String, default="pending") # pending, passed, failed, skipped
    tags = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "status": self.status,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class AppState(Base):
    __tablename__ = 'app_states'
    
    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey('exploration_sessions.id'))
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)
    dom_hash = Column(String, nullable=True)
    screenshot_hash = Column(String, nullable=True)
    state_data = Column(JSON, default={})
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "url": self.url,
            "title": self.title,
            "dom_hash": self.dom_hash,
            "screenshot_hash": self.screenshot_hash,
            "state_data": self.state_data,
            "is_anomaly": self.is_anomaly,
            "anomaly_score": self.anomaly_score,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
