# Software Architectural Patterns

> Where things _live_. The shape of the codebase, not the algorithms inside it.

This document is about codebase-level architecture: layered, hexagonal, onion,
clean, modular monolith, microservices, in-process event-driven, plugin, and the
MVC family. It answers questions like _where does HTTP parsing belong?_, _where
does a DB query belong?_, _where does a business rule belong?_, _when is a new
service warranted versus a module inside the monolith?_

Architectural mistakes are expensive to undo — you pay for them across every
feature, forever, until someone carves out time to fix the shape. Choose the
smallest shape that satisfies the real constraints, and **enforce the dependency
rule with a linter**, because without enforcement the rule erodes in months.

The opinions here are stronger than in most pattern catalogs. They are codified
as `import-linter` / `grimp` contracts at the bottom of each section, and as
`tests/test_imports.py` style boundary checks you can drop into any project.

## How to use this file

- **Reading order.** Top-to-bottom is the right order: every pattern below
  builds on the Dependency Rule. Pick a target architecture _before_ you start
  writing code; retrofitting is an order of magnitude harder than starting
  clean.
- **Per-pattern shape.** Each entry has _Intent · How it manifests · Sketch ·
  Type-safety notes · When NOT to use · Real-world examples · References_.
- **Citations are real.** Page numbers refer to the editions listed in the
  [References](#references) section.
- **Strict typing throughout.** Every Python sketch is written to target mypy
  `--strict` and pyright `--strict`: `Protocol` over `ABC`, PEP 604 unions, PEP
  695 generics, `Self`, `Final`, `@override`, no `Any`, and the annotation
  evaluation policy assumed by this catalogue; see `SKILL.md` conventions.

## the-dependency-rule

**What it is / Intent.** Every architectural pattern in this document is a
specific answer to one question: _which way do dependencies point?_ The
Dependency Rule says: source-code dependencies must point _only_ toward more
stable abstractions — and the most stable thing in any business application is
the domain. (Martin, _Clean Architecture_, 2017, ch. 22, "The Clean
Architecture.")

**When to reach for it / How it manifests.**

- Domain types and rules do not import from HTTP handlers, DB adapters, or
  external clients.
- Application services do not import from HTTP handlers.
- Adapters depend on domain types, not the reverse.
- Imports must be statically checkable, not "we agree by convention."

**Sketch.** A toy three-package layout illustrating the rule, with a CI test
that fails on violation.

```python
# src/myproject/domain/user.py
from dataclasses import dataclass
from typing import NewType, Self

UserId = NewType("UserId", str)

@dataclass(frozen=True, slots=True)
class User:
    id: UserId
    email: str

    @classmethod
    def new(cls, user_id: UserId, email: str) -> Self:
        if "@" not in email:
            raise ValueError(f"invalid email: {email!r}")
        return cls(id=user_id, email=email)
```

```python
# src/myproject/application/register_user.py
from dataclasses import dataclass
from typing import Protocol

from myproject.domain.user import User, UserId

class UserRepository(Protocol):
    def save(self, user: User) -> None: ...

@dataclass(frozen=True, slots=True)
class RegisterUser:
    repo: UserRepository

    def __call__(self, user_id: UserId, email: str) -> User:
        user = User.new(user_id, email)
        self.repo.save(user)
        return user
```

```python
# src/myproject/infrastructure/postgres_user_repo.py
from typing import override
from myproject.domain.user import User
from myproject.application.register_user import UserRepository

class PostgresUserRepository:
    @override
    def save(self, user: User) -> None: ...
```

```python
# tests/test_imports.py
import grimp

def test_domain_does_not_import_infrastructure() -> None:
    graph = grimp.build_graph("myproject")
    assert not graph.find_descendants("myproject.domain") & graph.find_descendants(
        "myproject.infrastructure"
    )
    forbidden = graph.find_shortest_chain(
        importer="myproject.domain", imported="myproject.infrastructure"
    )
    assert forbidden is None, f"domain imports infrastructure via: {forbidden}"
```

**Type-safety / static-analysis notes.** `import-linter` and `grimp` enforce the
rule at CI time. mypy and pyright ensure `UserRepository` is structurally
satisfied by `PostgresUserRepository`. `@override` (PEP 698) catches typos in
implementing methods. The domain has no third-party imports, so it is testable
without any infrastructure spin-up.

**When NOT to use.** Never. The Dependency Rule is unconditional in any
non-trivial codebase. The only valid escape is "this script is two files; there
are no layers." If there are layers at all, the rule applies.

**Real-world examples.** GitLab Rails monolith uses Packwerk to enforce package
boundaries; Stripe's API library structures domain/transport separation;
Instagram's Django backend uses internal layering rules vetted by static
analyzers.

**References.** Martin, _Clean Architecture_, 2017, ch. 14 ("Component
Coupling"), ch. 22 ("The Clean Architecture"). Cockburn, "Hexagonal
architecture," 2005. `import-linter`: <https://import-linter.readthedocs.io>.

---

## layered-n-tier

**What it is / Intent.** Code is split into stacked horizontal layers, each
depending only on the layer below: Presentation → Application → Domain →
Infrastructure. The classic "three-tier" or "N-tier" web app. Originated in
client-server enterprise systems (Buschmann et al., _POSA Vol. 1_, 1996, ch. 2).

**When to reach for it / How it manifests.**

- A small CRUD service where the domain is thin and unlikely to grow.
- The team is new to architectural patterns and wants the simplest
  organizational rule.
- Most of the work is moving rows between a database and an HTTP shape.
- Anti-signal: if you find yourself importing SQLAlchemy inside `domain/`,
  layered is too weak — switch to hexagonal.

**Sketch.** Directory layout, then strict-typed code per layer.

```text
src/myproject/
├── presentation/
│   ├── http/
│   │   ├── routes.py           # FastAPI/Flask routes — input/output
│   │   └── schemas.py          # Pydantic request/response DTOs
│   └── cli/
│       └── commands.py
├── application/
│   └── users/
│       ├── register.py         # one file per use case
│       └── deactivate.py
├── domain/
│   └── users/
│       ├── user.py             # entity
│       ├── email.py            # value object
│       └── errors.py           # domain exceptions
└── infrastructure/
    ├── db/
    │   └── user_repository.py  # SQLAlchemy implementation
    └── email/
        └── ses_client.py
```

```python
# domain/users/email.py
from dataclasses import dataclass
from typing import Self

@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if "@" not in self.value:
            raise ValueError(f"invalid email: {self.value!r}")

    @classmethod
    def parse(cls, raw: str) -> Self:
        return cls(value=raw.strip().lower())
```

```python
# application/users/register.py
from dataclasses import dataclass
from typing import Protocol
from myproject.domain.users.user import User
from myproject.domain.users.email import Email

class UserRepository(Protocol):
    def find_by_email(self, email: Email) -> User | None: ...
    def save(self, user: User) -> None: ...

@dataclass(frozen=True, slots=True)
class RegisterUser:
    repo: UserRepository

    def __call__(self, email: Email) -> User:
        if self.repo.find_by_email(email) is not None:
            raise UserAlreadyExists(email)
        user = User.new(email)
        self.repo.save(user)
        return user

class UserAlreadyExists(Exception):
    def __init__(self, email: Email) -> None:
        super().__init__(f"user already exists: {email.value}")
```

**The naive pitfall.** Strict layering tells you that infrastructure sits
_below_ domain. That makes it easy to "just reuse the SQLAlchemy model" inside
`domain/`. Once that happens, the dependency rule is inverted: domain knows
about SQLAlchemy. Now domain cannot be tested without a database, and swapping
persistence is a rewrite. This is precisely the trap hexagonal architecture is
designed to prevent.

**Type-safety / static-analysis notes.** Encode the layers as `import-linter`
contracts (see [enforcement-import-contracts](#enforcement-import-contracts)).
pyright/mypy will already catch wrong types crossing layers, but they won't
catch _wrong-direction imports_ — that requires `import-linter` or `grimp`
traversal in CI.

**When NOT to use.** A non-trivial domain (state machines, business invariants
spanning entities, multiple persistence backends). Layered architecture has no
formal answer to "how do we keep `domain/` from importing `infrastructure/`?" —
its naive form actively encourages that mistake. Switch to hexagonal at the
first sign of domain logic that feels infrastructure-aware.

**Real-world examples.** Most pre-2010 Java EE / Spring monoliths. Standard
Django app (presentation: views, application: services, domain: models,
infrastructure: ORM — although Django's ORM-as-domain blurs the lines). Rails
default scaffold (controllers → services → models → ActiveRecord).

**References.** Buschmann et al., _Pattern-Oriented Software Architecture, Vol.
1_, Wiley, 1996, ch. 2 ("Layers"). Fowler, _Patterns of Enterprise Application
Architecture_, Addison-Wesley, 2002, ch. 1 ("Layering").

---

## hexagonal-ports-and-adapters

**What it is / Intent.** Place the _domain_ at the center; everything else lives
at the edge. The domain defines **ports** — Protocols describing what it needs
from or offers to the outside world. Concrete **adapters** implement those ports
for specific technologies: Postgres, SES, FastAPI, gRPC. The domain never
imports a concrete adapter; adapters import the domain's ports. (Cockburn,
"Hexagonal architecture," 2005.)

The hexagon shape is not magic; Cockburn drew six sides because that left room
to draw ports on each face — not because six is special. (Cockburn, _Hexagonal
Architecture Explained_, 2024.)

**Primary (driving) vs Secondary (driven) adapters.** Cockburn's two-side
terminology:

- **Primary / Driving adapters** are on the _left_: they invoke the application.
  HTTP controllers, CLI commands, gRPC handlers, message-queue consumers. They
  drive the use cases.
- **Secondary / Driven adapters** are on the _right_: the application invokes
  them. Database repositories, email senders, third-party API clients. They are
  driven by the application.

**When to reach for it / How it manifests.**

- Non-trivial domain logic with invariants worth protecting.
- Realistic likelihood of swapping adapters (Postgres → another store, SES →
  Postmark, REST → gRPC).
- More than one entrypoint expected (HTTP + CLI + worker).
- Tests must run without spinning up a DB or a broker.
- Anti-signal: a 500-line script. Don't pay for isolation you won't exploit.

**Sketch.**

```text
src/myproject/
├── domain/
│   └── users/
│       ├── user.py            # entity
│       ├── email.py           # value object
│       └── ports.py           # UserRepository, EmailSender Protocols
├── application/
│   └── users/
│       └── register.py        # uses ports only — no concrete adapters
└── adapters/
    ├── inbound/               # primary / driving
    │   ├── http/
    │   │   └── routes.py
    │   └── cli/
    │       └── commands.py
    └── outbound/              # secondary / driven
        ├── postgres/
        │   └── user_repository.py
        └── ses/
            └── email_sender.py
```

```python
# domain/users/ports.py
from typing import Protocol
from myproject.domain.users.user import User
from myproject.domain.users.email import Email

class UserRepository(Protocol):
    """Driven port: persistence."""
    def find_by_email(self, email: Email) -> User | None: ...
    def save(self, user: User) -> None: ...

class EmailSender(Protocol):
    """Driven port: outbound notification."""
    def send_welcome(self, user: User) -> None: ...
```

```python
# application/users/register.py
from dataclasses import dataclass
from myproject.domain.users.user import User
from myproject.domain.users.email import Email
from myproject.domain.users.ports import EmailSender, UserRepository

@dataclass(frozen=True, slots=True)
class RegisterUser:
    """Inbound port (use case): the API the driving adapters call."""
    repo: UserRepository
    sender: EmailSender

    def __call__(self, email: Email) -> User:
        if self.repo.find_by_email(email) is not None:
            raise UserAlreadyExists(email)
        user = User.new(email)
        self.repo.save(user)
        self.sender.send_welcome(user)
        return user

class UserAlreadyExists(Exception): ...
```

```python
# adapters/outbound/postgres/user_repository.py
from typing import override
from sqlalchemy.orm import Session
from myproject.domain.users.email import Email
from myproject.domain.users.ports import UserRepository
from myproject.domain.users.user import User

class PostgresUserRepository:  # structurally satisfies UserRepository
    def __init__(self, session: Session) -> None:
        self._session: Session = session

    @override
    def find_by_email(self, email: Email) -> User | None:
        row = self._session.execute(...).first()
        return None if row is None else User.from_row(row)

    @override
    def save(self, user: User) -> None:
        self._session.merge(user.to_row())
```

```python
# adapters/inbound/http/routes.py
from fastapi import APIRouter
from myproject.application.users.register import RegisterUser, UserAlreadyExists
from myproject.domain.users.email import Email

router = APIRouter()

def make_routes(register: RegisterUser) -> APIRouter:
    @router.post("/users")
    def create(payload: dict[str, str]) -> dict[str, str]:
        try:
            user = register(Email.parse(payload["email"]))
        except UserAlreadyExists:
            return {"error": "already_exists"}
        return {"id": user.id}
    return router
```

**Composition root.** The wiring happens at the entrypoint — `main.py` or a
FastAPI app factory — which constructs concrete adapters and passes them into
use cases. Inner layers never call a DI container.

```python
# main.py
from sqlalchemy.orm import Session
from myproject.adapters.outbound.postgres.user_repository import PostgresUserRepository
from myproject.adapters.outbound.ses.email_sender import SesEmailSender
from myproject.adapters.inbound.http.routes import make_routes
from myproject.application.users.register import RegisterUser

def build_app(session: Session) -> object:
    repo = PostgresUserRepository(session)
    sender = SesEmailSender(region="us-east-1")
    register = RegisterUser(repo=repo, sender=sender)
    return make_routes(register)
```

**`tests/test_imports.py` boundary check.**

```python
import grimp

def test_domain_imports_only_stdlib_and_self() -> None:
    graph = grimp.build_graph("myproject")
    domain_imports = graph.find_modules_directly_imported_by("myproject.domain.users.ports")
    forbidden = {"sqlalchemy", "fastapi", "boto3", "httpx"}
    assert not any(m.split(".")[0] in forbidden for m in domain_imports)

def test_application_does_not_import_adapters() -> None:
    graph = grimp.build_graph("myproject")
    chain = graph.find_shortest_chain(
        importer="myproject.application", imported="myproject.adapters"
    )
    assert chain is None, f"application imports adapters: {chain}"
```

**Type-safety / static-analysis notes.** `Protocol` provides structural typing —
adapters do not need to inherit from the port. mypy/pyright check that adapters
provide every method with compatible types. `@override` (PEP 698) catches drift
between port and adapter. The composition root is the single place where
concrete types appear together; it is the only file allowed to import from both
`application/` and `adapters/`.

**When NOT to use.** A 500-line script. A proof-of-concept. A service that does
nothing but translate one API into another (fewer than ~3 use cases, no business
rules). When "swapping the adapter" will never happen, the indirection is
overhead.

**Real-world examples.** Netflix's microservices use ports/adapters internally
per service. Stripe's payment-processing core uses domain-centric ports for
pluggable acquirers. Many Domain-Driven Design systems (Vaughn Vernon's
_Implementing Domain-Driven Design_ uses hexagonal as the default).

**References.** Cockburn, "Hexagonal architecture," 2005,
<https://alistair.cockburn.us/hexagonal-architecture>. Cockburn, _Hexagonal
Architecture Explained_, self-published, 2024. Vernon, _Implementing
Domain-Driven Design_, Addison-Wesley, 2013, ch. 4 ("Architecture").

---

## onion-architecture

**What it is / Intent.** Jeffrey Palermo's 2008 formulation: concentric rings
from domain _model_ (innermost) outward through _domain services_, _application
services_, and _infrastructure_ (outermost). Source-code dependencies point only
inward; outer rings know about inner rings, never the reverse. (Palermo, "The
Onion Architecture: Part 1," 2008.)

**Onion vs Hexagonal.** Onion is hexagonal with an extra ring: it explicitly
separates _domain model_ from _domain services_ (cross-entity behavior). In
Python, that distinction is usually a rename: domain services live in
`domain/services/` rather than on the entities themselves.

**When to reach for it / How it manifests.**

- The domain has cross-entity operations that don't belong on a single entity
  (e.g. `TransferMoney(from_account, to_account, amount)`).
- The team wants explicit naming for "service" without dragging in anemic-domain
  bait.

**Sketch.**

```text
src/myproject/
├── domain/
│   ├── model/                  # innermost: entities, value objects
│   │   ├── account.py
│   │   └── money.py
│   └── services/               # cross-entity domain logic
│       └── transfer.py
├── application/                # use cases — orchestrate domain services
│   └── transfer_funds.py
└── infrastructure/             # outermost: DB, HTTP, queues
    └── postgres/
        └── account_repository.py
```

```python
# domain/services/transfer.py
from myproject.domain.model.account import Account
from myproject.domain.model.money import Money

def transfer(source: Account, target: Account, amount: Money) -> None:
    """Cross-entity invariant: both accounts touched in one operation.

    A method on Account alone cannot enforce this — it would either need
    a reference to target (creating a graph) or split the operation across
    two calls (allowing partial failure).
    """
    source.debit(amount)
    target.credit(amount)
```

**Type-safety / static-analysis notes.** Same as hexagonal: `Protocol` ports,
structural typing, import-contract enforcement. Pyright is strict about not
letting domain services import application or infrastructure (caught by
`import-linter`).

**When NOT to use.** Hexagonal already covers the same ground for most Python
projects. Pick onion only if the team uses the terminology — the architectural
benefits are identical.

**Real-world examples.** Many .NET DDD codebases (where the term originates).
Some Java Spring DDD implementations. In Python, indistinguishable from
hexagonal in practice.

**References.** Palermo, "The Onion Architecture: Part 1," 2008,
<https://jeffreypalermo.com/2008/07/the-onion-architecture-part-1/>. Vernon,
_Implementing Domain-Driven Design_, 2013, ch. 4.

---

## clean-architecture

**What it is / Intent.** Robert C. Martin's synthesis (2017): four concentric
rings — _Entities_ (Enterprise Business Rules), _Use Cases_ (Application
Business Rules), _Interface Adapters_, _Frameworks & Drivers_. The Dependency
Rule is unconditional: source-code dependencies cross ring boundaries only
inward. (Martin, _Clean Architecture_, 2017, ch. 22.)

```text
┌───────────────────────────────────────────────┐
│  Frameworks & Drivers (HTTP, DB, UI)          │
│  ┌─────────────────────────────────────────┐  │
│  │  Interface Adapters (controllers,       │  │
│  │   presenters, gateways/repositories)    │  │
│  │  ┌───────────────────────────────────┐  │  │
│  │  │  Use Cases (application services) │  │  │
│  │  │  ┌─────────────────────────────┐  │  │  │
│  │  │  │  Entities (domain model)    │  │  │  │
│  │  │  └─────────────────────────────┘  │  │  │
│  │  └───────────────────────────────────┘  │  │
│  └─────────────────────────────────────────┘  │
└───────────────────────────────────────────────┘
```

**Hexagonal vs Onion vs Clean.**

| Aspect               | Hexagonal                | Onion               | Clean                          |
| -------------------- | ------------------------ | ------------------- | ------------------------------ |
| Origin               | Cockburn 2005            | Palermo 2008        | Martin 2017                    |
| Inner-ring count     | 1 (domain)               | 2 (model, services) | 2 (entities, use cases)        |
| Outermost ring named | "adapters"               | "infrastructure"    | "frameworks & drivers"         |
| Boundary protocol    | port (Protocol)          | interface           | boundary interface (DIP)       |
| Diagrammatic shape   | hexagon (room for ports) | concentric rings    | concentric rings + 4 quadrants |

In Python, all three collapse to: _domain at center, Protocols on the boundary,
adapters at the edge_. Pick hexagonal terminology unless an existing codebase
uses one of the others.

**When to reach for it / How it manifests.**

- A team coming from .NET / DDD that already uses Clean terminology.
- A codebase Martin's _Clean Architecture_ book has been adopted as house style.

**Sketch.** Identical layout to hexagonal, with renamed directories:
`entities/`, `use_cases/`, `interface_adapters/`, `frameworks_and_drivers/`. The
code shape is the same.

**Type-safety / static-analysis notes.** Same as hexagonal. The Dependency Rule
is a straight `import-linter` `layers` contract.

**When NOT to use.** When you don't already use Clean terminology. The book is
worth reading; the renaming is not worth the team-wide rename.

**Real-world examples.** Uncle Bob's reference implementations (Ruby, Java,
.NET). The _Architecture Patterns with Python_ book (Percival & Gregory, 2020)
uses hexagonal but acknowledges the equivalence with Clean.

**References.** Martin, _Clean Architecture_, Pearson, 2017, ch. 22 ("The Clean
Architecture") — definitive. Percival & Gregory, _Architecture Patterns with
Python_, O'Reilly, 2020 — the Python-flavored treatment.

---

## modular-monolith

**What it is / Intent.** A single deployable unit, internally partitioned into
independent modules with explicit, enforced boundaries. Each module has its own
domain, application, and adapters; modules communicate only through published
interfaces or in-process events. The shape gives most of microservices'
organizational benefits without the operational cost. (Tudose, _Modular Monolith
with DDD_, 2021; Kapferer, _Service-Oriented Modular Monoliths_.)

**When to reach for it / How it manifests.**

- Team size 1–30 engineers; operational appetite for many services is low.
- Bounded contexts not yet stable — module boundaries are cheaper to move than
  service boundaries.
- You want the option to extract a service later without rewriting.
- Anti-signal: pretending a tangled monolith is "modular" when imports go in
  every direction. Modular = enforced boundaries.

**Sketch.**

```text
src/myproject/
├── modules/
│   ├── billing/
│   │   ├── public/                 # exported types and ports
│   │   │   └── __init__.py
│   │   ├── domain/
│   │   ├── application/
│   │   └── adapters/
│   ├── catalog/
│   │   ├── public/
│   │   └── ...
│   └── notifications/
│       ├── public/
│       └── ...
├── shared_kernel/                   # types shared by definition (Money, UserId)
└── platform/                        # cross-cutting: logging, config, telemetry
```

```python
# modules/billing/public/__init__.py
"""The public face of the billing module.

Other modules MUST import only from here. Internal types are private.
"""
from myproject.modules.billing.domain.events import InvoiceIssued
from myproject.modules.billing.domain.value_objects import InvoiceId
from myproject.modules.billing.application.charge import ChargeCustomer

__all__ = ["ChargeCustomer", "InvoiceId", "InvoiceIssued"]
```

```python
# modules/orders/application/place_order.py
from myproject.modules.billing.public import ChargeCustomer
# NOT: from myproject.modules.billing.domain.account import Account  # forbidden
```

**`tests/test_imports.py` boundary check.**

```python
import grimp

MODULES = ("billing", "catalog", "notifications", "orders")

def test_modules_only_use_public_of_others() -> None:
    graph = grimp.build_graph("myproject")
    for src in MODULES:
        for dst in MODULES:
            if src == dst:
                continue
            forbidden_internal_chain = graph.find_shortest_chain(
                importer=f"myproject.modules.{src}",
                imported=f"myproject.modules.{dst}.domain",
            )
            assert forbidden_internal_chain is None, (
                f"{src} reaches into {dst}.domain: {forbidden_internal_chain}"
            )
```

**Inter-module communication.**

- **Synchronous calls.** Module A imports module B's published service interface
  from `public/` and calls it directly. Cheap, but couples release cycles.
- **Domain events.** Module A emits `OrderPlaced`; module B subscribes via an
  in-process bus. Looser coupling, eventual consistency. Requires the outbox
  pattern if you may ever split. See
  [event-driven-in-process](#event-driven-in-process).

**Type-safety / static-analysis notes.** `import-linter` `forbidden` contracts
(see [enforcement-import-contracts](#enforcement-import-contracts)) enforce that
`modules/{x}/` cannot import from `modules/{y}/domain` or
`modules/{y}/adapters`. The `__all__` in each `public/__init__.py` makes the
public surface explicit; ruff (`F401`/`F403`) flags re-exports without
`__all__`.

**When NOT to use.**

- A single bounded context that fits in one module: just be a normal hexagonal
  app.
- Already at microservices and the boundaries are right: don't reverse a working
  decomposition.
- A two-engineer prototype: extracting modules will outpace product velocity.

**Real-world examples.** Shopify (Rails monolith with Packwerk-enforced
packages, 2014– present). GitHub Actions runner (originally a single .NET app
with strict internal modules). Many DDD-heavy systems described in Vernon and
Khononov.

**References.** Kapferer, _Service-Oriented Modular Monoliths_. Khononov,
_Learning Domain-Driven Design_, O'Reilly, 2021, ch. 14 ("Microservices") —
explains when the monolith is the right answer. Newman, _Building
Microservices_, 2nd ed., O'Reilly, 2021, ch. 1 ("What Are Microservices?") —
argues for the monolith default.

---

## microservices

**What it is / Intent.** Multiple independently deployable services, each owning
its data, communicating over network protocols (HTTP/gRPC for sync,
queues/streams for async). (Newman, _Building Microservices_, 2nd ed., 2021, ch.
1.)

> "I see microservices as **independently deployable services modeled around a
> business domain**. They communicate with each other via networks, and as an
> architecture choice offer many options for solving the problems you may face."
> — Newman, ch. 1.

**The qualification test.** Newman's reluctance is the right starting attitude:
choose microservices only when the _monolith pain ≥ distributed-systems pain_.
Before splitting a service out, every service should answer "yes" to **at least
three of**:

1. Does it have an independent reason to deploy (different team, cadence,
   release risk)?
2. Does it have an independent scaling profile?
3. Does it own data no other service writes to?
4. Can its API survive backwards-compatible evolution?

If fewer than three answers are yes, keep it as a module in the monolith.

**Service boundaries should match bounded contexts** (DDD's term for "a coherent
slice of business semantics"), not database tables or team org-charts. A service
that wraps a single table is a remote dispatcher; a service that owns a
consistent slice of business semantics is a real boundary.

**When to reach for it / How it manifests.**

- A specific module needs independent deployment cadence, independent scale, a
  different runtime, or a hard security boundary.
- Anti-signal: "we want microservices because they're modern" — the operational
  tax is real and quantified in lower velocity for ~6–18 months.

**Sketch.** Per-service hexagonal layout, plus a shared schemas package consumed
via versioned releases (not via shared imports).

```text
services/
├── orders/
│   ├── src/orders/
│   │   ├── domain/
│   │   ├── application/
│   │   └── adapters/
│   │       ├── inbound/http/
│   │       └── outbound/postgres/
│   ├── pyproject.toml          # owns its deps
│   └── Dockerfile              # owns its runtime
├── billing/
│   └── ...
└── shared/
    ├── orders-events/          # PUBLISHED package: event schemas only
    │   └── src/orders_events/
    │       └── v1.py
    └── billing-events/
```

```python
# services/orders/src/orders/adapters/outbound/billing/client.py
from typing import Protocol
from orders.domain.order import Order
from billing_events.v1 import ChargeRequested  # consumed via package, not import-from-source

class BillingClient(Protocol):
    """Outbound port: how orders talks to billing.

    Implementation may be HTTP, gRPC, or a queue producer — the port doesn't care.
    """
    def request_charge(self, order: Order) -> None: ...

class HttpBillingClient:
    def __init__(self, base_url: str, timeout_s: float = 5.0) -> None:
        self._base_url: str = base_url
        self._timeout_s: float = timeout_s

    def request_charge(self, order: Order) -> None:
        # Real impl: httpx.post with retries, timeouts, circuit breaker.
        ...
```

**Data ownership.** Each service owns its data. No cross-service DB reads —
other services call the owner's API. Sharing a database across services is a
_distributed monolith_ in disguise; see `anti-patterns.md` (Distributed
Monolith).

**Type-safety / static-analysis notes.** Type-check across service boundaries by
publishing the event/DTO schemas as a versioned package
(`orders-events==1.4.0`). Consumers pin a major version; breaking changes ship a
`v2` namespace. Cross-service calls cannot be type-checked at the network seam —
the seam is a deserialization boundary. Use `pydantic` or `dataclasses-json` to
validate at the boundary; treat the inputs as untrusted.

**When NOT to use.** Anything that fails Newman's qualification test. A
two-engineer team. A product where a single user request fans out to ten
services (you bought network latency for nothing). A team without observability,
CI/CD per service, schema-evolution discipline, and on-call rotations.

**Real-world examples.** Netflix (genuine — independent scale, on-call
boundaries, hundreds of services). Amazon retail (post-2002 mandate). Plenty of
_cautionary tales_ where teams adopted microservices and reverted to a modular
monolith (Segment, Istio→Ambient, GitHub's "primitives" rewrite).

**References.** Newman, _Building Microservices_, 2nd ed., O'Reilly, 2021, ch.
1, ch. 5 ("Implementing Microservice Communication"), ch. 14 ("User
Interfaces"). Khononov, _Learning Domain-Driven Design_, 2021, ch. 14. Fowler,
"Microservice Premium," 2015,
<https://martinfowler.com/bliki/MicroservicePremium.html>.

---

## event-driven-in-process

**What it is / Intent.** Domain events as the integration surface between
modules in a single process. A producer module emits an event ("OrderPlaced");
zero or more consumer modules subscribe and react. The producer doesn't know
who's listening. (Khononov, _Learning Domain-Driven Design_, 2021, ch. 9;
Vernon, _IDDD_, 2013, ch. 8.)

This document covers the **in-process** flavor only. Cross-service pub/sub
belongs in `system/communication.md`.

**When to reach for it / How it manifests.**

- Multiple modules react to the same state change (`OrderPlaced` triggers
  billing, inventory, notifications).
- Modules should not know each other's interfaces.
- Anti-signal: using an "event" with a single known subscriber that the producer
  always expects to handle. That's a _command_, not an event — call it directly.

**Sketch.**

```python
# modules/orders/domain/events.py
from dataclasses import dataclass
from datetime import datetime
from typing import Final, NewType

OrderId = NewType("OrderId", str)
EventId = NewType("EventId", str)

@dataclass(frozen=True, slots=True)
class OrderPlaced:
    """Event = a fact that happened. Past tense. Immutable.

    Carries enough payload that any consumer can act without a callback.
    """
    event_id: EventId
    order_id: OrderId
    total_cents: int
    placed_at: datetime
    version: Final[int] = 1
```

```python
# platform/eventbus.py
from collections import defaultdict
from collections.abc import Callable
from typing import TypeVar

E = TypeVar("E", bound=object)

class EventBus:
    def __init__(self) -> None:
        self._subs: dict[type[object], list[Callable[[object], None]]] = defaultdict(list)

    def subscribe[Ev](self, event_type: type[Ev], handler: Callable[[Ev], None]) -> None:
        # Cast: we know the dict stores Callable[[Ev], None] for this key.
        self._subs[event_type].append(handler)  # type: ignore[arg-type]

    def publish[Ev](self, event: Ev) -> None:
        for handler in self._subs[type(event)]:
            handler(event)
```

```python
# modules/billing/application/on_order_placed.py
from myproject.modules.orders.public import OrderPlaced
from myproject.modules.billing.application.charge import ChargeCustomer

def on_order_placed(charge: ChargeCustomer) -> None:
    def handler(event: OrderPlaced) -> None:
        charge(amount_cents=event.total_cents, order_id=event.order_id)
    bus.subscribe(OrderPlaced, handler)
```

**Event shape rules.**

- Past tense: `OrderPlaced`, not `PlaceOrder`.
- Immutable, identified (`event_id` for dedup), timestamped, versioned.
- Carry enough payload that consumers don't need a callback.
- Schema-versioned: a new `version` field guards against breaking consumers.

**The outbox pattern.** When a module both mutates its DB and publishes an
event, do both in the same transaction by writing the event to an `outbox`
table. A separate process reads the outbox and publishes. Without an outbox, a
DB-committed change with a failed publish leaves the system inconsistent. Adopt
outbox at _any_ point you might extract a module to a separate service.

```python
# modules/orders/application/place_order.py
from sqlalchemy.orm import Session
from myproject.modules.orders.domain.order import Order
from myproject.modules.orders.domain.events import OrderPlaced
from myproject.platform.outbox import OutboxMessage

def place_order(order: Order, session: Session) -> None:
    session.add(order)
    event = OrderPlaced.from_order(order)
    session.add(OutboxMessage(
        aggregate_id=order.id,
        event_type="OrderPlaced",
        version=event.version,
        payload=event.to_json(),
    ))
    session.commit()
```

A worker polls `outbox`, publishes each message, marks it published. Consumers
must be idempotent (events arrive at-least-once).

**Type-safety / static-analysis notes.** Subscribe with explicit `type[Ev]` so
the handler's argument type is checked. Use PEP 695 `[Ev]` for a parametric
`subscribe`. Avoid `Any`. The bus itself stores
`dict[type[object], list[Callable[[object], None]]]`; that single internal
`Any`-equivalent (`object`) is the only escape hatch and lives in the bus, not
at call sites.

**When NOT to use.** Two modules where module B is the only one that ever cares
about module A's state changes. That's a direct call dressed up as an event.
Save events for genuine fan-out (≥ 2 consumers) or for boundaries you expect to
extract to services.

**Real-world examples.** Shopify's Rails monolith uses domain events extensively
for cross-module reactions. ResellerPros' DDD systems use in-process buses
identical to the sketch above. Adapter to a real broker (Kafka/RabbitMQ) is a
one-file change once the outbox is in place.

**References.** Khononov, _Learning Domain-Driven Design_, 2021, ch. 9
("Communication Patterns"). Vernon, _IDDD_, 2013, ch. 8 ("Domain Events").
Richardson, "Outbox pattern,"
<https://microservices.io/patterns/data/transactional-outbox.html>.

---

## plugin-architecture

**What it is / Intent.** Extensibility via discovery: the host defines an
extension interface (a `Protocol`); plugins implement it; the host loads them at
runtime without naming them. Used by IDEs, data tools, CLI frameworks with a
community of authors. (Buse & Zimmermann, "Information Needs for Software
Development Analytics," ch. on plugin ecosystems; _Pluggable Type Systems_
literature.)

**When to reach for it / How it manifests.**

- Real third-party extension points (your team is not the only one writing
  plugins).
- A clear, narrow extension interface (one or two Protocols) that survives
  independent plugin upgrades.
- Anti-signal: a "plugin architecture" with one plugin written by your own team.
  That's ordinary modules with extra ceremony.

**Sketch — entry-point discovery.**

```python
# myproject/plugins/api.py — the public extension contract
from typing import Protocol

class Notifier(Protocol):
    """Plugins that deliver notifications.

    Must be stable across host versions: adding a method is a breaking change.
    """
    name: str
    def notify(self, message: str) -> None: ...
```

```toml
# In a plugin package's pyproject.toml
[project.entry-points."myproject.notifiers"]
slack = "my_slack_plugin.notifier:SlackNotifier"
email = "my_email_plugin.notifier:EmailNotifier"
```

```python
# myproject/plugins/loader.py
from importlib.metadata import entry_points
from typing import Final
from myproject.plugins.api import Notifier

ENTRY_POINT_GROUP: Final[str] = "myproject.notifiers"

def load_notifiers() -> list[Notifier]:
    """Discover and instantiate all installed Notifier plugins."""
    eps = entry_points(group=ENTRY_POINT_GROUP)
    notifiers: list[Notifier] = []
    for ep in eps:
        plugin_class = ep.load()
        instance = plugin_class()
        if not _satisfies_protocol(instance):
            raise PluginLoadError(f"{ep.name} does not implement Notifier")
        notifiers.append(instance)
    return notifiers

def _satisfies_protocol(obj: object) -> bool:
    return hasattr(obj, "name") and callable(getattr(obj, "notify", None))

class PluginLoadError(Exception): ...
```

**Versioning.** The plugin interface is a public API. Breaking changes need a
new namespace (`myproject.notifiers.v2`) and a migration window during which the
host loads both. Plugins in the wild do not upgrade in lockstep.

**Security.** Plugins run in the host process with the host's privileges. For
untrusted plugins, you need a different mechanism entirely — subprocess
isolation, WASM, or a language-level sandbox. None are built-in.

**Type-safety / static-analysis notes.** Protocol-based extension means the
_plugin package_ doesn't need to import the host. You may publish the Protocol
in a tiny `myproject-plugin-api` package so plugins type-check against it.
Runtime validation (`_satisfies_protocol`) catches plugins that look right at
install time but don't implement the interface — pyright won't catch this
because pyright doesn't load the host's plugin loader.

**When NOT to use.** Any extension point your own team writes. Use ordinary
modules. The entry-point discovery model is overkill until plugins live in
separate packages with separate release cycles.

**Real-world examples.** pytest (`pytest_*` entry points). pylint (custom
checkers). Black (no plugins by design — Łukasz Langa's choice). Click and Typer
plugin ecosystems. Jupyter extension API.

**References.** _Python Packaging User Guide_, "Entry points specification,"
<https://packaging.python.org/en/latest/specifications/entry-points/>. Beazley &
Jones, _Python Cookbook_, 3rd ed., O'Reilly, 2013, recipe 10.13 ("Importing
Modules Using a Name Given in a Variable").

---

## mvc-mvp-mvvm

**What it is / Intent.** A family of patterns for separating _what is shown_
(View), _what is shown about_ (Model), and _the glue between them_ (Controller /
Presenter / ViewModel). Originated in Smalltalk-80 (Reenskaug, 1979). Most
modern web frameworks are _MVC-flavored_; mobile/desktop UIs are commonly
_MVVM_.

**Distinctions.**

| Variant                                       | View knows…                | Model knows… | Glue knows…                       |
| --------------------------------------------- | -------------------------- | ------------ | --------------------------------- |
| **MVC** (Smalltalk, Rails, Django)            | Model directly (observes)  | Nothing      | Routes input to Model, picks View |
| **MVP** (legacy WinForms, Android pre-MVVM)   | Presenter only             | Nothing      | Calls View setters explicitly     |
| **MVVM** (WPF, Vue, Knockout, modern Android) | ViewModel via data binding | Nothing      | Exposes observable state          |

**When to reach for each.**

- **MVC.** Server-rendered web apps where the server picks templates and the
  client reloads pages. Most Django/Rails/Flask projects.
- **MVP.** Stateful desktop UIs where the framework does not provide data
  binding. Now rare; MVVM has won.
- **MVVM.** Reactive UIs with declarative bindings: SwiftUI, Jetpack Compose,
  Vue, React (with hooks). The ViewModel's observables are the View's source of
  truth.

**Sketch (MVC, Python web app).**

```python
# domain/order.py
from dataclasses import dataclass
from typing import NewType

OrderId = NewType("OrderId", str)

@dataclass(frozen=True, slots=True)
class Order:
    id: OrderId
    total_cents: int
    status: str

# views/orders.py — Jinja2 template selector + DTO assembly
from typing import TypedDict

class OrderViewData(TypedDict):
    id: str
    total: str
    status: str

def render_order_page(order: Order) -> tuple[str, OrderViewData]:
    return "orders/show.html", {
        "id": order.id,
        "total": f"${order.total_cents / 100:.2f}",
        "status": order.status,
    }

# controllers/orders.py
from typing import Protocol

class OrderRepository(Protocol):
    def get(self, order_id: OrderId) -> Order | None: ...

def show(repo: OrderRepository, order_id: OrderId) -> tuple[int, str, OrderViewData]:
    order = repo.get(order_id)
    if order is None:
        return 404, "errors/404.html", {"id": order_id, "total": "", "status": ""}
    template, data = render_order_page(order)
    return 200, template, data
```

**Sketch (MVVM, with reactive observable state).** In Python this rarely shows
up in the backend; it appears in PySide/PyQt and in cross-platform GUI
frameworks. The shape:

```python
# Pseudocode for a ViewModel pattern (Toga / PySide / etc.)
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

@dataclass
class OrderViewModel:
    """Observable state. The View binds to these properties."""
    _order: Order
    _on_change: list[Callable[[], None]]

    @property
    def total_label(self) -> str:
        return f"${self._order.total_cents / 100:.2f}"

    def reload(self, order: Order) -> None:
        self._order = order
        for cb in self._on_change:
            cb()
```

**Type-safety / static-analysis notes.** TypedDict for view-data DTOs gives the
templating layer a typed contract. Pydantic models work for inbound HTTP DTOs;
keep them at the controller boundary, not in the domain. mypy/pyright cannot
type-check Jinja templates directly — close that gap with a typed renderer or
move to a library that supports it (e.g., `jinja2-stubs` is partial).

**When NOT to use.** A stateless API server: there is no view. Use plain
controllers/handlers + DTOs. MVC ceremony is a bug for pure JSON APIs.

**Real-world examples.** Rails (server-rendered MVC). Django (MTV: Model,
Template, View — Django calls the controller a "view"). React (MVVM-flavored:
components are the view, hooks expose ViewModel state). Vue (MVVM by design).
SwiftUI (MVVM). WPF (the canonical MVVM).

**References.** Reenskaug, "Models-Views-Controllers," Xerox PARC technical
note, 1979. Fowler, "GUI Architectures," 2006,
<https://martinfowler.com/eaaDev/uiArchs.html>. Microsoft, "MVVM Pattern,"
<https://learn.microsoft.com/dotnet/architecture/maui/mvvm>.

---

## picking-a-shape

**Decision order, smallest commitment first.**

1. **One module, no layering.** Scripts, one-off tools, proofs of concept. Two
   files is fine.
2. **Layered monolith.** CRUD apps with thin domain logic. Enforce
   `domain → infra` dependency rule with a linter and stop.
3. **Hexagonal monolith.** Non-trivial domain, realistic likelihood of swapping
   adapters or adding entrypoints. Pay the port/adapter cost for the isolation.
4. **Modular monolith.** Multiple bounded contexts in one deployable. Enforce
   inter-module boundaries with import contracts.
5. **Microservices.** At least one module has independent
   deploy/scale/team/runtime reasons (Newman's qualification test,
   three-of-four).

**Default for a new service.** Start at level 3 (hexagonal monolith). Pre-invest
in the dependency rule; don't pre-invest in multiple services.

**Migration path.** Each level is reachable from the level below with mechanical
refactors, _provided the dependency rule is respected_. Violate the rule and you
lock yourself into the level you built at; every migration becomes a rewrite.

---

## enforcement-import-contracts

Architectural intent without enforcement is folklore. Encode every dependency
rule as a CI contract.

**`importlinter` — layered.**

```ini
# .importlinter
[importlinter]
root_packages =
    myproject

[importlinter:contract:layers]
name = Layered dependency rule
type = layers
layers =
    myproject.presentation
    myproject.application
    myproject.domain
    myproject.infrastructure
```

**`importlinter` — modular monolith with `forbidden`.**

```ini
[importlinter:contract:modules]
name = Modules only talk via public interfaces
type = forbidden
source_modules =
    myproject.modules
forbidden_modules =
    myproject.modules.*.domain
    myproject.modules.*.adapters
ignore_imports =
    myproject.modules.*.public -> myproject.modules.*.domain
    myproject.modules.*.public -> myproject.modules.*.application
```

**`grimp` — programmatic boundary tests.** Use this when contracts get too
expressive for INI:

```python
# tests/test_imports.py
import grimp

def test_no_circular_packages() -> None:
    graph = grimp.build_graph("myproject")
    cycles = graph.find_packages_in_circular_dependencies()
    assert not cycles, f"circular dependencies detected: {cycles}"

def test_domain_has_no_third_party_deps() -> None:
    graph = grimp.build_graph("myproject", include_external_packages=True)
    for module in graph.find_descendants("myproject.domain"):
        externals = {
            m.split(".")[0]
            for m in graph.find_modules_directly_imported_by(module)
            if not m.startswith("myproject")
        }
        allowed = {"dataclasses", "typing", "datetime", "decimal", "enum", "collections"}
        assert externals <= allowed, (
            f"domain module {module} imports forbidden: {externals - allowed}"
        )
```

Wire these into `make ci` and fail builds when they fail. The cost of a one-line
CI red is zero; the cost of `domain/` quietly importing `psycopg2` for two years
is a rewrite.

---

## review-checklist

For any proposal that adds a module, service, or layer:

1. Is there a concrete current problem this shape solves? Or is this
   future-proofing?
2. Which way do the dependencies point? Is the rule enforceable with a linter?
3. If this is a new service: does it have an independent
   deploy/scale/team/runtime reason? If not, make it a module.
4. If this is an event-driven boundary: is the event truly a fact in the past,
   or a disguised command? Is there an outbox?
5. Where is composition? A composition root at the entrypoint is correct;
   scattered `container.get()` calls are not.
6. Is there a migration path to the _next_ level if this one stops fitting? Or
   have we locked in?

If this proposal can be replaced by "add a module with a Protocol," do that
first.

---

## references

**Books.**

- Martin, Robert C. _Clean Architecture: A Craftsman's Guide to Software
  Structure and Design_. Pearson, 2017. ch. 14, ch. 22.
- Newman, Sam. _Building Microservices_, 2nd ed. O'Reilly, 2021. ch. 1, ch. 5,
  ch. 14.
- Vernon, Vaughn. _Implementing Domain-Driven Design_. Addison-Wesley, 2013. ch.
  4, ch. 8.
- Khononov, Vlad. _Learning Domain-Driven Design_. O'Reilly, 2021. ch. 9,
  ch. 14.
- Percival, Harry, and Bob Gregory. _Architecture Patterns with Python_.
  O'Reilly, 2020.
- Buschmann, Frank, Regine Meunier, Hans Rohnert, Peter Sommerlad, and Michael
  Stal. _Pattern-Oriented Software Architecture, Vol. 1_. Wiley, 1996. ch. 2.
- Fowler, Martin. _Patterns of Enterprise Application Architecture_.
  Addison-Wesley, 2002. ch. 1.
- Feathers, Michael. _Working Effectively with Legacy Code_. Prentice
  Hall, 2004. ch. 17 ("My Application Has No Structure").
- Beck, Kent. _Implementation Patterns_. Addison-Wesley, 2008. ch. 4 ("Class").

**Web sources.**

- Cockburn, Alistair. "Hexagonal architecture," 2005,
  <https://alistair.cockburn.us/hexagonal-architecture>.
- Palermo, Jeffrey. "The Onion Architecture: Part 1," 2008,
  <https://jeffreypalermo.com/2008/07/the-onion-architecture-part-1/>.
- Fowler, Martin. "Microservice Premium," 2015,
  <https://martinfowler.com/bliki/MicroservicePremium.html>.
- Fowler, Martin. "GUI Architectures," 2006,
  <https://martinfowler.com/eaaDev/uiArchs.html>.
- Richardson, Chris. "Pattern: Transactional Outbox,"
  <https://microservices.io/patterns/data/transactional-outbox.html>.
- _Python Packaging User Guide_, "Entry points specification,"
  <https://packaging.python.org/en/latest/specifications/entry-points/>.
