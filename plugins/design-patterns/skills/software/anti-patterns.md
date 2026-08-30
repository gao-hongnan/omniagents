# Software Anti-Patterns (Code-Level)

> Structural and code-level smells to flag in review and refactor on sight. Each
> entry names the symptom, the cost of leaving it, the target shape after
> refactoring, and the static-analysis mechanism that catches it.

This document is the _code-level_ counterpart to `architectural.md`. It covers
smells that live inside a file or a small group of files: god objects, anemic
models, primitive obsession, exception swallowing, type erosion, mutable
defaults. Architecture-level anti-patterns (Distributed Monolith, etc.) live in
`architectural.md`.

An anti-pattern is not "code I dislike." It is a shape that _predictably_ causes
defects, slows future change, or defeats the type system. If you cannot name the
concrete harm — with a code example and a static-analysis tool that catches the
fix — it does not belong on this list.

## How to use this file

- **In code review.** Scan the diff for the symptoms in
  [Review Checklist](#review-checklist). If you find one, refer the author here.
- **When refactoring.** Each entry has a Bad → Fixed pair and the type-system
  mechanism that prevents regression.
- **Per-entry shape.** _Symptom · Why it hurts · Bad/Fixed · Type-safety /
  static-analysis notes · When NOT to refactor · Real-world examples ·
  References_.
- **Strict typing.** Every fixed example is written to target mypy `--strict`
  and pyright `--strict`: no `Any`, PEP 604 unions, PEP 695 generics, `Self`,
  `Final`, `@override`, `Literal`, `NewType`, `TypedDict`, and the annotation
  evaluation policy assumed by this catalogue; see `SKILL.md` conventions.

## Contents

- [god-object-god-module](#god-object-god-module)
- [anemic-domain-model](#anemic-domain-model)
- [feature-envy](#feature-envy)
- [shotgun-surgery-divergent-change](#shotgun-surgery-divergent-change)
- [primitive-obsession](#primitive-obsession)
- [stringly-typed-apis](#stringly-typed-apis)
- [stringly-typed-booleans](#stringly-typed-booleans)
- [boolean-flag-parameters](#boolean-flag-parameters)
- [hidden-temporal-coupling](#hidden-temporal-coupling)
- [happy-path-only-error-handling](#happy-path-only-error-handling)
- [exception-swallowing](#exception-swallowing)
- [over-mocking-in-tests](#over-mocking-in-tests)
- [premature-abstraction](#premature-abstraction)
- [speculative-generality](#speculative-generality)
- [big-ball-of-mud](#big-ball-of-mud)
- [circular-imports](#circular-imports)
- [leaky-abstractions](#leaky-abstractions)
- [interface-segregation-violations](#interface-segregation-violations)
- [liskov-violations](#liskov-violations)
- [dead-code-tolerance](#dead-code-tolerance)
- [magic-numbers-magic-strings](#magic-numbers-magic-strings)
- [scattered-configuration](#scattered-configuration)
- [comments-as-apology](#comments-as-apology)
- [type-erosion](#type-erosion)
- [hand-rolled-boundary-coercion](#hand-rolled-boundary-coercion)
- [mutable-default-arguments](#mutable-default-arguments)
- [review-checklist](#review-checklist)
- [references](#references)

## god-object-god-module

**Symptom.** A class or module that accumulates unrelated responsibilities.
`UserManager` handles authentication, email, billing, audit logging, and report
generation. The file is 2,000+ lines; everything imports from it; nothing can
change without touching it.

**Why it hurts.** Every caller pulls in every transitive dependency. Tests must
stub a dozen collaborators. Merge conflicts cluster on this one file. The type
of `UserManager` tells you nothing about what a caller actually uses.

**Bad.**

```python
class UserManager:
    def __init__(
        self,
        db: "Database",
        smtp: "SmtpClient",
        billing: "StripeClient",
        audit: "AuditLog",
    ) -> None:
        self._db = db
        self._smtp = smtp
        self._billing = billing
        self._audit = audit

    def authenticate(self, email: str, password: str) -> "User": ...
    def send_welcome_email(self, user: "User") -> None: ...
    def charge_monthly(self, user: "User") -> "Invoice": ...
    def generate_report(self, user: "User") -> "Report": ...
```

**Fixed.** Split by _reason to change_, not by noun. Authentication changes when
the auth provider changes; billing changes when pricing changes. These are
different reasons and belong in different modules.

```python
from typing import Protocol
from dataclasses import dataclass

class Authenticator(Protocol):
    def authenticate(self, email: str, password: str) -> "User": ...

class BillingService(Protocol):
    def charge_monthly(self, user: "User") -> "Invoice": ...

@dataclass(frozen=True, slots=True)
class CheckoutFlow:
    auth: Authenticator   # the call site declares what it actually needs
    billing: BillingService

    def run(self, email: str, password: str) -> "Invoice":
        user = self.auth.authenticate(email, password)
        return self.billing.charge_monthly(user)
```

**Type-safety / static-analysis notes.** `pylint R0902/R0904` (too many instance
attributes / methods). `radon cc` flags high cyclomatic complexity per file.
ruff `PLR0904` flags too many public methods. The Protocol-based fix gives each
call site a _type signature that advertises its dependencies_ — which
mypy/pyright check.

**When NOT to refactor.** A 200-line module with cohesive helpers around a
single concept is not a god module. The line count alone is not the signal —
_unrelated responsibilities_ is.

**Real-world examples.** Java's pre-Spring "FacadeService" classes. Rails' fat
ActiveRecord models that grow billing, auth, and audit code. Many `utils.py`
files that end up importing the entire codebase.

**References.** Fowler, _Refactoring_, 2nd ed., Addison-Wesley, 2018, ch. 3
("Bad Smells in Code") — _Large Class_. Riel, _Object-Oriented Design
Heuristics_, Addison-Wesley, 1996, ch. 3.

---

## anemic-domain-model

**Symptom.** Dataclasses with only fields; all behavior lives in `*Service`
classes that reach into those dataclasses and mutate them. The data has no
opinions; the services enforce all invariants from the outside.

**Why it hurts.** Invariants are enforced at call sites, not at the data. Any
caller can set `order.status = "paid"` directly, bypassing the state machine.
The dataclass type does not encode what is _legal_; you must audit every service
to know. Bugs hide in the gap between "what the type allows" and "what the
business allows." (Fowler, "AnemicDomainModel," 2003.)

**Bad.**

```python
from dataclasses import dataclass

@dataclass
class Order:
    items: list["LineItem"]
    status: str           # any string is "valid" to the type checker
    discount_cents: int

class OrderService:
    def apply_discount(self, order: Order, percent: int) -> None:
        order.discount_cents = (
            sum(i.price_cents for i in order.items) * percent // 100
        )

    def mark_paid(self, order: Order) -> None:
        if order.status != "pending":
            raise InvalidTransition(order.status)
        order.status = "paid"

class InvalidTransition(Exception): ...
```

**Fixed.** Move behavior onto the entity. Use a `StrEnum` for the state machine.
Keep `*Service` for _orchestration_ (cross-entity transactions, external IO) —
not for basic invariant enforcement.

```python
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self

class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"

@dataclass(slots=True)
class Order:
    items: list["LineItem"]
    status: OrderStatus
    discount_cents: int = 0

    def apply_discount(self, percent: int) -> None:
        if not 0 <= percent <= 100:
            raise ValueError(f"percent out of range: {percent}")
        self.discount_cents = (
            sum(i.price_cents for i in self.items) * percent // 100
        )

    def mark_paid(self) -> Self:
        if self.status is not OrderStatus.PENDING:
            raise InvalidTransition(self.status)
        self.status = OrderStatus.PAID
        return self

class InvalidTransition(Exception): ...
```

**Type-safety / static-analysis notes.** `StrEnum` (PEP 663) makes invalid
statuses impossible to assign at the type level. `Self` (PEP 673) lets
`mark_paid` return the correct subclass type if `Order` is subclassed.
mypy/pyright catch any caller that tries `order.status = "paid"` (string literal
not assignable to `OrderStatus`).

**When NOT to refactor.** A pure read model (e.g., an HTTP response DTO)
genuinely has no behavior; that's fine — it's a data carrier, not a domain
entity. The smell is when the _domain_ model is anemic.

**Real-world examples.** Most Spring `@Entity` JPA classes circa 2010. Many
Django applications where all logic lives in `views.py` and the models are bare
fields.

**References.** Fowler, "AnemicDomainModel," 2003,
<https://martinfowler.com/bliki/AnemicDomainModel.html>. Evans, _Domain-Driven
Design_, Addison-Wesley, 2003, ch. 5 ("A Model Expressed in Software"). Vernon,
_Implementing Domain-Driven Design_, Addison-Wesley, 2013, ch. 6 ("Entities").

---

## feature-envy

**Symptom.** A method on class `A` spends most of its time calling getters on
class `B` and computing things about `B`. The logic lives where the data
doesn't.

**Why it hurts.** Any change to `B`'s shape requires hunting down enviers.
Encapsulation is broken — `B` must expose its internals to satisfy the envier.

**Bad.**

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class LineItem:
    price_cents: int
    tax_rate_bps: int  # basis points: 100 = 1%

@dataclass(frozen=True, slots=True)
class Invoice:
    lines: list[LineItem]

class TaxCalculator:
    def total_tax(self, invoice: Invoice) -> int:
        # Every operation reads from invoice.lines.
        return sum(
            line.price_cents * line.tax_rate_bps // 10_000
            for line in invoice.lines
        )
```

**Fixed.** Move the method to where the data lives. Keep the outer class only if
it coordinates _multiple_ types.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class LineItem:
    price_cents: int
    tax_rate_bps: int

    def tax(self) -> int:
        return self.price_cents * self.tax_rate_bps // 10_000

@dataclass(frozen=True, slots=True)
class Invoice:
    lines: list[LineItem]

    def total_tax(self) -> int:
        return sum(line.tax() for line in self.lines)
```

**Type-safety / static-analysis notes.** No specific lint rule catches feature
envy directly; `pylint R0916` flags methods with too many arguments which often
correlates. The signal comes from review: a method whose body is
`arg.foo + arg.bar - arg.baz` belongs on `arg`'s class.

**When NOT to refactor.** If the "envious" method genuinely straddles two types
(applying a discount that depends on both customer tier and order total), a
separate service is correct.

**Real-world examples.** "Validator" classes that iterate over a domain object's
fields. "Formatter" classes that read every attribute of a model to produce a
string. Move the logic onto the model unless the formatter swaps between
presentation backends.

**References.** Fowler, _Refactoring_, 2nd ed., 2018, ch. 3 — _Feature Envy_;
ch. 8 — _Move Function_. Beck, _Implementation Patterns_, Addison-Wesley, 2008,
ch. 4.

---

## shotgun-surgery-divergent-change

These are mirror images. Both indicate misplaced responsibilities.

**Shotgun Surgery.** Adding a single concept (e.g., a new currency) forces edits
across fifteen files. A module that should own the concept does not exist; the
concept is smeared across the codebase.

**Divergent Change.** A single module is edited for multiple unrelated reasons —
one week for a new report format, the next for a new auth method, the next for a
DB migration. The module has too many responsibilities.

**Bad — Shotgun (currency support smeared across files).**

```python
# pricing.py
def format_price(amount_cents: int) -> str:
    return f"${amount_cents / 100:.2f}"   # USD only

# checkout.py
def total(items: list[int]) -> int:
    return sum(items)                      # implicitly USD

# invoices.py
def render_total(amount_cents: int) -> str:
    return f"${amount_cents / 100:.2f}"   # USD only
```

Adding EUR requires touching every file. The concept "money + currency" has no
home.

**Fixed — introduce the missing abstraction.**

```python
# money.py
from dataclasses import dataclass
from enum import StrEnum
from typing import Self

class Currency(StrEnum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

@dataclass(frozen=True, slots=True)
class Money:
    amount_cents: int
    currency: Currency

    def __add__(self, other: "Money") -> Self:
        if self.currency is not other.currency:
            raise ValueError(
                f"currency mismatch: {self.currency} vs {other.currency}"
            )
        return type(self)(
            amount_cents=self.amount_cents + other.amount_cents,
            currency=self.currency,
        )

    def format(self) -> str:
        symbol = {"USD": "$", "EUR": "€", "GBP": "£"}[self.currency.value]
        return f"{symbol}{self.amount_cents / 100:.2f}"
```

Now adding a currency is a one-line edit in `Currency`.

**Detection.** `git log --stat -- path/to/module`. If one concept touches many
files on every change, you have shotgun surgery. If one file changes for many
unrelated reasons, divergent change.

**Type-safety / static-analysis notes.** `Money` as a
`@dataclass(frozen=True, slots=True)` with `Currency: StrEnum` is exhaustively
type-checkable. Any function taking `int` for an amount is now suspect — replace
with `Money`.

**When NOT to refactor.** When the concept is genuinely cross-cutting and adding
a layer of indirection wouldn't reduce edit-locality (e.g., logging — every file
logs).

**Real-world examples.** Currency, time zones, locales, units of measurement
(meters vs feet). The Mars Climate Orbiter loss in 1999 was unit confusion
across module boundaries.

**References.** Fowler, _Refactoring_, 2nd ed., 2018, ch. 3 — _Shotgun Surgery_,
_Divergent Change_. Khononov, _Learning Domain-Driven Design_, O'Reilly, 2021,
ch. 6.

---

## primitive-obsession

**Symptom.** Important domain concepts are passed around as `str`, `int`, or
`float`. `user_id: str`, `amount_cents: int`, `email: str`. The compiler cannot
stop you from passing a user id where a tenant id is expected.

**Why it hurts.** Whole classes of bugs (unit mismatches, id mix-ups, validation
bypass) become impossible to catch with static analysis. Validation is
duplicated at every boundary, or skipped.

**Bad.**

```python
def fetch_user(user_id: str) -> "User": ...
def fetch_tenant(tenant_id: str) -> "Tenant": ...

t = "t_123"
fetch_user(t)  # type checker sees both as `str`; no error
```

**Fixed.** `NewType` for plain identifiers; a small
`@dataclass(frozen=True, slots=True)` for anything with invariants or multiple
fields.

```python
from typing import NewType, Self
from dataclasses import dataclass

UserId = NewType("UserId", str)
TenantId = NewType("TenantId", str)

def fetch_user(user_id: UserId) -> "User": ...
def fetch_tenant(tenant_id: TenantId) -> "Tenant": ...

fetch_user(TenantId("t_123"))  # pyright/mypy error: TenantId not assignable to UserId

@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if "@" not in self.value:
            raise ValueError(f"invalid email: {self.value!r}")

    @classmethod
    def parse(cls, raw: str) -> Self:
        return cls(value=raw.strip().lower())

@dataclass(frozen=True, slots=True)
class Money:
    amount_cents: int
    currency: str

    def __add__(self, other: Self) -> Self:
        if self.currency != other.currency:
            raise ValueError(
                f"currency mismatch: {self.currency} vs {other.currency}"
            )
        return type(self)(
            self.amount_cents + other.amount_cents, self.currency
        )
```

**Type-safety / static-analysis notes.** `NewType` is the cheapest possible
primitive replacement — zero runtime cost, full type-level discrimination.
mypy's `disallow_subclassing_any` and `strict_equality` give you the best
signal. ruff has no specific rule but flagged custom rules can detect string
parameters named `*_id`.

**When NOT to refactor.** One-off internal tuples used within a single function.
Don't wrap everything; the goal is to constrain _boundaries_.

**Real-world examples.** Stripe IDs use prefixes (`cus_`, `acct_`, `pi_`)
precisely so that runtime mistakes can be caught — but that's a runtime hack for
what `NewType` solves at type-check time. Mars Climate Orbiter, again: a `force`
value in pound-seconds was treated as newton-seconds.

**References.** Fowler, _Refactoring_, 2nd ed., 2018, ch. 3 — _Primitive
Obsession_; ch. 7 — _Replace Primitive with Object_. Evans, _Domain-Driven
Design_, 2003, ch. 5 — _Value Objects_.

---

## stringly-typed-apis

**Symptom.** APIs that accept magic strings: `status="pending"`,
`mode="strict"`, `level="WARN"`. Typos are runtime errors; valid values are not
discoverable without reading source.

**Bad.**

```python
def log(level: str, message: str) -> None: ...

log("WARNING", "oops")  # silently wrong: code expects "WARN"
log("warm", "oops")     # silently wrong: typo
```

**Fixed.**

```python
from enum import StrEnum
from typing import Literal

class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"

def log(level: LogLevel, message: str) -> None: ...

log(LogLevel.WARN, "oops")  # OK
log("WARN", "oops")          # mypy/pyright error: str not assignable to LogLevel

# Literal is the lighter option when serialization is not needed.
def set_mode(mode: Literal["strict", "lax"]) -> None: ...
set_mode("strict")  # OK
set_mode("strikt")  # mypy/pyright error
```

**Type-safety / static-analysis notes.** `StrEnum` (PEP 663) gives values that
_are_ strings (so they JSON-serialize) and a closed set the checker enforces.
`Literal["a", "b"]` is lighter when you don't need an enum type. ruff `PLW1641`
and `EM101` give nudges in adjacent territory.

**When NOT to refactor.** A truly open-ended string field (e.g., user-supplied
tags). Trying to enumerate it would be wrong.

**Real-world examples.** `logging` module's level constants (numbers, but
`getLevelName` returns strings). Many SQLAlchemy `enum`s typed as `str`. Pre-PEP
586 Python before `Literal` existed.

**References.** PEP 586, "Literal Types," 2019. PEP 663, "Standardize StrEnum
behavior," 2021. Fowler, _Refactoring_, 2nd ed., 2018, ch. 3 — _Primitive
Obsession_.

---

## stringly-typed-booleans

**Symptom.** A _boolean state machine_ expressed as strings: `status="active"`,
`status="inactive"`. Two values, no enum, no Literal.

**Bad.**

```python
def is_user_active(user: "User") -> bool:
    return user.status == "active"  # one typo = wrong answer

def activate(user: "User") -> None:
    user.status = "ative"  # silent bug
```

**Fixed.**

```python
from enum import StrEnum
from dataclasses import dataclass

class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"

@dataclass(slots=True)
class User:
    id: str
    status: UserStatus

def is_user_active(user: User) -> bool:
    return user.status is UserStatus.ACTIVE   # `is` works for enum members

def activate(user: User) -> None:
    user.status = UserStatus.ACTIVE
```

**Bonus — when "two values" is genuinely a flag, use `bool`.** If the values are
"present/absent" or "on/off" with no third state coming, `bool` is correct.
`StrEnum` is for cases that _might_ grow a `SUSPENDED` or `BANNED` value later.

**Type-safety / static-analysis notes.** Comparison with `is` instead of `==`
for enum members is faster and safer (caught by ruff `E712` for the
`True`/`False` case). mypy/ pyright reject `user.status = "ative"` if
`status: UserStatus`.

**When NOT to refactor.** When the field is genuinely an open-ended string
(free-form tag).

**Real-world examples.** Django's pre-`TextChoices` model fields. Many
CSV-driven import pipelines that round-trip `"yes"/"no"` strings.

**References.** PEP 663, "Standardize StrEnum behavior," 2021. Beck,
_Implementation Patterns_, 2008, ch. 6 ("Behavior").

---

## boolean-flag-parameters

**Symptom.** Functions whose behavior forks on a boolean. The call site is
unreadable; the function body has two distinct paths joined by an `if`.

**Bad.**

```python
def render(user: "User", short: bool = False) -> str: ...

render(user, True)  # what does True mean here? unreadable.
```

**Fixed.** Split into two functions with descriptive names, or take a `StrEnum`.

```python
from enum import StrEnum

def render_full(user: "User") -> str: ...
def render_short(user: "User") -> str: ...

# If the two really share structure, make the discriminator explicit:
class RenderMode(StrEnum):
    FULL = "full"
    SHORT = "short"

def render(user: "User", mode: RenderMode) -> str: ...

render(user, RenderMode.SHORT)  # readable, exhaustive, type-checked
```

**Type-safety / static-analysis notes.** ruff `FBT001`, `FBT002`, `FBT003` flag
boolean positional parameters and boolean defaults. `match` on `RenderMode` is
exhaustive — pyright warns on a missing case.

**When NOT to refactor.** Genuine binary options with no behavior change worth
naming (`ignore_case=True` on a regex). Even then, prefer keyword-only:
`compile(r"...", *, ignore_case: bool = False)`.

**Real-world examples.** `requests.get(url, verify=False)` — three letters that
disable TLS verification, easy to miss in review.
`subprocess.run(..., shell=True)` — shell-injection enabling flag. Both are kept
for backwards compatibility but flagged by ruff.

**References.** Martin, _Clean Code_, Pearson, 2008, ch. 3 ("Functions") — _Flag
Arguments_. Fowler, _Refactoring_, 2nd ed., 2018, ch. 11 — _Remove Flag
Argument_.

---

## hidden-temporal-coupling

**Symptom.** Methods must be called in a specific order, but the type signature
does not enforce it. The contract is folklore.

**Bad.**

```python
class Report:
    def configure(self, source: "DataSource") -> None: ...
    def compute(self) -> None: ...
    def render(self) -> str: ...  # crashes if compute() wasn't called

report = Report()
print(report.render())  # runtime error, no static warning
```

**Fixed.** Make each stage return the next type. The type system enforces
ordering.

```python
from dataclasses import dataclass
from typing import Self

@dataclass(frozen=True, slots=True)
class ConfiguredReport:
    source: "DataSource"

    def compute(self) -> "ComputedReport":
        return ComputedReport(rows=[...])

@dataclass(frozen=True, slots=True)
class ComputedReport:
    rows: list["Row"]

    def render(self) -> str: ...

# Ordering enforced by types: you cannot render() until you compute().
rendered = ConfiguredReport(source=src).compute().render()
```

**Type-safety / static-analysis notes.** Each step's return type is the only
thing the next step can be called on. mypy/pyright reject
`ConfiguredReport(...).render()`.

**When NOT to refactor.** When the steps must stay on one object (e.g., a
builder that gets assembled across several call sites). Use the State pattern
with discriminated states. Or make stage transitions return `Self` with a
phantom-type marker.

**Real-world examples.** Many "open/use/close" file-like APIs (use a context
manager). Builders that crash if you forget `.build()` (use the pattern above).
Database connection pools that crash if you forget `.connect()` first.

**References.** Beck, _Implementation Patterns_, 2008, ch. 5 ("State"). Vernon,
_Implementing Domain-Driven Design_, 2013, ch. 6.

---

## happy-path-only-error-handling

**Symptom.** Code written as if IO never fails, networks never partition, and
JSON is always well-formed.

**Bad.**

```python
def fetch_profile(user_id: "UserId") -> "Profile":
    raw = httpx.get(f"/users/{user_id}").json()
    return Profile(name=raw["name"], email=raw["email"])
```

**Why it hurts.** Every failure mode becomes a 500 in production. No retries, no
timeout, no fallback, no structured error. Nobody can tell whether a `KeyError`
in the logs is a bug or expected.

**Fixed.** At every process boundary (network, disk, subprocess, user input):

1. Set a timeout.
2. Decide which errors are retryable.
3. Map transport errors to domain errors the caller can act on.
4. Log enough context to diagnose without re-running.

```python
from typing import NewType
import httpx

UserId = NewType("UserId", str)

class ProfileUnavailable(Exception):
    def __init__(self, user_id: UserId, reason: str) -> None:
        super().__init__(f"profile unavailable for {user_id}: {reason}")
        self.user_id = user_id
        self.reason = reason

class ProfileMalformed(Exception):
    def __init__(self, user_id: UserId, missing: str) -> None:
        super().__init__(f"profile malformed for {user_id}: missing {missing}")

def fetch_profile(user_id: UserId) -> "Profile":
    try:
        response = httpx.get(f"/users/{user_id}", timeout=5.0)
        response.raise_for_status()
        raw = response.json()
    except httpx.TimeoutException as exc:
        raise ProfileUnavailable(user_id, reason="timeout") from exc
    except httpx.HTTPStatusError as exc:
        raise ProfileUnavailable(
            user_id, reason=f"http_{exc.response.status_code}"
        ) from exc
    try:
        return Profile(name=raw["name"], email=raw["email"])
    except KeyError as exc:
        raise ProfileMalformed(user_id, missing=str(exc)) from exc
```

**Type-safety / static-analysis notes.** Custom exception types let callers
catch specific failure modes. ruff `BLE001` (blind except), `B017` (bare except
inside try), and `PT012` (pytest-specific) catch related issues. Always use
`raise X from exc` so the original cause is preserved in the chained traceback.

**When NOT to refactor.** Internal helpers that genuinely have no failure modes
(pure math). Process-internal code where exceptions naturally propagate to a
top-level handler.

**Real-world examples.** Almost every production incident postmortem mentions an
unhandled `KeyError` or `TimeoutError` at a process boundary. The Knight Capital
$440M trading loss in 2012 began with an exception that took down a server.

**References.** Nygard, _Release It!_, 2nd ed., Pragmatic Bookshelf, 2018, ch. 4
("Stability Patterns"). Beazley & Jones, _Python Cookbook_, 3rd ed., O'Reilly,
2013, ch. 14.

---

## exception-swallowing

**Symptom.**

```python
try:
    do_work()
except Exception:
    pass
```

Or the slightly-more-polite version:

```python
try:
    do_work()
except Exception as exc:
    logger.error("something went wrong")  # no exc info, no context
```

**Why it hurts.** The bug that caused the exception is invisible. Incidents take
hours longer to diagnose because the stack trace was discarded. Retries are
silent; cascading failures are silent; data corruption is silent.

**Fixed.** Catch the _narrowest_ exception you can actually handle. Re-raise or
wrap anything else. If you truly must log-and-continue, log with `exc_info=True`
(or `logger.exception(...)`) and a structured reason.

```python
import logging
logger = logging.getLogger(__name__)

class TransientBackendError(Exception): ...

def do_work() -> None: ...

try:
    do_work()
except TransientBackendError:
    logger.warning(
        "backend transient failure, retrying",
        exc_info=True,
        extra={"op": "do_work"},
    )
    raise
except Exception:
    logger.exception("do_work failed unexpectedly")
    raise
```

**Bare `except:` (no `Exception`)** also catches `KeyboardInterrupt` and
`SystemExit`. Never use it. ruff `E722` flags it.

**Type-safety / static-analysis notes.** ruff `BLE001` (blind except), `S110`
(bandit: try/except/pass), `S112` (try/except/continue without log) — all catch
the bad shape. mypy/pyright cannot enforce "you must re-raise" but
`# noqa: BLE001` makes ignored cases visible in review.

**When NOT to refactor.** When the exception is genuinely benign and there's a
tested, documented reason (e.g., a deletion that's idempotent — `OSError` on
`unlink` of a non-existent file). Even then, catch the _specific_ error class.

**Real-world examples.** Almost every codebase older than five years contains
`except: pass` with a comment "TODO: figure out why this fails." That comment is
older than several engineers.

**References.** Martin, _Clean Code_, Pearson, 2008, ch. 7 ("Error Handling").
Bandit documentation,
<https://bandit.readthedocs.io/en/latest/plugins/b110_try_except_pass.html>.

---

## over-mocking-in-tests

**Symptom.** A test file where most lines are `mock.patch(...)`; the test
asserts that mock methods were called with certain arguments; no real code path
is exercised.

**Why it hurts.** You are testing that your test setup matches your test setup.
Refactors that don't change behavior break every test. Actual bugs — wrong SQL,
wrong ordering, wrong serialization — pass because they live in the code the
mocks replaced.

**Bad.**

```python
from unittest.mock import patch, MagicMock

def test_register_user_sends_email() -> None:
    with patch("app.users.RegisterUser") as ru, \
         patch("app.users.SmtpClient") as smtp:
        ru.return_value.return_value = MagicMock(id="u1")
        smtp.return_value.send.return_value = None
        # ... 30 more lines of mock setup ...
        # Finally:
        smtp.return_value.send.assert_called_once()
    # What did this actually verify?
```

**Fixed.** Test real domain code against in-memory or containerized
implementations of external dependencies. Mock only at the _edges_. Prefer fakes
(small hand-written in-memory implementations of the Protocol) over mocks for
collaborators with state.

```python
from typing import Protocol, override
from dataclasses import dataclass

class UserRepository(Protocol):
    def get(self, user_id: "UserId") -> "User | None": ...
    def save(self, user: "User") -> None: ...

class InMemoryUserRepository:
    def __init__(self) -> None:
        self._store: dict["UserId", "User"] = {}

    @override
    def get(self, user_id: "UserId") -> "User | None":
        return self._store.get(user_id)

    @override
    def save(self, user: "User") -> None:
        self._store[user.id] = user

class CountingEmailSender:
    def __init__(self) -> None:
        self.sent: list["User"] = []

    def send_welcome(self, user: "User") -> None:
        self.sent.append(user)

def test_register_user_sends_email() -> None:
    repo = InMemoryUserRepository()
    sender = CountingEmailSender()
    register = RegisterUser(repo=repo, sender=sender)

    user = register(Email.parse("a@b.com"))

    assert repo.get(user.id) is not None
    assert len(sender.sent) == 1
```

**Type-safety / static-analysis notes.** Fakes are normal classes that implement
the Protocol — `@override` (PEP 698) catches drift between the Protocol and the
fake. mypy/ pyright check that fakes really do satisfy the interface;
`MagicMock` defeats both checkers.

**When NOT to refactor.** When the collaborator is genuinely an opaque external
(a network call). Mock it at the boundary, with a single mock per test,
narrowly. Use `responses` or `respx` for HTTP, not `MagicMock`.

**Real-world examples.** Django test suites that mock `models.User.objects.get`
instead of using a test database. Microservice tests that mock the HTTP client
instead of using an in-memory fake server.

**References.** Meszaros, _xUnit Test Patterns_, Addison-Wesley, 2007, ch. 11
("Test Doubles") — distinguishes Mock, Stub, Fake, Spy. Freeman & Pryce,
_Growing Object-Oriented Software, Guided by Tests_, Addison-Wesley, 2009.
Fowler, "Mocks Aren't Stubs,"
<https://martinfowler.com/articles/mocksArentStubs.html>.

---

## premature-abstraction

**Symptom.** A Protocol with one implementation. A factory that returns one
class. A plugin system with one plugin. An `*Adapter` that trivially forwards
every method. Configuration for something there is only one of.

**Why it hurts.** Every layer costs readers attention and adds a place bugs can
hide. "Flexibility for future needs" that never materialize is deadweight; when
the real second case arrives, the speculative abstraction rarely fits it anyway.

**Bad.**

```python
from typing import Protocol

class GreeterProtocol(Protocol):
    def greet(self, name: str) -> str: ...

class EnglishGreeter:
    def greet(self, name: str) -> str:
        return f"Hello, {name}!"

class GreeterFactory:
    @staticmethod
    def create() -> GreeterProtocol:
        return EnglishGreeter()  # the only implementation

def hello(name: str) -> str:
    greeter = GreeterFactory.create()
    return greeter.greet(name)
```

**Fixed.**

```python
def hello(name: str) -> str:
    return f"Hello, {name}!"
```

**Rule of three.** Write the direct code. Write it again when a second case
appears. Extract the abstraction when the _third_ case shows up and you can see
the shape. Two cases is often a coincidence; three is a pattern. (Beck,
_Implementation Patterns_, 2008.)

**Type-safety / static-analysis notes.** No static analyzer catches premature
abstraction because nothing is _wrong_ — the indirection is just wasted. The
smell is review-only: search for Protocols with one implementation
(`grep "implements GreeterProtocol"` returns one hit).

**When NOT to refactor.** When you're days away from the second case and have a
clear shape for the abstraction. Even then, write both call sites first; make
the shared shape emerge.

**Real-world examples.** "Repository" pattern over a single in-memory dict.
"Strategy" pattern with one strategy. Factory classes over a `dict` lookup with
one entry.

**References.** Fowler, _Refactoring_, 2nd ed., 2018, ch. 24 — _Speculative
Generality_. Beck, _Implementation Patterns_, 2008, ch. 4. Hunt & Thomas, _The
Pragmatic Programmer_, 20th anniversary ed., Addison-Wesley, 2019, _Rule of
Three_.

---

## speculative-generality

**Symptom.** Hooks, base classes, and configuration knobs added "in case we need
them." Empty methods overridden in only one subclass. Class hierarchies one
level deep.

**Bad.**

```python
from typing import Protocol, override

class FormatterProtocol(Protocol):
    def format(self, value: object) -> str: ...
    def pre_format(self, value: object) -> object: ...   # never overridden
    def post_format(self, formatted: str) -> str: ...    # never overridden

class JsonFormatter:
    @override
    def pre_format(self, value: object) -> object:
        return value
    @override
    def post_format(self, formatted: str) -> str:
        return formatted
    @override
    def format(self, value: object) -> str:
        import json
        return json.dumps(self.pre_format(value))
```

**Fixed.**

```python
import json

def to_json(value: object) -> str:
    return json.dumps(value)
```

**Type-safety / static-analysis notes.** ruff `B027` flags empty methods on
abstract base classes. pyright does not flag unused overrides directly. The
signal is review-based: hooks with no real overriders.

**When NOT to refactor.** If you're a framework author with real downstream
extension needs, hooks are warranted — but document the extension contract and
add a CI test that exercises a non-trivial subclass.

**Real-world examples.** Java Spring's many `*Aware` interfaces (genuinely
useful in Spring's dependency-injection model; useless in user code that doesn't
subclass Spring internals). Python's `__init_subclass__` used speculatively
without any subclass.

**References.** Fowler, _Refactoring_, 2nd ed., 2018, ch. 24 — _Speculative
Generality_ (distinct from premature abstraction in that the _future
flexibility_ is the bait, not the abstraction itself).

---

## big-ball-of-mud

**Symptom.** Modules import from each other in every direction. No discernible
layering. Renaming a function requires searching every file. New features can
only be added by grepping for "similar" existing code and copy-pasting. (Foote &
Yoder, "Big Ball of Mud," 1997.)

**Why it hurts.** Onboarding is measured in months. Any change risks breaking
something far away. Tests are brittle because nothing is isolated.

**You don't fix a ball of mud in one sitting.** Strategy:

1. Draw a dependency graph (`pydeps`, `grimp`). Identify the worst cycles.
2. Freeze the worst module behind a Protocol. New code depends on the Protocol.
3. Migrate callers one at a time to the Protocol.
4. Once the Protocol is the only door, rewrite or split the implementation.

```python
# Step 2: extract the Protocol; new callers depend on this only.
from typing import Protocol

class UserService(Protocol):
    def get(self, user_id: "UserId") -> "User | None": ...
    def update(self, user: "User") -> None: ...

class LegacyUserService:  # the existing tangled implementation
    def get(self, user_id: "UserId") -> "User | None": ...
    def update(self, user: "User") -> None: ...

# New code:
def some_new_feature(svc: UserService) -> None: ...
```

**Type-safety / static-analysis notes.** `import-linter` and `grimp` (see
`architectural.md`) catch cycles in CI. Run regularly while the cleanup is in
progress.

**When NOT to refactor.** When the legacy system is on a deprecation path and
will be replaced wholesale. Refactoring the muddy version is wasted effort if
you'll throw it away.

**Real-world examples.** Most codebases inherited from acquisitions. Many
academic-origin codebases (jupyter notebook → script → "system"). Foote &
Yoder's original paper notes: this is, statistically, the most common
architecture in the wild.

**References.** Foote, Brian, and Joseph Yoder. "Big Ball of Mud." _PLoP_ 1997.
Feathers, _Working Effectively with Legacy Code_, Prentice Hall, 2004 — the
entire book is the playbook.

---

## circular-imports

**Symptom.**
`ImportError: cannot import name 'X' from partially initialized module 'Y'`. Or
the quieter variant: imports that only work because of import-order accidents.

**Root cause.** Two modules genuinely depend on each other at module load time.
Usually a sign that a third concept wants to exist between them.

**Refactor targets.**

- **Extract the shared type.** If `users.py` and `orders.py` both need `Money`,
  move `Money` to `money.py`. Both import from it.

- **Use `typing.TYPE_CHECKING`** for type-only imports.

    ```python
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from .orders import Order

    def process(order: "Order") -> None: ...   # forward-reference string
    ```

- **Invert via Protocol.** The "downstream" module defines a Protocol for what
  it needs; the "upstream" module implements it. The dependency arrow flips.

- **Defer the import** inside a function — _only_ if the import is genuinely
  lazy by design. Do not use this as a workaround for bad layering.

**Type-safety / static-analysis notes.** `if TYPE_CHECKING:` imports are visible
to mypy/pyright at type-check time but not at runtime. ruff `TC001`/`TC002`
(typing imports should be inside TYPE_CHECKING) help organize. `import-linter`
cycles contract catches the structural problem.

**When NOT to refactor.** Never. Circular imports indicate a missing concept.
Find it.

**Real-world examples.** SQLAlchemy declarative models with two tables that
ForeignKey-reference each other. Django apps where `models.py` and `signals.py`
import each other.

**References.** Feathers, _Working Effectively with Legacy Code_, 2004, ch. 21
("I'm Changing the Same Code All Over the Place"). _Python docs_,
"typing.TYPE_CHECKING."

---

## leaky-abstractions

**Symptom.** An interface claims to hide a detail but its users must understand
the detail to use it correctly. A `Cache` Protocol whose callers must know it's
backed by Redis to reason about TTL semantics. A `Repository` whose methods
return SQLAlchemy models. (Spolsky, "The Law of Leaky Abstractions," 2002.)

**Why it hurts.** Swapping the implementation is impossible without rewriting
every caller. The abstraction lied — it added a layer of types without reducing
the knowledge callers need.

**Bad.**

```python
from typing import Protocol
from sqlalchemy.exc import IntegrityError

class UserRepository(Protocol):
    def save(self, user: "User") -> None: ...

# Caller must know it's SQLAlchemy to handle the failure mode.
try:
    repo.save(user)
except IntegrityError:   # leaked from SQLAlchemy
    ...
```

**Fixed.** The interface returns domain types; errors surfaced at the interface
are domain errors.

```python
from typing import Protocol

class DuplicateUser(Exception):
    def __init__(self, email: str) -> None:
        super().__init__(f"user with email {email} already exists")

class UserRepository(Protocol):
    def save(self, user: "User") -> None:
        """Raise DuplicateUser if a user with this email already exists."""

# Implementation translates infra errors to domain errors.
class PostgresUserRepository:
    def save(self, user: "User") -> None:
        try:
            self._session.add(user)
            self._session.commit()
        except IntegrityError as exc:
            raise DuplicateUser(user.email.value) from exc
```

**Type-safety / static-analysis notes.** Pyright/mypy don't catch _what types
leak_; the discipline is review-based. `import-linter` catches the structural
symptom: domain code importing `sqlalchemy.exc.IntegrityError` is an abstraction
leak.

**When NOT to refactor.** When you've decided to live with the implementation
forever and gain real value from the leakiness (rare).

**Real-world examples.** Django's `Model.objects.get()` raising `DoesNotExist` —
fine inside Django, but every cross-cutting helper that catches it leaks Django
through the codebase. SQLAlchemy `Query` objects passed across layers.

**References.** Spolsky, Joel. "The Law of Leaky Abstractions," 2002,
<https://www.joelonsoftware.com/2002/11/11/the-law-of-leaky-abstractions/>.
Vernon, _Implementing Domain-Driven Design_, 2013, ch. 12 ("Repositories").

---

## interface-segregation-violations

**Symptom.** A Protocol with 15 methods; concrete implementations only need 3.
(Martin, _Clean Architecture_, 2017, ch. 10 — Interface Segregation Principle.)

**Why it hurts.** Implementations that don't need the extra methods either raise
`NotImplementedError` (a runtime trap) or stub them with no-ops (silent bugs).
Every caller of the fat interface drags in symbols it doesn't use; mocking is
painful.

**Bad.**

```python
from typing import Protocol

class FileSystem(Protocol):
    def read(self, path: str) -> bytes: ...
    def write(self, path: str, data: bytes) -> None: ...
    def delete(self, path: str) -> None: ...
    def list(self, path: str) -> list[str]: ...
    def watch(self, path: str) -> "Iterator[Event]": ...
    def chmod(self, path: str, mode: int) -> None: ...
    def chown(self, path: str, uid: int, gid: int) -> None: ...

class S3Filesystem:
    def read(self, path: str) -> bytes: ...
    def write(self, path: str, data: bytes) -> None: ...
    def delete(self, path: str) -> None: ...
    def list(self, path: str) -> list[str]: ...
    def watch(self, path: str) -> "Iterator[Event]":
        raise NotImplementedError("S3 has no watch")  # runtime trap
    def chmod(self, path: str, mode: int) -> None:
        raise NotImplementedError                      # silent on most code paths
    def chown(self, path: str, uid: int, gid: int) -> None:
        raise NotImplementedError
```

**Fixed.** Split into smaller, role-specific Protocols. Compose where needed.

```python
from typing import Protocol

class Reader(Protocol):
    def read(self, path: str) -> bytes: ...

class Writer(Protocol):
    def write(self, path: str, data: bytes) -> None: ...
    def delete(self, path: str) -> None: ...

class Lister(Protocol):
    def list(self, path: str) -> list[str]: ...

class Watcher(Protocol):
    def watch(self, path: str) -> "Iterator[Event]": ...

class S3Filesystem:  # implements Reader, Writer, Lister — and that's all.
    def read(self, path: str) -> bytes: ...
    def write(self, path: str, data: bytes) -> None: ...
    def delete(self, path: str) -> None: ...
    def list(self, path: str) -> list[str]: ...

def copy(src: Reader, dst: Writer, path: str) -> None:
    dst.write(path, src.read(path))
```

**Type-safety / static-analysis notes.** With Protocols, the call site declares
the _minimum_ interface it needs (`src: Reader`). Any object that has `read`
satisfies it. No fake `NotImplementedError`. mypy/pyright check that
`S3Filesystem` is structurally a `Reader & Writer & Lister`.

**When NOT to refactor.** When the interface is genuinely cohesive and every
method is used by every implementation.

**Real-world examples.** Java's `java.util.List` requires implementations of
`add`/`remove`/`set` that throw on immutable lists — a textbook ISP violation.
Python's `io.IOBase` is split into Reader/Writer/Seeker for the same reason.

**References.** Martin, _Clean Architecture_, 2017, ch. 10. Martin, "The
Interface Segregation Principle," 1996,
<http://staff.cs.utu.fi/~jounsmed/doos_06/material/Martin_OO-Principles.pdf>.

---

## liskov-violations

**Symptom.** A subclass whose behavior surprises callers that hold a reference
to the parent type. Overridden methods strengthen preconditions, weaken
postconditions, raise new exception types, or break invariants the parent
guarantees. (Liskov & Wing, "A Behavioral Notion of Subtyping," TOPLAS 1994.)

**Bad.**

```python
class Rectangle:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def set_width(self, w: int) -> None:
        self.width = w

    def set_height(self, h: int) -> None:
        self.height = h

class Square(Rectangle):
    def set_width(self, w: int) -> None:
        self.width = w
        self.height = w   # surprise: changes height too

    def set_height(self, h: int) -> None:
        self.width = h
        self.height = h
```

A function that takes `Rectangle`, sets width to 5 and height to 4, expects
`area == 20`. Pass a `Square`, get `area == 16`. The substitution silently
broke.

**Fixed.** Don't model `Square` as a subclass of `Rectangle`. They share a
_bounded polygon_ concept but differ in invariants. Make both implement a
Protocol of shared operations.

```python
from typing import Protocol
from dataclasses import dataclass

class Shape(Protocol):
    def area(self) -> int: ...
    def perimeter(self) -> int: ...

@dataclass(frozen=True, slots=True)
class Rectangle:
    width: int
    height: int

    def area(self) -> int:
        return self.width * self.height

    def perimeter(self) -> int:
        return 2 * (self.width + self.height)

@dataclass(frozen=True, slots=True)
class Square:
    side: int

    def area(self) -> int:
        return self.side * self.side

    def perimeter(self) -> int:
        return 4 * self.side
```

Immutability (`frozen=True`) eliminates the original surprise: there's no
`set_*` to violate.

**Type-safety / static-analysis notes.** mypy `--strict` and pyright `--strict`
enforce that overrides have compatible signatures. Pyright's
`--reportIncompatibleMethodOverride` catches narrower overrides. `@override`
(PEP 698) catches accidental overrides. None of them catch _behavioral_ LSP
violations — those need tests.

**When NOT to refactor.** When the violation is intentional and documented (rare
and suspicious — typically points to a wrong taxonomy).

**Real-world examples.** `OrderedDict` vs `dict` (mostly LSP-compatible since
3.7). NumPy's `np.matrix` vs `np.ndarray` operator overloads (deprecated for
this reason).

**References.** Liskov & Wing, "A Behavioral Notion of Subtyping," ACM TOPLAS
16(6), 1994. Martin, _Clean Architecture_, 2017, ch. 9 (LSP).

---

## dead-code-tolerance

**Symptom.** Functions, classes, branches, files that nothing calls. Imports
that aren't used. Configuration knobs whose code paths were removed. The
codebase carries weight that contributes nothing.

**Why it hurts.** Readers spend time understanding code that never runs.
Refactors are slowed by fear ("does anything use this?"). Dead code rots —
security patches don't get applied, dependencies drift.

**Bad.** A 200-line `legacy_calculator.py` that no test imports and no
production caller references, with TODO comments dated 2019.

**Fixed.** Delete it. Git remembers. If you ever need it back:
`git log --all -- legacy_calculator.py`.

**Type-safety / static-analysis notes.**

- ruff `F401` — unused import.
- ruff `F841` — unused variable.
- ruff `ARG` rules — unused function arguments.
- `vulture` — unused functions/classes/methods (heuristic; tune carefully).
- pyright `reportUnusedFunction`, `reportUnusedVariable`,
  `reportUnusedExpression`.
- coverage gaps in CI (functions never executed by tests).

**When NOT to refactor.** Code that's deliberately retained for backwards
compatibility (public API) — mark with `@deprecated` (PEP 702). Code in active
development behind a feature flag — gate the dead branches with a `Final`
sentinel.

**Real-world examples.** Most codebases over five years old contain ≥ 10% dead
code by LOC. The Linux kernel's `staging/` directory; Mozilla's `obsolete/`
markers; every codebase with a "v1" you forgot to remove.

**References.** Feathers, _Working Effectively with Legacy Code_, 2004, ch. 17.
Hunt & Thomas, _The Pragmatic Programmer_, 20th ed., 2019 — _Dead Programs Tell
No Lies_.

---

## magic-numbers-magic-strings

**Symptom.** Literals embedded in code without names. `if status == 7:`,
`range(86_400)`, `timeout=30`. The reader has to guess what the number means.

**Bad.**

```python
def is_session_expired(session: "Session") -> bool:
    return (now() - session.created).total_seconds() > 86_400

def cleanup() -> None:
    delete_old_sessions(7)  # 7 what?
```

**Fixed.** Name them with `Final` — and when the value is _configuration_
(a timeout, budget, or limit an operator would override or inspect), it
belongs in the consolidated settings tree, not in another module constant
(see [scattered-configuration](#scattered-configuration)).

```python
from typing import Final
from datetime import timedelta

SESSION_TTL: Final[timedelta] = timedelta(days=1)
SESSION_GC_BATCH_SIZE: Final[int] = 7

def is_session_expired(session: "Session") -> bool:
    return (now() - session.created) > SESSION_TTL

def cleanup() -> None:
    delete_old_sessions(SESSION_GC_BATCH_SIZE)
```

**Type-safety / static-analysis notes.** `Final` (PEP 591) tells type checkers
the value won't be reassigned. Pyright's `reportConstantRedefinition` catches
violations. ruff `PLR2004` (magic-value-comparison) flags `if x == 7:` style.
`Final[timedelta]` documents the unit at the type level.

**When NOT to refactor.** Truly self-explanatory literals: `for i in range(2):`,
`* 2` in a doubling formula. Naming `TWO = 2` is parody, not engineering.

**Real-world examples.** HTTP status codes (use `http.HTTPStatus`). Timeouts.
Retry counts. Pagination sizes. Anywhere a number appears twice — give it a name
once.

**References.** Beck, _Implementation Patterns_, 2008, ch. 8 ("Number"). Fowler,
_Refactoring_, 2nd ed., 2018, ch. 9 — _Replace Magic Number with Symbolic
Constant_.

---

## scattered-configuration

**Symptom.** Configuration values — timeouts, retry budgets, limits, URLs,
thresholds — spread across per-module `Final` constants, re-stated
signature defaults, and direct `os.environ` reads. The same default literal
appears in a config field _and_ a function signature, or the same
pattern/limit constant lives in two modules. Changing behavior requires
finding every copy.

**Why it hurts.** A default with two owners has already drifted: callers
that omit the parameter silently diverge from configured ones, and no test
can notice the split. Operators cannot override or inspect what is
scattered, and each new module re-decides values that were decided once.

**Bad.**

```python
# config.py
DEFAULT_REGION: Final[str] = "us-east-1"
# presets.py — the preset re-hardcodes the field's default
region: str = "us-east-1",
# keys.py — config.key_log_prefix_segments has its own 2
def render_key(..., prefix_segments: int = 2): ...
```

**Fixed.** One consolidated settings tree — pydantic `BaseSettings` for a
service, or a frozen `BaseModel` config object the consumer nests when a
reusable library must not own the env namespace. Signatures read from it;
they never re-state its values. Module `Final` constants remain only for
true program constants no operator would vary.

```python
from pydantic import BaseModel, ConfigDict


class StorageSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str = "us-east-1"
    key_log_prefix_segments: int = 2


def render_key(settings: StorageSettings, raw: str) -> str:
    segments = settings.key_log_prefix_segments  # one owner, one default
    ...
```

**Type-safety / static-analysis notes.** `frozen=True` makes configuration
immutable after load; `validate_default=True` catches bad defaults at
startup rather than in production. Review mechanics: grep for the same
literal in two files, and for signature defaults that mirror a settings
field.

**When NOT to refactor.** True program constants (protocol codes, byte
math, a regex used in one place) stay `Final` — not every named number is
configuration. Deliberate defaults are fine; _duplicated_ defaults are the
smell.

**Real-world examples.** openai-python consolidates every tunable onto
typed config objects instead of scattering defaults across call sites.
Twelve-Factor config-in-the-environment only works when one loader owns
the mapping.

**References.** `python:pydantic` § Settings (this marketplace) — settings
consolidation and the migration move from scattered constants.

---

## comments-as-apology

**Symptom.** Comments that explain _what the code does_ because the code is
unclear. Comments masking unclear naming. Comments that cite a ticket but not
the reasoning. Comments left over from previous refactors that no longer match
the code. (Martin, _Clean Code_, 2008, ch. 4 — "Comments do not make up for bad
code.")

**Bad.**

```python
def calc(x: list[int]) -> int:
    # iterate over the list, sum the elements that are even,
    # multiply by 2, and return
    s = 0
    for v in x:
        if v % 2 == 0:
            s += v
    return s * 2

# TODO(2019-04-12): figure out why retries fail on Tuesdays
def maybe_retry(): ...
```

**Fixed.** Make the code say what the comment said.

```python
def double_sum_of_even_numbers(values: list[int]) -> int:
    return 2 * sum(v for v in values if v % 2 == 0)
```

**Comments that _are_ worth writing.**

- _Why_, not _what_: the design choice or business constraint that's not in the
  code.
- Performance trade-offs: "this is O(n²) but n ≤ 10; switching to a heap costs
  more than it saves."
- Workarounds with a citation: "Workaround for psycopg2#1234 — remove when 2.10
  is on PyPI."

**Type-safety / static-analysis notes.** ruff has no rule for "explain why" —
the discipline is review-based. ruff `FIX002` flags TODO comments without
assignees; `FIX003` flags `XXX`. Use them to drive cleanup.

**When NOT to refactor.** Public APIs _need_ docstrings — those are not "apology
comments." Distinguish: the docstring is a contract, the comment-as-apology is
debt.

**Real-world examples.** Codebases with `# This is hacky but works` over a
`re.sub` that strips invisible characters. The `XXX HACK FIXME` triad in any
non-trivial codebase.

**References.** Martin, _Clean Code_, Pearson, 2008, ch. 4 — _Comments_. Hunt &
Thomas, _The Pragmatic Programmer_, 20th ed., 2019. Beck, _Implementation
Patterns_, 2008, ch. 4.

---

## type-erosion

**Symptom.** `Any` creeping into a once-typed codebase. `cast(...)` everywhere.
Public APIs with no annotations. `# type: ignore` without a code or a comment.
`dict[str, object]` carrying structured data that _could_ be a `TypedDict`.

**Why it hurts.** The type system stops catching bugs. Refactors that should
ripple become silent. New developers cannot reason about the code; tooling
cannot help them.

**Bad.**

```python
from typing import Any, cast

def fetch_user(uid: Any) -> Any:
    raw = http_get(f"/users/{uid}")  # returns dict[str, object]
    return cast(Any, raw)

def display(user: Any) -> str:
    return user["name"] + " <" + user["email"] + ">"  # any typo silently passes
```

**Fixed.**

```python
from typing import NewType

from pydantic import BaseModel, ConfigDict

UserId = NewType("UserId", str)


class UserPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    email: str


def fetch_user(uid: UserId) -> UserPayload:
    raw = http_get(f"/users/{uid}")  # returns dict[str, object]
    # Parse at the boundary: never trust what the network returns.
    # A declared schema — not a hand-rolled isinstance chain per field.
    return UserPayload.model_validate(raw)  # raises naming the field


def display(user: UserPayload) -> str:
    return f"{user.name} <{user.email}>"
```

**Type-safety / static-analysis notes.**

- mypy: `--strict` (= `disallow_untyped_defs`, `disallow_any_explicit`,
  `disallow_any_generics`, `warn_return_any`, …). Use `mypy --strict` in CI.
- pyright: `--strict` mode; `reportGeneralTypeIssues`,
  `reportUnknownArgumentType`, `reportUnknownVariableType`.
- ruff: `ANN` family (`ANN001`–`ANN401`); `ANN401` flags explicit `Any`.
- `# type: ignore[code]` requires a specific code; bare `# type: ignore` is
  itself an anti-pattern (mypy `--show-error-codes` + `unused-ignore` flags
  drift).

**When NOT to refactor.** Genuine generic plumbing where the value type really
is arbitrary (e.g., a serializer's "any JSON-encodable object" — model with a
precise recursive type, not `Any`).

**Real-world examples.** Codebases that adopted type hints in 2018 and never
tightened them. Heavy `kwargs: Any` usage in CLI wrappers. Pre-PEP 589
(TypedDict) patterns where JSON shapes were typed as `dict[str, Any]`.

**References.** PEP 484, "Type Hints," 2014. PEP 589, "TypedDict," 2019. PEP
591, "Adding a final qualifier to typing," 2019. PEP 698, "Override
decorator," 2022. _mypy docs_, "Strict mode,"
<https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict>.

---

## hand-rolled-boundary-coercion

**Symptom.** A family of private helpers — `_as_str`, `_as_int(value,
default)`, `_as_optional_int`, `_as_mapping` — narrowing `object`-typed
payload fields with `isinstance` checks, including the
`isinstance(x, int) and not isinstance(x, bool)` dance. Call sites grow
`or ""` / `or 0` fallbacks and sentinel defaults (`_EPOCH` for a missing
date). Often defended by a module docstring: "responses are narrowed, not
trusted."

**Why it hurts.** Each helper re-derives strictness, defaults, and error
paths by hand, and the edges leak: a missing value becomes a fabricated
`""`, `0`, or sentinel indistinguishable from real data, so the failure
mode is silent corruption instead of a validation error. The family grows
one helper at a time until the module owns a private, untested validation
library.

**Bad.**

```python
def _as_int(value: object, default: int = 0) -> int:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool)
        else default
    )


size = _as_int(response.get("ContentLength"))  # missing → fabricated 0
etag = ETag(_as_str(response.get("ETag")) or "")  # missing → fake empty ETag
```

**Fixed.** Parse untrusted payloads with a declared boundary schema — a
pydantic `TypeAdapter` or a small response `BaseModel`. Strictness is
chosen once, bool-for-int is rejected, absence is modeled as `T | None`
instead of fabricated, and malformed payloads raise instead of corrupting.
Use a `TypeIs` predicate when the goal is only to narrow for the checker —
a predicate, never a coercer.

```python
from pydantic import BaseModel, ConfigDict


class HeadObjectResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content_length: int
    etag: str | None = None  # absence is modeled, never fabricated


head = HeadObjectResponse.model_validate(response)  # errors name the field
```

**Type-safety / static-analysis notes.** No checker flags the helper
bodies — their danger is silence, not untypedness. Review triggers: three
or more `_as_*` / `_coerce_*` isinstance helpers in one module; the
bool-exclusion dance (a hand-built validator by definition); `or ""` /
`or 0` on payload reads; a docstring arguing the pattern — adjudicate the
claim, don't defer to it.

**When NOT to refactor.** One or two genuine predicates with domain
semantics (not shape coercion) are fine — as `TypeIs`. Trusted internal
data that is already typed needs no boundary parse; do not re-validate
your own constructors.

**Real-world examples.** SDK response handling written before the project
adopted pydantic. The docstring-defense pattern is common and the argument
is usually correct — narrowing untrusted responses matters — while the
conclusion (hand-roll it per field) is what fails.

**References.** `python:pydantic` § TypeAdapter and `python:typings`
§ Traps Reviewers Should Catch (this marketplace). PEP 742, "TypeIs,"
2024.

---

## mutable-default-arguments

**Symptom.** A function default that's a mutable object. Python evaluates
defaults _once_ at function-definition time; mutations persist across calls.

**Bad.**

```python
def append_item(item: int, target: list[int] = []) -> list[int]:
    target.append(item)
    return target

print(append_item(1))   # [1]
print(append_item(2))   # [1, 2]   <-- surprise!
print(append_item(3))   # [1, 2, 3] <-- the same list
```

**Fixed.** Use `None` as the sentinel; create the mutable inside the function.

```python
def append_item(item: int, target: list[int] | None = None) -> list[int]:
    if target is None:
        target = []
    target.append(item)
    return target
```

For dataclasses, use `field(default_factory=list)`:

```python
from dataclasses import dataclass, field

@dataclass(slots=True)
class Cart:
    items: list[str] = field(default_factory=list)
```

**Type-safety / static-analysis notes.**

- ruff `B006` — _do not use mutable data structures for argument defaults_.
- pyright `reportCallInDefaultInitializer` flags some related patterns.
- The `@dataclass` decorator raises at class-definition time if you try
  `items: list[str] = []` directly.

**When NOT to refactor.** Never. The behavior is a bug 99% of the time. The 1%
(memoizing a default cache) is better expressed with `functools.lru_cache` or a
`Final` module-level constant.

**Real-world examples.** This is item #1 on the "Python gotchas" lists for a
reason. Every new Python developer runs into it.

**References.** _Python docs_, "More on Defining Functions" — note 4.7.1.
<https://docs.python.org/3/tutorial/controlflow.html#default-argument-values>.
Beazley, _Python Cookbook_, 3rd ed., O'Reilly, 2013, ch. 7.

---

## review-checklist

When reading a diff, scan for these in order:

1. **Scope** — does one change touch many unrelated files? (Shotgun Surgery)
2. **Types** — are domain concepts passed as primitives or strings? (Primitive
   Obsession, Stringly-Typed)
3. **Behavior location** — is logic on the data that owns the invariant, or in a
   service reaching in? (Anemic Model, Feature Envy)
4. **Errors** — is every process boundary wrapped? Is any exception silently
   swallowed? (Happy-Path-Only, Exception Swallowing)
5. **Tests** — do they exercise real code, or assert against mock setups?
   (Over-Mocking)
6. **Abstractions** — does each Protocol / base class have at least two real
   implementations, or a clearly imminent second one? (Premature Abstraction,
   Speculative Generality)
7. **Dependencies** — do imports go one direction? Any cycles? Any modules that
   know too much about infrastructure? (Big Ball of Mud, Circular Imports, Leaky
   Abstractions)
8. **Type discipline** — any `Any`, bare `cast`, `# type: ignore` without a
   code? (Type Erosion)
9. **Boundaries** — are untrusted payloads parsed by a declared schema, or
   narrowed by hand-rolled isinstance coercion helpers with fabricated
   fallbacks? (Hand-Rolled Boundary Coercion)
10. **Defaults** — any mutable defaults? (Mutable Default Arguments)
11. **Constants** — any magic numbers without `Final`, configuration
    scattered across module constants, or the same default re-stated in a
    signature and a config field? (Magic Numbers / Strings, Scattered
    Configuration)

If a single diff triggers three or more of these, reject and ask for a smaller,
more focused change.

---

## references

**Books.**

- Fowler, Martin. _Refactoring: Improving the Design of Existing Code_, 2nd ed.
  Addison-Wesley, 2018. ch. 3 ("Bad Smells in Code"), ch. 7–24 (refactorings).
- Martin, Robert C. _Clean Code: A Handbook of Agile Software Craftsmanship_.
  Pearson, 2008. ch. 3, ch. 4, ch. 7, ch. 17.
- Martin, Robert C. _Clean Architecture: A Craftsman's Guide to Software
  Structure and Design_. Pearson, 2017. ch. 9, ch. 10.
- Feathers, Michael. _Working Effectively with Legacy Code_. Prentice
  Hall, 2004. ch. 17, ch. 21.
- Beck, Kent. _Implementation Patterns_. Addison-Wesley, 2008. ch. 4–8.
- Evans, Eric. _Domain-Driven Design: Tackling Complexity in the Heart of
  Software_. Addison-Wesley, 2003. ch. 5.
- Vernon, Vaughn. _Implementing Domain-Driven Design_. Addison-Wesley, 2013. ch.
  6, ch. 12.
- Khononov, Vlad. _Learning Domain-Driven Design_. O'Reilly, 2021. ch. 6.
- Hunt, Andrew, and David Thomas. _The Pragmatic Programmer_, 20th anniversary
  ed. Addison-Wesley, 2019.
- Riel, Arthur. _Object-Oriented Design Heuristics_. Addison-Wesley, 1996.
  ch. 3.
- Meszaros, Gerard. _xUnit Test Patterns: Refactoring Test Code_.
  Addison-Wesley, 2007. ch. 11.
- Freeman, Steve, and Nat Pryce. _Growing Object-Oriented Software, Guided by
  Tests_. Addison-Wesley, 2009.
- Nygard, Michael. _Release It! Design and Deploy Production-Ready Software_,
  2nd ed. Pragmatic Bookshelf, 2018. ch. 4.
- Beazley & Jones. _Python Cookbook_, 3rd ed. O'Reilly, 2013. ch. 7, ch. 14.

**Web sources.**

- Fowler, Martin. "AnemicDomainModel," 2003,
  <https://martinfowler.com/bliki/AnemicDomainModel.html>.
- Fowler, Martin. "Mocks Aren't Stubs,"
  <https://martinfowler.com/articles/mocksArentStubs.html>.
- Foote, Brian, and Joseph Yoder. "Big Ball of Mud," PLoP 1997,
  <http://www.laputan.org/mud/>.
- Spolsky, Joel. "The Law of Leaky Abstractions," 2002,
  <https://www.joelonsoftware.com/2002/11/11/the-law-of-leaky-abstractions/>.
- Liskov, Barbara, and Jeannette Wing. "A Behavioral Notion of Subtyping." _ACM
  TOPLAS_ 16(6), 1994.
- Bandit, "B110: try_except_pass,"
  <https://bandit.readthedocs.io/en/latest/plugins/b110_try_except_pass.html>.

**PEPs.**

- PEP 484, "Type Hints," 2014.
- PEP 586, "Literal Types," 2019.
- PEP 589, "TypedDict," 2019.
- PEP 591, "Final Qualifier," 2019.
- PEP 663, "StrEnum," 2021.
- PEP 673, "Self Type," 2022.
- PEP 698, "Override Decorator," 2022.
- PEP 702, "Marking deprecations using the type system," 2023.
