from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BaseDomain:
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GLPIUser(BaseDomain):
    id: Optional[int] = None
    username: Optional[str] = None
    realname: Optional[str] = None
    firstname: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GLPITicket(BaseDomain):
    id: Optional[int] = None
    name: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    urgency: Optional[str] = None
    impact: Optional[str] = None
    category: Optional[str] = None
    entity: Optional[str] = None
    requester: Optional[str] = None
    assignee: Optional[str] = None
    date: Optional[str] = None
    date_creation: Optional[str] = None
    date_mod: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GLPIArticle(BaseDomain):
    id: Optional[int] = None
    name: Optional[str] = None
    content: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    entity: Optional[str] = None
    is_faq: bool = False
    views: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GLPIITILCategory(BaseDomain):
    id: Optional[int] = None
    name: Optional[str] = None
    completename: Optional[str] = None
    entity: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GLPIAccount(BaseDomain):
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
