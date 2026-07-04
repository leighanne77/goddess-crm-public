"""users↔contacts link — email-match linking + per-requester intro scoping.

Covers: the `user_id_for_email` helper, auto-linking a new contact to the
team user it *is* on create (REST), and the pathfinder scoping the warm
intro to the requester's own relationships (never routing through/to the
requester, firm-wide fallback when unlinked).
"""

from typing import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Contact, Relationship, User
from app.security import create_access_token
from app.services.intro_pathfinder import find_intro_paths
from app.services.user_link import user_id_for_email


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


def _contact(
    db: Session,
    owner: User,
    name: str,
    *,
    user_id: int | None = None,
    email: str | None = None,
    fly: str = "Must Fly",
    opt: str = "APPROVED",
) -> Contact:
    c = Contact(
        name=name,
        owner_id=owner.id,
        user_id=user_id,
        email=email,
        fly_status=fly,
        opt_in_status=opt,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _edge(db: Session, a: Contact, b: Contact, *, hist: str = "strong") -> None:
    db.add(Relationship(from_contact_id=a.id, to_contact_id=b.id, shared_history=hist))
    db.commit()


# --- user_id_for_email -------------------------------------------------


def test_email_match_is_case_insensitive(
    db: Session, user_factory: Callable[..., User]
) -> None:
    u = user_factory(email="ada@test.fake")
    assert user_id_for_email(db, "  ADA@test.FAKE ") == u.id


def test_email_match_none_when_no_user_or_no_email(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user_factory(email="ada@test.fake")
    assert user_id_for_email(db, "nobody@test.fake") is None
    assert user_id_for_email(db, None) is None
    assert user_id_for_email(db, "not-an-email") is None


# --- auto-link on create (REST) ---------------------------------------


def test_create_contact_links_to_matching_user(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    teammate = user_factory(email="teammate@test.fake")

    resp = client.post(
        "/api/contacts",
        headers=_auth_headers(owner),
        json={"name": "Teammate Card", "email": "Teammate@test.fake"},
    )
    assert resp.status_code == 201
    created = db.get(Contact, resp.json()["id"])
    assert created is not None and created.user_id == teammate.id


def test_create_contact_no_link_when_email_unmatched(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    resp = client.post(
        "/api/contacts",
        headers=_auth_headers(owner),
        json={"name": "Stranger", "email": "stranger@nowhere.fake"},
    )
    assert resp.status_code == 201
    assert db.get(Contact, resp.json()["id"]).user_id is None


# --- pathfinder scoping ------------------------------------------------


def test_paths_scoped_to_requesters_own_relationships(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    mine = _contact(db, me, "Me", user_id=me.id)  # requester's own node
    ada = _contact(db, me, "Ada")  # someone I know
    cyd = _contact(db, me, "Cyd")  # someone I do NOT know
    target = _contact(db, me, "Barrett")
    _edge(db, mine, ada)  # I know Ada
    _edge(db, ada, target)  # Ada knows the target  → my route
    _edge(db, cyd, target)  # firm-wide route I can't personally reach

    result = find_intro_paths(db, me, target.id)

    reach_out = {p.path.intermediaries[0].name for p in result.paths}
    assert reach_out == {"Ada"}  # scoped: Cyd is not someone I know
    # The requester is never a node on any returned path.
    for p in result.paths:
        assert "Me" not in [n.name for n in p.path.intermediaries]


def test_cannot_be_introduced_to_yourself(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    mine = _contact(db, me, "Me", user_id=me.id)
    ada = _contact(db, me, "Ada")
    _edge(db, ada, mine)  # someone knows me

    result = find_intro_paths(db, me, mine.id)
    assert result.target is not None  # found (it's my own card)
    assert result.paths == []  # but there's no "intro to yourself"


def test_unlinked_requester_falls_back_to_firm_wide(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()  # NOT linked to any contact
    ada = _contact(db, me, "Ada")
    cyd = _contact(db, me, "Cyd")
    target = _contact(db, me, "Barrett")
    _edge(db, ada, target)
    _edge(db, cyd, target)

    result = find_intro_paths(db, me, target.id)
    reach_out = {p.path.intermediaries[0].name for p in result.paths}
    assert reach_out == {"Ada", "Cyd"}  # firm-wide: both routes surface
