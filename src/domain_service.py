from typing import Any, Dict, List

try:
    from src.domain_store import DomainStore
    from src.domains import GLPIArticle, GLPITicket, GLPIITILCategory, GLPIUser
except ModuleNotFoundError:  # pragma: no cover - execução direta via python src/main.py
    from domain_store import DomainStore
    from domains import GLPIArticle, GLPITicket, GLPIITILCategory, GLPIUser


class DomainService:
    def __init__(self, cache_path: str = "data/glpi_cache.json") -> None:
        self.store = DomainStore(cache_path=cache_path)

    def _normalize_ticket(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        status = payload.get("status")
        category = payload.get("category")
        entity = payload.get("entity")
        user_recipient = payload.get("user_recipient")
        team = payload.get("team") or []

        assignee = None
        requester = None
        for member in team:
            role = (member or {}).get("role")
            if role == "requester":
                requester = member.get("display_name") or member.get("name")
            if role == "assigned":
                assignee = member.get("display_name") or member.get("name")

        return GLPITicket(
            id=payload.get("id"),
            name=payload.get("name"),
            content=payload.get("content"),
            status=status.get("name") if isinstance(status, dict) else status,
            priority=payload.get("priority"),
            urgency=payload.get("urgency"),
            impact=payload.get("impact"),
            category=category.get("name") if isinstance(category, dict) else category,
            entity=entity.get("name") if isinstance(entity, dict) else entity,
            requester=requester or (user_recipient.get("name") if isinstance(user_recipient, dict) else user_recipient),
            assignee=assignee,
            date=payload.get("date"),
            date_creation=payload.get("date_creation"),
            date_mod=payload.get("date_mod"),
            extra={
                "href": payload.get("href"),
                "team": team,
            },
        ).to_dict()

    def _normalize_user(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return GLPIUser(
            id=payload.get("id"),
            username=payload.get("username"),
            realname=payload.get("realname"),
            firstname=payload.get("firstname"),
            email=(payload.get("emails") or [{}])[0].get("email") if isinstance((payload.get("emails") or [{}])[0], dict) else None,
            is_active=bool(payload.get("is_active", True)),
            extra={
                "default_entity": payload.get("default_entity"),
                "location": payload.get("location"),
                "emails": payload.get("emails"),
            },
        ).to_dict()

    def _normalize_article(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return GLPIArticle(
            id=payload.get("id"),
            name=payload.get("name"),
            content=payload.get("content"),
            categories=[category.get("name") if isinstance(category, dict) else str(category) for category in (payload.get("categories") or [])],
            entity=(payload.get("entity") or {}).get("name") if isinstance(payload.get("entity"), dict) else payload.get("entity"),
            is_faq=bool(payload.get("is_faq", False)),
            views=payload.get("views", 0),
            extra={
                "date_creation": payload.get("date_creation"),
                "date_mod": payload.get("date_mod"),
                "href": payload.get("href"),
            },
        ).to_dict()

    def _normalize_category(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return GLPIITILCategory(
            id=payload.get("id"),
            name=payload.get("name"),
            completename=payload.get("completename"),
            entity=(payload.get("entity") or {}).get("name") if isinstance(payload.get("entity"), dict) else payload.get("entity"),
            extra={
                "is_helpdesk_visible": payload.get("is_helpdesk_visible"),
                "code": payload.get("code"),
            },
        ).to_dict()

    def update_from_api_response(self, domain: str, raw_payload: Any) -> None:
        if isinstance(raw_payload, dict) and "data" in raw_payload and raw_payload.get("data") is not None:
            data = raw_payload.get("data")
        else:
            data = raw_payload

        if isinstance(data, list):
            items = []
            if domain == "tickets":
                items = [self._normalize_ticket(item) for item in data]
            elif domain == "users":
                items = [self._normalize_user(item) for item in data]
            elif domain == "articles":
                items = [self._normalize_article(item) for item in data]
            elif domain == "categories":
                items = [self._normalize_category(item) for item in data]
            else:
                items = [item for item in data]
            self.store.replace(domain, items)
        elif isinstance(data, dict):
            if domain == "account":
                self.store.replace("account", [data])
            elif domain == "users":
                self.store.replace("users", [self._normalize_user(data)])
            elif domain == "tickets":
                self.store.replace("tickets", [self._normalize_ticket(data)])
            elif domain == "articles":
                self.store.replace("articles", [self._normalize_article(data)])
            elif domain == "categories":
                self.store.replace("categories", [self._normalize_category(data)])
            else:
                self.store.replace(domain, [data])

    def get(self, domain: str) -> List[Dict[str, Any]]:
        return self.store.data.get(domain, [])

    def load_from_cache(self) -> Dict[str, List[Dict[str, Any]]]:
        self.store.load()
        return self.store.data
