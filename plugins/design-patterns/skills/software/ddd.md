# Domain-Driven Design Patterns

Patterns from Eric Evans's _Domain-Driven Design_ (the "blue book") and Vaughn
Vernon's _Implementing Domain-Driven Design_ (the "red book"), translated to
strictly-typed Python 3.13+. The point of DDD is not the patterns. The point is
_aligning the model with the language of the business_ — the patterns are the
structural moves that follow from that alignment. If you adopt the patterns
without the language work, you have ceremony.

The single thread through every pattern below: **encode invariants in types, not
in services.** Anemic dataclasses with `*Service` mutators are the standard
failure mode and are explicitly out of bounds — Wlaschin's "make illegal states
unrepresentable" applies in full force.

## How to use this file

Read [Tactical patterns](#tactical-patterns) before any non-trivial domain
modeling. Read [Strategic patterns](#strategic-patterns) when designing system
_boundaries_ — between services, between modules, between teams. Most defects in
long-lived domain code come from ignoring strategic decisions and re-deriving
the same wrong boundary repeatedly.

Each entry follows a fixed shape:

1. **Intent** — what it solves.
2. **When to reach for it** — the trigger.
3. **Sketch** — strict-typed Python 3.13+. Strategic patterns may sketch in
   prose where code would be misleading.
4. **Type-safety notes** — what the checker enforces.
5. **When NOT to use** — overkill threshold.
6. **Real-world examples** — named systems / cases.
7. **Anti-pattern variant** — the common misuse.
8. **References** — book + chapter.

Conventions (non-negotiable):

- `Protocol` over `ABC`; PEP 695 generics (`class Foo[T]:`); PEP 604 unions
  (`X | Y`).
- `Self`, `Final`, `@override`. No `Any`. Use the annotation-evaluation policy
  in `SKILL.md` conventions; the `python:typings` sister skill has the full
  canonical reference if it is also loaded.
- Every Python block is written to target `mypy --strict` and
  `pyright --strict`.

---

# Tactical patterns

## Entity

**Intent.** A domain object whose identity persists over time independent of its
attribute values. Two `Customer` instances with identical names and emails are
still _different customers_ if their ids differ. Entities are tracked across
operations by id, not by value.

**When to reach for it.**

- The thing has a _lifecycle_ — creation, mutation, lookup, retirement.
- Two instances with identical state must remain distinguishable (same name,
  different customers).
- The thing has _behaviors_ that change its own state (an order can be
  `place()`d).

**Sketch.**

```python
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NewType, Self
from uuid import UUID, uuid4

CustomerId = NewType("CustomerId", UUID)

@dataclass
class Customer:
    """Entity. Identity = id. Equality = id, not field-by-field."""
    id: CustomerId
    email: Email                          # value object — see next section
    full_name: str
    registered_at: datetime
    _events: list["DomainEvent"] = field(default_factory=list, repr=False)

    @classmethod
    def register(cls, email: Email, full_name: str) -> Self:
        new_id = CustomerId(uuid4())
        now = datetime.now(UTC)
        instance = cls(id=new_id, email=email, full_name=full_name, registered_at=now)
        instance._events.append(CustomerRegistered(
            event_id=uuid4(), occurred_at=now, customer_id=new_id, email=email,
        ))
        return instance

    def change_email(self, new_email: Email) -> None:
        if new_email == self.email:
            return                  # idempotent
        old, self.email = self.email, new_email
        self._events.append(EmailChanged(
            event_id=uuid4(), occurred_at=datetime.now(UTC),
            customer_id=self.id, old=old, new=new_email,
        ))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Customer) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def pull_events(self) -> list["DomainEvent"]:
        events, self._events = self._events, []
        return events
```

`__eq__` / `__hash__` are by id, not by all fields — the defining trait of an
entity and the inverse of [Value Object](#value-object).

**Type-safety notes.**

- `NewType("CustomerId", UUID)` makes `def deactivate(id: CustomerId)`
  un-callable with a `BillingAccountId` even though both are UUIDs underneath.
- `_events` is private: external code cannot mutate; command methods append;
  `pull_events()` is the explicit drain.
- `change_email` is a _command method_, not a setter. The rule ("no-op if
  unchanged") and the event emission live together; there is no public setter
  that bypasses them.

**When NOT to use.**

- The thing has no lifecycle and no identity beyond its values — that's a value
  object.
- The thing is a transient computation result. Don't model derived totals,
  projections, or query results as entities; they're DTOs.

**Real-world examples.**

- A `User`, `Order`, `Product`, `Account` — anything stored in a database keyed
  by an id.
- Stripe API resources with stable `obj_xxxxx` ids — Customer, Subscription,
  Invoice.
- File-system inodes — same file content under two paths is still two files
  (different inodes); same inode under two names is one file.

**Anti-pattern variant.** The "anemic entity" — fields plus public setters,
behavior elsewhere.

```python
@dataclass
class Customer:
    id: UUID
    email: str           # public, mutable, unvalidated

class CustomerService:
    def change_email(self, customer: Customer, new_email: str) -> None:
        if "@" not in new_email:
            raise ValueError(...)
        customer.email = new_email
        self._publish(EmailChanged(...))
```

The rule "email must be valid" lives outside the type. Any caller that mutates
`customer.email` directly bypasses the validation and the event. Move the rule
onto the entity (or onto the `Email` value object) and the bypass becomes
impossible.

**References.**

- Evans, _Domain-Driven Design_, ch. 5, "A Model Expressed in Software," section
  "Entities."
- Vernon, _Implementing Domain-Driven Design_, ch. 5, "Entities."

---

## Value Object

**Intent.** A domain object defined entirely by its attributes; two instances
with equal fields are equal, period. No identity. Always immutable.

**When to reach for it.**

- A measurement, an amount, a coordinate, an address, a date range, a color, a
  coupon code, an email, a phone number — anything where "what it is" is "all of
  its fields."
- Encoding domain rules into a type so they can't be violated downstream
  (`Money` enforces same-currency addition; `Email` enforces format).

**Sketch.**

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Money:
    amount_cents: int
    currency: str

    def __post_init__(self) -> None:
        if self.amount_cents < 0:
            raise ValueError(f"money cannot be negative: {self.amount_cents}")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError(f"currency must be a 3-letter ISO code: {self.currency!r}")

    def add(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError(f"cannot add {self.currency} and {other.currency}")
        return Money(amount_cents=self.amount_cents + other.amount_cents, currency=self.currency)

    def scale(self, factor: int) -> "Money":
        return Money(amount_cents=self.amount_cents * factor, currency=self.currency)

@dataclass(frozen=True, slots=True)
class DateRange:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"end {self.end} before start {self.start}")

    def overlaps(self, other: "DateRange") -> bool:
        return self.start <= other.end and other.start <= self.end
```

Two `Money(amount_cents=1000, currency="USD")` are _the same value_.
`frozen=True` dataclasses give field-by-field `__eq__` and a deterministic
`__hash__` for free.

**Type-safety notes.**

- `frozen=True, slots=True` together: immutable, fast, hashable.
- `__post_init__` is the smart-constructor gate. Once a `Money` exists, its
  invariants hold. Downstream code never has to recheck.
- Operations that _change_ a value return a _new_ value (`add`, `scale`). They
  never mutate. This is what lets two threads share a `Money` safely.
- Avoid mutable fields inside a frozen value object. `items: list[X]` defeats
  the freeze; use `tuple[X, ...]`.

**When NOT to use.**

- The thing has identity that survives all field changes (a customer, an order).
  That's an entity.
- The thing is a transient bag of fields used once at a request boundary. A
  dataclass is fine; you don't need invariants.

**Real-world examples.**

- `Money`, `Email`, `IBAN`, `PhoneNumber`, `Address`, `Coordinate`, `DateRange`,
  `Percentage`.
- The Python `datetime`, `Decimal`, `pathlib.Path` — value objects in the
  standard library.
- The Java `java.time.LocalDate`, `java.math.BigDecimal` — same idea.

**Anti-pattern variant.**

```python
# Stringly-typed primitive obsession.
def transfer(from_account: str, to_account: str, amount: float, currency: str) -> None: ...
```

`amount: float` for money is a defect (binary floating point + decimals).
`currency: str` can be `"usd"`, `"USD"`, or `"$"`. Replace with `Money` and
`AccountId` value objects; the function signature now refuses every wrong call.

**References.**

- Evans, _Domain-Driven Design_, ch. 5, "Value Objects."
- Vernon, _Implementing Domain-Driven Design_, ch. 6, "Value Objects."
- Wlaschin, _Domain Modeling Made Functional_, ch. 6, "Integrity and Consistency
  in the Domain."

---

## Aggregate Root

**Intent.** A _consistency boundary_. An aggregate is a cluster of entities and
value objects treated as one unit for changes; the aggregate root is the single
entity through which all changes happen. The root enforces invariants that span
the cluster; outside callers cannot reach into the interior to mutate it.

**When to reach for it.**

- Multiple objects must obey a _joint_ rule
  (`Order.total <= Customer.credit_limit`, `Cart.line_count <= 50`).
- Concurrent updates to interior objects would race (two threads modifying
  different `LineItem`s of the same `Order`).
- Persistence wants a clear "save this thing" boundary.

**Sketch.**

```python
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NewType, Self
from uuid import UUID, uuid4

OrderId = NewType("OrderId", UUID)
LineItemId = NewType("LineItemId", UUID)

@dataclass(frozen=True, slots=True)
class LineItem:
    """Value object inside the Order aggregate. No identity outside the order."""
    id: LineItemId
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"quantity must be positive: {self.quantity}")

    def line_total(self) -> Money:
        return self.unit_price.scale(self.quantity)

@dataclass
class Order:
    """Aggregate root.

    Invariants enforced inside this class:
    * total never exceeds the customer's credit limit (set at construction)
    * once placed, items cannot change
    * cancellation is idempotent and only valid before fulfilment
    """
    _id: OrderId
    _customer_id: CustomerId
    _credit_limit: Money
    _items: list[LineItem] = field(default_factory=list)
    _status: Literal["draft", "placed", "fulfilled", "cancelled"] = "draft"
    _placed_at: datetime | None = None
    _events: list["DomainEvent"] = field(default_factory=list, repr=False)

    @classmethod
    def new(cls, customer_id: CustomerId, credit_limit: Money) -> Self:
        return cls(_id=OrderId(uuid4()), _customer_id=customer_id, _credit_limit=credit_limit)

    @property
    def id(self) -> OrderId:
        return self._id

    @property
    def status(self) -> str:
        return self._status

    @property
    def items(self) -> Sequence[LineItem]:
        # Sequence, not list, so callers cannot append/remove from outside.
        return tuple(self._items)

    def add_item(self, sku: str, quantity: int, unit_price: Money) -> None:
        if self._status != "draft":
            raise OrderAlreadyPlaced(self._id)
        new_item = LineItem(id=LineItemId(uuid4()), sku=sku, quantity=quantity, unit_price=unit_price)
        proposed_total = self._total_with(new_item)
        if proposed_total.amount_cents > self._credit_limit.amount_cents:
            raise CreditLimitExceeded(self._id, proposed=proposed_total, limit=self._credit_limit)
        self._items.append(new_item)

    def place(self) -> None:
        if self._status != "draft":
            raise OrderAlreadyPlaced(self._id)
        if not self._items:
            raise EmptyOrder(self._id)
        now = datetime.now(UTC)
        self._status = "placed"
        self._placed_at = now
        self._events.append(OrderPlaced(
            event_id=uuid4(), occurred_at=now,
            order_id=self._id, customer_id=self._customer_id, total=self.total(),
        ))

    def cancel(self, reason: str) -> None:
        if self._status == "cancelled":
            return        # idempotent
        if self._status == "fulfilled":
            raise OrderAlreadyFulfilled(self._id)
        self._status = "cancelled"
        self._events.append(OrderCancelled(
            event_id=uuid4(), occurred_at=datetime.now(UTC),
            order_id=self._id, reason=reason,
        ))

    def total(self) -> Money:
        if not self._items:
            return Money(amount_cents=0, currency=self._credit_limit.currency)
        first = self._items[0].line_total()
        return _sum_money([item.line_total() for item in self._items[1:]], start=first)

    def _total_with(self, extra: LineItem) -> Money:
        return self.total().add(extra.line_total())

    def pull_events(self) -> list["DomainEvent"]:
        events, self._events = self._events, []
        return events
```

`Order` is the aggregate root. `LineItem` is a value object inside the aggregate
— no repository, no separate identity in any context outside of `Order`. Outside
callers see `order.items` as a `Sequence[LineItem]` (immutable view), not as the
internal `list`.

**Key rules.**

- **One repository per aggregate root.** `OrderRepository`, never
  `LineItemRepository`. The repository's job is to load/save the _whole_
  aggregate.
- **Reference between aggregates by id, not by direct reference.** An `Order`
  holds a `CustomerId`, never a `Customer`. This keeps the consistency boundary
  tight: changing a customer doesn't cascade-load the order graph.
- **One transaction = one aggregate.** A use case that modifies `Order` _and_
  `Customer` in the same DB transaction is a smell — you've made `Customer` part
  of the consistency boundary, which probably means they should be one
  aggregate.

**Type-safety notes.**

- Private fields with leading underscore + `Sequence`-typed read-only views.
  Pyright/mypy cannot prevent reaching into `_items` from outside, but
  `mypy --strict` will flag external access to underscored attributes if you
  enable it (`disallow_protected_access`).
- Status modeled with `Literal[...]`. A bug like `self._status = "placd"` (typo)
  is caught at type-check time.
- Domain exceptions (`OrderAlreadyPlaced`, `CreditLimitExceeded`) are
  domain-meaningful, not generic `ValueError`.

**When NOT to use.**

- The "aggregate" has one entity inside it. That entity _is_ the aggregate;
  calling it "Aggregate" adds a noun without adding structure.
- Truly independent objects forced into one aggregate "for convenience." If
  `Order.cancel()` doesn't actually need to look at `Customer`, they're separate
  aggregates.

**Real-world examples.**

- A shopping `Cart` with `LineItem`s (cart is the root).
- A `Document` with `Section`s and `Paragraph`s (document is the root).
- Stripe `Invoice` with `LineItem`s — the invoice is the aggregate; line items
  don't have a standalone API.

**Anti-pattern variant.** The "aggregate root in name only" — the public API
exposes the internal collections mutably, so callers bypass the invariants:

```python
class Order:
    items: list[LineItem] = []           # public mutable list

# Caller mutates internal state directly, bypassing add_item:
order.items.append(LineItem(...))         # invariant check skipped
```

If the rules live in `add_item` but anyone can append directly, the rules don't
exist. Underscore-private the field and expose a `Sequence` view.

**References.**

- Evans, _Domain-Driven Design_, ch. 6, "The Life Cycle of a Domain Object,"
  section "Aggregates."
- Vernon, "Effective Aggregate Design" (three-part essay; reproduced in
  _Implementing Domain-Driven Design_, ch. 10).
- Vernon, _Implementing Domain-Driven Design_, ch. 10, "Aggregates."

---

## Domain Service

**Intent.** A piece of domain logic that doesn't belong to any one entity or
value object — typically because it operates on _several_ aggregates or
expresses a _transformation_ with no natural home on a single object.

**When to reach for it.**

- The operation involves two or more aggregates
  (`transfer(from_account, to_account, amount)`).
- The operation is conceptually a _verb in the domain language_ but is not the
  responsibility of any single entity.
- Adding the operation to one entity would require it to know too much about
  another.

**Sketch.**

```python
from typing import Protocol

class FxRateProvider(Protocol):
    def rate(self, from_currency: str, to_currency: str, on: date) -> float: ...

class TransferService:
    """Domain service: moves money between two accounts.

    Lives in the domain layer (no infra), but is a service because the operation
    isn't naturally `from_account.transfer(...)` — it touches two aggregates
    equally.
    """
    def __init__(self, fx: FxRateProvider) -> None:
        self._fx = fx

    def transfer(self, from_acc: Account, to_acc: Account, amount: Money, on: date) -> None:
        if from_acc.id == to_acc.id:
            raise SelfTransferNotAllowed(from_acc.id)
        if from_acc.currency != amount.currency:
            raise CurrencyMismatch(from_acc.currency, amount.currency)
        from_acc.debit(amount)
        if to_acc.currency == amount.currency:
            to_acc.credit(amount)
        else:
            rate = self._fx.rate(amount.currency, to_acc.currency, on)
            converted = Money(amount_cents=int(amount.amount_cents * rate), currency=to_acc.currency)
            to_acc.credit(converted)
```

The service mutates two aggregates in concert. `from_acc.debit` and
`to_acc.credit` are command methods on the entities themselves; the _service_
coordinates the order and the cross-account rules.

**Type-safety notes.**

- The service depends on a `Protocol` (`FxRateProvider`), not a concrete class.
  Tests inject a fake; production injects a real adapter.
- The service is _stateless_ between calls — the state lives on the aggregates
  it touches. A "service" with mutable instance state is a smell; that state
  probably belongs on an entity.

**When NOT to use.**

- The operation has a clear home on one entity. `Order.cancel()` is a method on
  `Order`, not `OrderCancellationService`.
- The operation is pure I/O orchestration (HTTP request/response wiring with no
  domain rules). That's an _application service_, not a _domain service_.
  Different layer.

**Real-world examples.**

- A `PricingService` that computes a quote across catalog rules, tax rules, and
  customer contracts.
- A `RoutingService` that picks a fulfillment center given inventory and
  shipping rules.
- A `ScoringService` for a credit decision that looks at multiple aggregates.

**Anti-pattern variant.** Naming everything `*Service`. A two-line helper called
`EmailNormalizationService` is just a function that should live as a method on
`Email` or as a module-level function in the domain.

**References.**

- Evans, _Domain-Driven Design_, ch. 5, "Services."
- Vernon, _Implementing Domain-Driven Design_, ch. 7, "Services."

---

## Repository

**Intent.** Abstract persistence behind a collection-like interface. Callers
think "give me the order with this id" or "save this order," not "issue this
SQL." The repository's job is to load and save _whole aggregates_ — never half
an aggregate, never multiple aggregates per call.

**When to reach for it.**

- You have business logic above the persistence layer that should be tested
  without a DB.
- You want to delay the choice of persistence technology, or support multiple
  backends.
- Domain entities should not depend on ORM types.

**Sketch.**

```python
from collections.abc import Sequence
from typing import Protocol

class Repository[TAggregate, TId](Protocol):
    """One repository per aggregate root."""
    def get(self, aggregate_id: TId) -> TAggregate | None: ...
    def add(self, aggregate: TAggregate) -> None: ...
    def remove(self, aggregate: TAggregate) -> None: ...

class OrderRepository(Repository[Order, OrderId], Protocol):
    """Domain-specific extension. Domain queries live here."""
    def find_open_for_customer(self, customer_id: CustomerId) -> Sequence[Order]: ...

# Concrete adapter — returns DOMAIN entities, not ORM rows.
class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, aggregate_id: OrderId) -> Order | None:
        row = self._session.get(OrderRow, aggregate_id)
        return _to_domain(row) if row is not None else None

    def find_open_for_customer(self, customer_id: CustomerId) -> Sequence[Order]:
        stmt = (
            select(OrderRow)
            .where(OrderRow.customer_id == customer_id)
            .where(OrderRow.status.in_(("draft", "placed")))
        )
        return [_to_domain(r) for r in self._session.execute(stmt).scalars()]

    def add(self, aggregate: Order) -> None:
        self._session.add(_to_row(aggregate))

    def remove(self, aggregate: Order) -> None:
        row = self._session.get(OrderRow, aggregate.id)
        if row is not None:
            self._session.delete(row)
```

**Key rules.**

- **One repository per aggregate root.** Not per table. `Order` has its own
  repo; `LineItem` does not, because `LineItem` is interior to the `Order`
  aggregate.
- **Repositories return domain entities and raise domain exceptions.** Catch
  `IntegrityError` inside the adapter and translate to `DuplicateOrder`,
  `OrderNotFound`, etc. Leaking ORM types up the stack negates the abstraction.
- **Repositories don't commit.** That's the [Unit of Work](#repository)'s job
  (see `enterprise-patterns.md` for UoW). Repositories _stage_ changes.
- **Cross-aggregate queries belong elsewhere.** A query that joins `Order` and
  `Customer` and returns a denormalized projection is a Query Object or a CQRS
  read-model, not a repository method.

**Type-safety notes.**

- `Repository[TAggregate, TId]` is a `Protocol` parameterized via PEP 695
  generics — no `Generic[T]` ceremony.
- Concrete repositories implement _both_ the generic
  `Repository[Order, OrderId]` interface and a domain-specific `OrderRepository`
  that adds query methods.
- `get` returns `Order | None`, not `Order`. Forcing the caller to handle "not
  found" explicitly is what the type is for.

**When NOT to use.**

- A 500-line CRUD service where every endpoint is one query and one mutation.
  Use the ORM directly. The repository abstraction adds a layer without hiding
  anything meaningful.
- You only have one persistence backend forever, the domain is thin, and tests
  can run against an in-process SQLite. The dependency-inversion benefit doesn't
  materialize.

**Real-world examples.**

- The `cosmicpython` book (Percival & Gregory) — Python repositories with
  SQLAlchemy.
- Spring Data `JpaRepository` (Java) — generic repositories with derived query
  methods.
- Django's ORM is _not_ a repository — the model class is the persistence object
  (Active Record). Django apps that want clean domain layers wrap models in
  repository facades.

**Anti-pattern variant.** "Repository per table."

```python
class OrderRepository:           # OK
    def get(self, oid): ...
class LineItemRepository:        # WRONG: LineItem is interior to Order aggregate
    def get(self, lid): ...
```

If `LineItemRepository.get()` exists, callers can mutate a line item without
going through the order — invariants like "max 50 items per order" are now
bypassable. Delete the `LineItemRepository`; the only way to a `LineItem` is
through `OrderRepository.get(...)`.

**References.**

- Evans, _Domain-Driven Design_, ch. 6, "Repositories."
- Vernon, _Implementing Domain-Driven Design_, ch. 12, "Repositories."
- Fowler, _Patterns of Enterprise Application Architecture_ — the original
  Repository pattern.
- See also `enterprise-patterns.md` in the moirae playbook for the
  persistence-mechanics view.

---

## Domain Events

**Intent.** Represent a _fact that happened_ in the domain as a first-class
value. Other parts of the system react to the event without the emitter knowing
they exist.

**When to reach for it.**

- A domain mutation that other modules or services should observe
  (`OrderPlaced`, `CustomerRegistered`, `PaymentCaptured`).
- You want to decouple "what happened" from "what to do about it."
- You need an audit trail of business-meaningful changes.

**Sketch.**

```python
@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: UUID
    occurred_at: datetime

@dataclass(frozen=True, slots=True)
class OrderPlaced(DomainEvent):
    order_id: OrderId
    customer_id: CustomerId
    total: Money

@dataclass(frozen=True, slots=True)
class OrderCancelled(DomainEvent):
    order_id: OrderId
    reason: str
```

Events are accumulated on the aggregate and drained by the use-case layer after
commit:

```python
def place_order(uow: UnitOfWork, customer_id: CustomerId, sku: str, qty: int) -> Order:
    with uow:
        customer = uow.customers.get(customer_id) or _raise_not_found(customer_id)
        order = Order.new(customer_id=customer.id, credit_limit=customer.credit_limit)
        order.add_item(sku=sku, quantity=qty, unit_price=_lookup_price(sku))
        order.place()
        uow.orders.add(order)
        uow.commit()
    # Drain AFTER commit. A handler running on rolled-back state is a defect.
    for event in order.pull_events():
        dispatcher.dispatch(event)
    return order
```

**The Outbox pattern** (see `enterprise-patterns.md`) is the correct way to
publish events across processes: write the event row in the same DB transaction
as the aggregate change, a worker drains and publishes. Without an outbox, you
have a race between "DB commit" and "publish" that eventually loses a message.

**Type-safety notes.**

- Events are `frozen=True, slots=True`. Once published, a `OrderPlaced` is
  permanent.
- Each event type is a distinct dataclass. A handler dispatches via `match` and
  gets exhaustiveness via `assert_never`.
- Event payloads are _value objects and ids_, never live entities. Don't put
  `customer: Customer` on an event — by the time the handler runs, the
  customer's state may have moved on. Put `customer_id: CustomerId` and let the
  handler load fresh state if needed.

**When NOT to use.**

- A purely-internal mutation that no one outside the aggregate cares about.
  Don't event-spam every setter.
- Trivial sync side effects in the same process that don't need replay or audit.
  A direct function call is simpler.

**Real-world examples.**

- Stripe webhook events (`charge.succeeded`, `customer.subscription.updated`)
  are domain events from Stripe's domain crossing the wire to ours.
- AWS EventBridge / SNS topics for cross-service domain events.
- The Kafka pattern: aggregates publish events to topics; consumers project them
  into read-models.

**Anti-pattern variant.** Dispatching events _before_ commit:

```python
def place_order(...):
    order.place()                       # appends OrderPlaced to events
    for event in order.pull_events():
        dispatcher.dispatch(event)      # WRONG: handlers run before the DB commit
    uow.commit()                        # the commit might fail
```

If the commit fails, handlers have already run on a state that no longer exists.
Always drain _after_ `uow.commit()` succeeds.

**References.**

- Evans, _Domain-Driven Design_, "Domain Events" (added in the 2014 epilogue /
  various Vernon writings).
- Vernon, _Implementing Domain-Driven Design_, ch. 8, "Domain Events."
- See also `enterprise-patterns.md` (moirae) for Outbox and dispatcher
  mechanics.

---

## Specification

**Intent.** Encapsulate a domain _predicate_ as a composable object. A
`Specification[T]` answers "does this T satisfy X?" for varying Xs and can be
combined (`AND`, `OR`, `NOT`) without ad-hoc lambdas at call sites.

**When to reach for it.**

- The same predicate is reused across filtering, validation, and queries.
- The predicate has a _name_ in the business language ("active customer in good
  standing").
- You want to combine simple predicates into composite ones declaratively.

**Sketch.**

```python
from dataclasses import dataclass
from typing import Protocol

class Specification[T](Protocol):
    def is_satisfied_by(self, candidate: T) -> bool: ...

@dataclass(frozen=True, slots=True)
class And[T]:
    left: Specification[T]
    right: Specification[T]
    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)

@dataclass(frozen=True, slots=True)
class Not[T]:
    inner: Specification[T]
    def is_satisfied_by(self, candidate: T) -> bool:
        return not self.inner.is_satisfied_by(candidate)

# Domain-specific specs:
@dataclass(frozen=True, slots=True)
class CustomerInGoodStanding:
    def is_satisfied_by(self, c: Customer) -> bool:
        return c.outstanding_balance.amount_cents == 0 and not c.is_suspended

@dataclass(frozen=True, slots=True)
class CustomerInTier:
    tier: str
    def is_satisfied_by(self, c: Customer) -> bool:
        return c.tier == self.tier

# Composition reads as the business rule:
eligible = And(CustomerInGoodStanding(), CustomerInTier(tier="gold"))
matches = [c for c in customers if eligible.is_satisfied_by(c)]
```

**Pragmatic take for Python.** A `Specification` is a class-shaped
`Callable[[T], bool]`. For pure in-memory predicates, a plain function is
usually enough; the specification adds ceremony for composition. **Use it when
the _name_ matters in the business language and when several call sites reuse
the predicate.** Otherwise prefer a function.

**The DB-translation trap.** A common extension is "the repository takes a
Specification and runs it as SQL." This works in toy examples but degrades fast:
the repository now needs to know how to translate every Specification to SQL,
including custom operators. **In practice, prefer a Query Object** (see
`enterprise-patterns.md`) for the SQL case and reserve Specifications for
in-memory predicate composition.

**Type-safety notes.**

- `Specification[T]` as a `Protocol` — no inheritance ceremony.
- `frozen=True` on the composite specs (`And`, `Or`, `Not`) so they're hashable
  and reusable.
- `is_satisfied_by` is a single, total method. Don't add side effects.

**When NOT to use.**

- One call site, one predicate. A function or lambda wins.
- The predicate is genuinely SQL-shaped (involves joins, indexes, aggregates).
  That's a Query Object job.

**Real-world examples.**

- Java/.NET DDD codebases use Specification heavily for repository-level rules.
- The `dry-python/classes` library uses similar shapes in Python.
- Rails-style `scope :active, -> { where(status: 'active') }` is a Specification
  under another name.

**Anti-pattern variant.** Building a full SQL translator inside `Specification`
because the abstraction promised one. The translator becomes a partial
reimplementation of the ORM. Cut losses and write Query Objects.

**References.**

- Evans & Fowler, "Specifications" white paper, 2002.
- Evans, _Domain-Driven Design_, ch. 9, "Making Implicit Concepts Explicit."
- See also `enterprise-patterns.md` (moirae) for Query Object as the
  persistence-side alternative.

---

## Factory

**Intent.** Move _complex construction logic_ off the entity and into a
dedicated factory. The factory enforces invariants at the moment of creation;
the entity then assumes construction succeeded.

**When to reach for it.**

- Construction needs information from multiple sources (database, event,
  external API).
- The "valid" set of initial states is non-trivial — a constructor with eight
  optional parameters is a smell.
- Construction varies by source (`Order.from_quote(...)` vs
  `Order.from_legacy_record(...)`).

**Sketch.**

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class OrderQuote:
    customer_id: CustomerId
    items: tuple[QuotedLine, ...]
    valid_until: datetime

class OrderFactory:
    """Constructs Order aggregates from various sources, enforcing creation rules."""
    def __init__(self, customers: CustomerRepository, pricing: PricingService) -> None:
        self._customers = customers
        self._pricing = pricing

    def from_quote(self, quote: OrderQuote, now: datetime) -> Order:
        if quote.valid_until < now:
            raise QuoteExpired(quote.valid_until)
        customer = self._customers.get(quote.customer_id)
        if customer is None:
            raise CustomerNotFound(quote.customer_id)
        order = Order.new(customer_id=customer.id, credit_limit=customer.credit_limit)
        for line in quote.items:
            unit_price = self._pricing.lookup(line.sku, customer.tier)
            order.add_item(sku=line.sku, quantity=line.quantity, unit_price=unit_price)
        return order
```

**Two flavors.**

- _Class-method factories_ (`Order.new(...)`, `Order.from_csv_row(...)`). Live
  on the aggregate. Use for simple construction with no external dependencies.
- _Standalone factory classes_ (`OrderFactory`). Used when construction needs
  injected collaborators (`CustomerRepository`, `PricingService`) that don't
  belong on the aggregate.

**Type-safety notes.**

- The factory's return type is the _aggregate root_, not a builder or a fluent
  intermediate. Callers get a fully-valid aggregate or an exception.
- The factory's dependencies are `Protocol`s, so tests inject fakes.
- A failed creation raises a domain exception; the half-constructed aggregate is
  never exposed.

**When NOT to use.**

- A two-line `__init__` is enough. `Money(amount_cents=100, currency="USD")`
  doesn't need a factory.
- The construction logic is so simple it should live on the class itself
  (`Customer.register(email)`).

**Real-world examples.**

- An `EventFromKafkaRecord` factory that parses a Kafka record into a domain
  event.
- A `UserFromOAuthClaim` factory that constructs a domain `User` from a JWT.
- An `InvoiceFromOrder` factory.

**Anti-pattern variant.** A factory that returns a partially-valid object
expecting the caller to fill in the rest:

```python
order = factory.create_skeleton(customer_id)   # invariants not yet held
order.set_items(items)                          # mutates outside the aggregate's command API
factory.finalize(order)                         # caller must remember to call this
```

That's a builder split into pieces — and the aggregate has no way to enforce
that `finalize` was called. Either return a fully-valid aggregate from one call,
or use a real Builder pattern with a single `build()` method.

**References.**

- Evans, _Domain-Driven Design_, ch. 6, "Factories."
- Vernon, _Implementing Domain-Driven Design_, ch. 11, "Factories."

---

## Module

**Intent.** A package boundary that aligns with a _concept_ in the domain
language. The module's name is a noun in that language, and the contents
implement everything about that concept and nothing else.

**When to reach for it.**

- The domain has identifiable sub-areas (billing, shipping, catalog, identity).
- Two parts of the codebase change for different reasons.
- A new contributor should be able to find "the billing rules" in one obvious
  place.

**Sketch.** A module is just a directory with an `__init__.py`. The discipline
is what's inside:

```text
src/
  shop/
    billing/                # one module = one bounded sub-domain
      __init__.py
      domain/               # entities, VOs, aggregates, domain services
      application/          # use cases / application services
      infrastructure/       # adapters: SQLAlchemy repos, HTTP clients
    catalog/
      __init__.py
      domain/
      application/
      infrastructure/
    shipping/
      __init__.py
      ...
```

**Inside one module, layered:**

- `domain/` — entities, value objects, domain services, repositories _as
  Protocols_. **Pure Python; no framework imports.**
- `application/` — use cases that orchestrate domain operations and Unit of
  Work. Imports from `domain/` only.
- `infrastructure/` — concrete repository implementations, ORM rows, HTTP
  clients. Imports from `domain/` (to implement the Protocols) and external
  libraries.

**The dependency rule between modules.** Modules depend on each other only
through _stable_ contracts (a Protocol, an event payload, a published API).
Direct imports between two modules' `domain/` packages should be rare; if
they're frequent, you're missing a shared module or the boundary is wrong.
Enforce this in CI with `import-linter` or `grimp`.

**Type-safety notes.**

- A module's public API lives in its `__init__.py` exports. Internal types are
  _not_ re-exported; if a consumer reaches
  `from shop.billing.domain.invoice_internal import _X`, the boundary is being
  violated.
- Use `__all__` to control public surface.
- Type-only cross-module dependencies (`from shop.catalog import ProductId`) are
  fine; behavioral dependencies
  (`from shop.catalog.application import update_inventory`) usually indicate the
  wrong layering.

**When NOT to use.**

- A 500-line app. One package is fine; multiple modules is premature structure.
- An app where every "module" would have one file. The split adds directories
  without adding clarity.

**Real-world examples.**

- The `cosmicpython` example app splits `shop` into `domain`, `service_layer`,
  `adapters` — one module per ubiquitous layer rather than one per business
  sub-domain. Both are valid; the choice depends on whether the domain or the
  layer is the more useful axis.
- Django apps as modules: each app should be a domain concept (`accounts`,
  `billing`, `catalog`), not a technical layer (`forms`, `models`, `views`).

**Anti-pattern variant.** Modules organized by _technical layer_ across the
whole codebase:

```text
src/
  models/      # all ORM models, mixing billing + catalog + shipping
  services/    # all services
  views/       # all endpoints
```

Now a billing change touches `models/`, `services/`, _and_ `views/`, and so does
a catalog change, and they conflict on the same files. Module by _concept_,
layer _within_ the module.

**References.**

- Evans, _Domain-Driven Design_, ch. 5, "Modules (a.k.a. Packages)."
- Vernon, _Implementing Domain-Driven Design_, ch. 9, "Modules."
- See also `architectural-patterns.md` (moirae) for layered/hexagonal/clean
  architecture enforcement.

---

# Strategic patterns

These patterns govern relationships _between_ parts of a system — between
bounded contexts, between teams, between codebases. They are about _boundaries_,
not internals.

## Bounded Context

**Intent.** A boundary within which a particular model is internally consistent
and unambiguous. The same word means different things in different contexts;
rather than fighting that, give each context its own model with its own
vocabulary.

**When to reach for it.**

- The same noun (`Customer`, `Product`, `Order`) means materially different
  things in different parts of the business — billing's `Customer` has a credit
  limit; marketing's `Customer` has lifetime value; support's `Customer` has a
  ticket history.
- Multiple teams work on the system, each with its own language.
- One model is sprouting fields that some use cases use and others ignore.

**Sketch.** A bounded context is _not_ a folder structure or a microservice —
those are deployment artifacts. A bounded context is a _modeling boundary_:

```text
Bounded contexts in the shop:

[Catalog]                      [Sales]                     [Fulfillment]
- Product (sku, price, ...)    - Order (lines, status)     - Shipment (route, ETA)
- Category                     - Customer (credit_limit)   - Customer (delivery_addr)
- Inventory level              - Cart                      - Carrier
- "Customer" not modelled      - "Product" = sku ref       - "Order" = shipment input

[Identity]                     [Billing]
- User (email, password)       - Account (balance)
- Session                      - Invoice
- "Customer" = user            - Customer (billing_addr)
```

`Customer` exists in three contexts. Each context owns its own representation.
They _reference each other by id_ across the boundary; they do _not_ share the
model class.

**Implementation in code.** Each bounded context becomes a module (or service)
with its own domain model:

```text
src/
  shop/
    sales/
      domain/customer.py      # Customer with credit_limit, tier
    billing/
      domain/customer.py      # Customer with balance, payment_method
    identity/
      domain/user.py          # User with email, password
```

The classes are different. They share an id (`CustomerId` is a UUID with the
same value across contexts), but no inheritance and no shared base type.

**Type-safety notes.**

- Cross-context references are _id-typed_, not entity-typed. Sales does not
  import `billing.Customer`; it stores a `BillingAccountId`.
- Use `import-linter` to fail the build on illegal cross-context imports.
- Translation between contexts happens at the boundary — see
  [Anti-Corruption Layer](#anti-corruption-layer).

**When NOT to use.**

- Single-team app, one model, one vocabulary, no team boundaries. Bounded
  contexts are about managing _linguistic_ drift; in a small app the language
  stays unified.

**Real-world examples.**

- Amazon retail vs. Amazon Web Services — same parent company, completely
  different domain models; no shared `Customer` class.
- Banking: "account" in retail banking means something different from "account"
  in trading. Different bounded contexts.

**Anti-pattern variant.** A monolithic `User` class with 80 fields, half
nullable, used by billing, marketing, support, and product. This is the
[Big Ball of Mud](#big-ball-of-mud) at the model level. Split per context.

**References.**

- Evans, _Domain-Driven Design_, ch. 14, "Maintaining Model Integrity."
- Vernon, _Implementing Domain-Driven Design_, ch. 2, "Domains, Subdomains, and
  Bounded Contexts."

---

## Context Map

**Intent.** A diagram (or written document) that shows every bounded context and
the _nature_ of the relationship between any two. The map is the
strategic-design artifact.

**When to reach for it.**

- More than two bounded contexts exist or are about to.
- Teams are debating "who owns what" or "who has to change for whom."
- Planning a migration, a service split, or an integration.

**Sketch.** The map enumerates relationships using DDD's vocabulary:

```text
[Identity]  --U/D-->  [Sales]            U = upstream, D = downstream
                                          (Sales depends on Identity's user model)

[Sales]     --SK--->  [Billing]          SK = Shared Kernel
                                          (Sales and Billing share Money, CustomerId)

[Sales]     --ACL--> [LegacyERP]         ACL = Anti-Corruption Layer
                                          (Sales translates from ERP's bizarre model)

[Sales]     --OHS--> [Catalog]           OHS = Open Host Service
                                          (Catalog publishes a stable API for many consumers)

[Mobile App] --CF--> [Sales]             CF = Conformist
                                          (Mobile takes whatever Sales provides without
                                           translation; it's not worth fighting)
```

**Pattern key.**

- _Upstream / Downstream (U/D)._ Asymmetric: upstream changes affect downstream.
  Downstream has no leverage.
- _Customer / Supplier._ Negotiated relationship — downstream has _some_
  influence. See [Customer / Supplier](#customer--supplier).
- _Shared Kernel._ Two contexts share a small piece of model deliberately. See
  [Shared Kernel](#shared-kernel).
- _Anti-Corruption Layer._ Downstream wraps the upstream to keep its bad model
  from leaking in. See [Anti-Corruption Layer](#anti-corruption-layer).
- _Open Host Service._ Upstream publishes a stable, well-documented API for many
  consumers. See [Open Host Service](#open-host-service).
- _Published Language._ The shared format on the wire. See
  [Published Language](#published-language).
- _Conformist._ Downstream just takes what's given, no translation. See
  [Conformist](#conformist).
- _Separate Ways._ Two contexts don't integrate at all.

**Type-safety notes.** None — the context map is a _human_ artifact. The
code-level manifestation is whose Protocol is whose, who imports from whom, and
how translation happens at boundaries.

**When NOT to use.** A single-context system. There's no map to draw.

**Real-world examples.**

- Microservice architectures need an explicit context map; without one, every
  team re-invents which model is canonical.
- Migration projects (legacy → modern) benefit enormously: the map shows where
  the ACL lives.

**Anti-pattern variant.** No context map at all. Teams discover relationships at
integration time, when the wrong assumptions cost weeks. The remedy is a
one-page document, kept current.

**References.**

- Evans, _Domain-Driven Design_, ch. 14, "Maintaining Model Integrity," section
  "Context Map."
- Vernon, _Implementing Domain-Driven Design_, ch. 3, "Context Maps."
- Brandolini, _Introducing EventStorming_ — provides a discovery method for the
  map.

---

## Anti-Corruption Layer

**Intent.** When integrating with a system whose model is awkward, legacy, or
impedance- mismatched, build a translation layer that converts _their_ model
into _ours_. Domain code sees only our model; the layer absorbs the awkwardness.

**When to reach for it.**

- Integrating with a legacy system whose data model would corrupt the new domain
  if let in raw.
- Calling an external API whose payload shapes don't match how we want to think.
- Migrating from one system to another while both are alive.

**Sketch.**

```python
# Our domain shape — what the rest of our code wants to see.
@dataclass(frozen=True, slots=True)
class CustomerProfile:
    id: CustomerId
    email: Email
    full_name: str
    tier: Literal["bronze", "silver", "gold"]

class CustomerProfileSource(Protocol):
    def load(self, id: CustomerId) -> CustomerProfile | None: ...

# Anti-Corruption Layer for the legacy ERP.
class LegacyErpAclCustomerSource:
    """The ERP returns customers with cryptic status codes ``A1``/``A2``/``B``,
    name as a single ``cust_name`` string, and email via a comma-delimited
    contact field. None of that nonsense leaks past this class.
    """
    def __init__(self, erp_client: LegacyErpClient) -> None:
        self._client = erp_client

    def load(self, id: CustomerId) -> CustomerProfile | None:
        raw = self._client.get_customer(legacy_id=str(id))
        if raw is None or raw["status"] == "DELETED":
            return None
        return CustomerProfile(
            id=id,
            email=Email(value=self._extract_primary_email(raw["contacts"])),
            full_name=raw["cust_name"].strip(),
            tier=self._tier_from_status(raw["status"]),
        )

    @staticmethod
    def _extract_primary_email(contacts: str) -> str:
        for chunk in contacts.split(","):
            if "@" in (c := chunk.strip()):
                return c
        raise ValueError(f"no email in contacts {contacts!r}")

    @staticmethod
    def _tier_from_status(status: str) -> Literal["bronze", "silver", "gold"]:
        match status:
            case "A1": return "gold"
            case "A2": return "silver"
            case "B":  return "bronze"
            case _:    raise ValueError(f"unknown legacy status: {status!r}")
```

**Key rules.**

- The ACL is _the only place_ in our codebase that imports the legacy types. If
  a second module imports `LegacyErpClient`, the ACL has failed.
- The ACL's output is _our_ domain types — `CustomerProfile`, `Email`, `Tier` —
  not adapted legacy types.
- Errors at the boundary translate to _our_ domain exceptions.
  `LegacyErpHttpError` becomes `CustomerNotFound` or `LegacyErpUnavailable` (a
  new domain exception).

**Type-safety notes.**

- The `CustomerProfileSource` Protocol is what consumers depend on. Tests inject
  a fake; production injects the ACL.
- Translation happens once, at the boundary. Downstream code never special-cases
  legacy semantics.

**When NOT to use.**

- The external system _is_ our domain (a microservice you control). Use
  [Published Language](#published-language) instead.
- A trivial integration where the wire shape is already what we want.

**Real-world examples.**

- Wrapping Salesforce with an ACL so domain code doesn't see Salesforce's
  bespoke names (`Account`, `Opportunity__c`).
- Wrapping a legacy mainframe COBOL response into a domain shape.
- Wrapping a Stripe webhook payload into a domain `PaymentReceived` event.

**Anti-pattern variant.** Letting the legacy types leak into the domain because
"it's just this one place." It's never just one place. The legacy shape spreads,
and refactoring later costs ten times more than the ACL would have.

**References.**

- Evans, _Domain-Driven Design_, ch. 14, "Anti-Corruption Layer."
- Vernon, _Implementing Domain-Driven Design_, ch. 3 (context map
  relationships).

---

## Shared Kernel

**Intent.** Two bounded contexts deliberately _share_ a small piece of model — a
value object, an enum, an id type — and commit to coordinating changes to it.
Sharing comes with a contract: nobody changes the kernel without notifying the
other team.

**When to reach for it.**

- Two contexts both reason about the same primitive concept and a duplication
  would drift. Common cases: `Money`, `CustomerId`, `Currency`, `CountryCode`.
- The shared piece is _small_ and _stable_.

**Sketch.**

```text
src/
  shop/
    _kernel/                  # the shared kernel — minimal, stable
      __init__.py
      money.py                # Money, Currency
      ids.py                  # CustomerId, OrderId, etc.
      events.py               # base DomainEvent
    sales/
      domain/...              # imports from _kernel
    billing/
      domain/...              # imports from _kernel
```

**Key rules.**

- **Keep the kernel small.** Every type added is a new constraint that must hold
  for both contexts. The kernel should be tens of lines, not hundreds.
- **No domain logic that's specific to one context.** A `Customer` class is not
  in the kernel; only `CustomerId` is.
- **Coordinate changes.** Adding a method to `Money` requires both teams'
  agreement.
- **The kernel has tests of its own.** Every method has invariants both contexts
  depend on.

**Type-safety notes.**

- Kernel types are `frozen=True, slots=True` value objects with smart
  constructors. They're the most-frozen things in the codebase.
- `import-linter` enforces that every context can import the kernel but the
  kernel imports nothing from any context.

**When NOT to use.**

- Two contexts that genuinely have different ideas about "the same" concept.
  Don't force shared kernel; use [Anti-Corruption Layer](#anti-corruption-layer)
  instead.
- The "kernel" is growing. Each addition makes the contract more brittle.

**Real-world examples.**

- A monorepo where multiple services share `Money`, `Currency`, `CustomerId`.
- ISO standards as de facto shared kernels: ISO 4217 currency codes, ISO 8601
  dates.

**Anti-pattern variant.** A bloated `common/` package where every team dumps
things "in case someone else needs them." That's not a kernel; it's a junk
drawer. The kernel must be _intentional_ and _small_.

**References.**

- Evans, _Domain-Driven Design_, ch. 14, "Shared Kernel."
- Vernon, _Implementing Domain-Driven Design_, ch. 3.

---

## Customer / Supplier

**Intent.** An asymmetric but _negotiated_ relationship between two contexts:
downstream ("customer") and upstream ("supplier"). The customer has needs the
supplier agrees to meet; the supplier owns the model but accepts feedback on
what to add or change.

**When to reach for it.**

- The downstream team genuinely needs influence over the upstream's contract —
  without it, they cannot do their job.
- Both teams sit inside the same organization (or have a contract with similar
  effect).

**Sketch in prose.** No code-level shape. The pattern is a _team_ and _process_
contract:

- The customer team writes acceptance tests against the supplier's API ("we need
  an event with these fields when X happens").
- The supplier team treats those tests as part of their definition of done.
- Backwards-incompatible changes go through a deprecation cycle agreed in
  advance.

The code-level manifestation is an [Open Host Service](#open-host-service) with
a [Published Language](#published-language) plus contract tests.

**Type-safety notes.** Same as Open Host Service / Published Language.

**When NOT to use.**

- The upstream is external (a third party); you're a [Conformist](#conformist).
- The upstream cannot or will not negotiate; you need an
  [Anti-Corruption Layer](#anti-corruption-layer).

**Real-world examples.**

- A backend API team and a mobile-app team in the same company with a shared
  roadmap.
- A platform team and product teams using a shared internal SDK.

**Anti-pattern variant.** Calling the relationship "customer / supplier" while
operating it as "conformist" — the downstream team has no real say. Either fix
the relationship or accept that you're conformist.

**References.**

- Evans, _Domain-Driven Design_, ch. 14, "Customer/Supplier Development Teams."

---

## Conformist

**Intent.** Downstream gives up on shaping upstream's model and conforms to
whatever the upstream provides, without translation. The downstream "speaks the
upstream's language" in its own internals.

**When to reach for it.**

- The upstream is external and unmoved by your needs.
- The upstream's model is _good enough_ — building an
  [Anti-Corruption Layer](#anti-corruption-layer) would be overkill for the
  value gained.
- The cost of translation exceeds the cost of letting the upstream's vocabulary
  in.

**Sketch in prose.** Use the upstream's types directly in your domain:

```python
# Conformist — we just use Stripe's Customer / Subscription model directly.
from stripe import Customer, Subscription

def cancel_for_user(user_id: str) -> None:
    customer = Customer.retrieve(_stripe_id_for(user_id))
    for sub in customer.subscriptions.auto_paging_iter():
        sub.cancel()
```

The trade-off: every change in the upstream propagates straight into our code;
we have no isolation. We accept that because translating Stripe to a custom
domain model is more work than periodic adaptation.

**Type-safety notes.** Use the upstream's types directly. If the upstream is
unityped (a JSON dict), wrap it minimally in a `TypedDict` so call sites get
_some_ shape.

**When NOT to use.**

- The upstream's model genuinely conflicts with our domain language. The
  cognitive cost of conforming compounds; the ACL pays for itself.
- The upstream changes frequently in ways that touch many of your call sites.

**Real-world examples.**

- Using Stripe's resource model directly in a small SaaS app — cheaper than
  translating.
- Using GitHub's API model directly in a tooling integration.

**Anti-pattern variant.** Pretending you're a conformist while in fact you've
started to sprinkle local type aliases and helpers — that's an ACL forming
organically. Either commit to conformism or commit to the ACL.

**References.**

- Evans, _Domain-Driven Design_, ch. 14, "Conformist."

---

## Open Host Service

**Intent.** A bounded context that publishes a _stable, documented_ API for many
consumers, acting as the integration point for everyone who needs to talk to it.
The API is the contract; the internals are free to change.

**When to reach for it.**

- Many downstream contexts need the same upstream data or operations.
- Each downstream having its own integration would mean N translation layers,
  all slightly different.
- The upstream is willing to take responsibility for a stable contract.

**Sketch.**

```python
# The Open Host Service — a stable Protocol exposed to many consumers.
class CatalogReadApi(Protocol):
    def get_product(self, sku: str) -> ProductView | None: ...
    def list_products(self, *, category: str | None = None, limit: int = 50) -> Sequence[ProductView]: ...
    def get_inventory_level(self, sku: str) -> int: ...

@dataclass(frozen=True, slots=True)
class ProductView:
    """The Published Language of the Catalog — stable wire shape."""
    sku: str
    name: str
    description: str
    price: Money
    available: bool
```

The contract is the `CatalogReadApi` Protocol _plus_ `ProductView` (the
[Published Language](#published-language)). Internals — how products are stored,
indexed, cached — are free to evolve as long as `ProductView` is stable.

**Wire-level manifestation.** The Protocol becomes:

- A REST API (`GET /products/{sku}`) returning JSON in `ProductView` shape.
- A gRPC service with the same shapes.
- A library with the same Protocol for in-process consumers.

All three forms can coexist; the _language_ is the same.

**Type-safety notes.**

- `CatalogReadApi` is a `Protocol` — multiple concrete implementations (REST
  client, gRPC client, in-memory) all satisfy it.
- The `ProductView` dataclass is frozen; consumers cannot mutate it.
- Versioning lives in the Published Language: `ProductViewV1`, `ProductViewV2`.

**When NOT to use.**

- One downstream consumer, no plan for more. Direct integration is simpler.
- The "service" is internal-only and the contract is in flux. An OHS is a
  _commitment_; if you're not ready to commit, don't ship one.

**Real-world examples.**

- Stripe API — the canonical OHS. Decades of versioning discipline.
- AWS service APIs — every service is an OHS.
- Internal platform APIs at large companies (auth service, identity service,
  billing service).

**Anti-pattern variant.** Publishing an "OHS" but reserving the right to change
it arbitrarily. That's an unstable internal API with a misleading name.

**References.**

- Evans, _Domain-Driven Design_, ch. 14, "Open Host Service."

---

## Published Language

**Intent.** A _shared, documented format_ used by an integration. The Published
Language is the on-the-wire vocabulary — the JSON shape of an event, the
protobuf schema, the API's response format. It's what everyone speaks,
regardless of internal models.

**When to reach for it.**

- Multiple consumers exchange data with one upstream (paired with
  [Open Host Service](#open-host-service)).
- Cross-organization integration where each side has its own internal model but
  must agree on a common wire shape.
- Long-lived events that may be replayed across versions of consumers and
  producers.

**Sketch.**

```python
# Published Language for OrderPlaced events — what hits the wire.
@dataclass(frozen=True, slots=True)
class LineItemV1:
    sku: str
    quantity: int
    unit_price_cents: int

@dataclass(frozen=True, slots=True)
class OrderPlacedV1:
    schema_version: Literal["v1"]
    event_id: str                # UUID as string for JSON portability
    occurred_at: str             # ISO-8601 UTC
    order_id: str
    customer_id: str
    total_amount_cents: int
    total_currency: str          # ISO-4217 3-letter code
    line_items: tuple[LineItemV1, ...]

def to_published(evt: OrderPlaced) -> OrderPlacedV1:
    return OrderPlacedV1(
        schema_version="v1",
        event_id=str(evt.event_id),
        occurred_at=evt.occurred_at.isoformat(),
        order_id=str(evt.order_id),
        customer_id=str(evt.customer_id),
        total_amount_cents=evt.total.amount_cents,
        total_currency=evt.total.currency,
        line_items=tuple(...),
    )
```

The Published Language is _not_ the same as the domain event class. The domain
class is internal; the Published Language version is the _wire contract_.
Stability promises apply to the wire version.

**Key rules.**

- **Versioning is part of the language.** `schema_version` lets consumers skip
  events they don't understand and producers evolve safely.
- **No internal types in the wire.** Domain `Email` becomes `str`; domain
  `Money` becomes separate `amount_cents` and `currency` fields. The wire is
  JSON-Schema- or Protobuf-friendly.
- **Backward compatibility is non-negotiable.** Adding fields is fine; renaming
  or removing fields requires a new major version with a deprecation period.

**Type-safety notes.**

- Use Pydantic or `attrs` for runtime validation at the boundary; the type
  checker can't catch wire-shape drift on its own.
- Round-trip tests: `from_published(to_published(event)) == event` (modulo
  loss).

**When NOT to use.**

- An internal API in flux. Use the [Open Host Service](#open-host-service)
  without committing to a Published Language until the shape stabilizes.
- A one-off integration where the wire shape is the upstream's and you're a
  [Conformist](#conformist).

**Real-world examples.**

- CloudEvents — a Published Language for cloud-native events.
- Schema.org — a Published Language for the semantic web.
- Stripe's webhook event payloads — versioned Published Language with multi-year
  backward compatibility.

**Anti-pattern variant.** Serializing the _internal_ domain class directly to
JSON. Now internal renames break consumers; internal-only fields leak. Always go
through a Published Language type.

**References.**

- Evans, _Domain-Driven Design_, ch. 14, "Published Language."

---

## Big Ball of Mud

**Intent.** _(This is an anti-pattern documented because absence-of-pattern
matters.)_ The default state of long-lived systems with no strategic design
discipline: every model fused to every other, no boundaries, no consistent
vocabulary, change anywhere triggers change everywhere.

**Symptoms.**

- One `User` class, 80 fields, half nullable, used by every module.
- Cross-cutting imports — billing imports from shipping imports from catalog
  imports from identity, in cycles.
- Tests need a fully-stubbed environment because everything depends on
  everything.
- "Refactoring" is rumored to be possible; nobody attempts it.

**Why it happens.** Strategic design ([Bounded Context](#bounded-context),
[Context Map](#context-map), [Anti-Corruption Layer](#anti-corruption-layer))
takes deliberate effort. Without that effort, integration takes the path of
least resistance: import what you need, extend what's there, leave the cleanup
for later.

**The remedy.** You cannot fix a Big Ball of Mud by "rewriting it." You fix it
by:

1. Drawing the [Context Map](#context-map) of the current mess (it has implicit
   boundaries).
2. Picking one boundary and making it explicit — usually with an
   [Anti-Corruption Layer](#anti-corruption-layer) on the new side.
3. Squeezing dependencies through that boundary, one at a time, until the new
   context is independent.
4. Repeating.

Each step takes weeks. The whole operation takes years. There is no shortcut.

**When NOT to "fix" it.**

- The system is being decommissioned. Don't refactor what's about to be deleted.
- The team that wrote it has scattered and the documentation is gone. A clean
  rewrite with a preserved Published Language is sometimes cheaper than
  archaeology.

**Real-world examples.**

- Most enterprise systems older than ten years.
- Startups that grew without strategic design and are now mid-rewrite.

**References.**

- Foote & Yoder, "Big Ball of Mud," 1997 — the paper that named the pattern.
- Evans, _Domain-Driven Design_, ch. 14, "Big Ball of Mud" (added in the 2014
  retrospective).
- Vernon, _Implementing Domain-Driven Design_, throughout — the book is largely
  about _avoiding_ this.

---

## When to Use What

A short decision tree.

1. **The thing has identity that survives field changes** → [Entity](#entity).
2. **The thing is defined by its attributes alone** →
   [Value Object](#value-object).
3. **A cluster of objects must obey a joint invariant under concurrent change**
   → [Aggregate Root](#aggregate-root).
4. **A piece of domain logic doesn't fit on any one entity** →
   [Domain Service](#domain-service).
5. **Business logic above persistence needs to be tested without a DB** →
   [Repository](#repository).
6. **A domain mutation must be observed by another module / service** →
   [Domain Events](#domain-events) plus the Outbox pattern.
7. **The same predicate is reused across filtering, validation, and queries** →
   [Specification](#specification) (or a plain function if one call site).
8. **Construction needs cross-aggregate orchestration** → [Factory](#factory).
9. **The codebase has more than one bounded sub-domain** → [Module](#module) per
   sub-domain plus layer within.
10. **The same noun means different things in different parts of the business**
    → [Bounded Context](#bounded-context).
11. **You're integrating with a system whose model would corrupt yours if let in
    raw** → [Anti-Corruption Layer](#anti-corruption-layer).
12. **Multiple consumers need the same upstream data** →
    [Open Host Service](#open-host-service) plus
    [Published Language](#published-language).

---

## Review Checklist

Items map to anchors above.

1. Does every entity have id-based equality (`__eq__` / `__hash__` keyed on the
   id)? ([Entity](#entity))
2. Do value objects raise on invalid construction (`__post_init__`)? Are they
   `frozen=True, slots=True`? ([Value Object](#value-object))
3. Does every aggregate hide its interior collections behind `Sequence`-typed
   views and require commands to mutate? ([Aggregate Root](#aggregate-root))
4. Is there _one_ repository per aggregate root — never per interior entity?
   ([Repository](#repository))
5. Do repository methods return _domain_ entities (and raise _domain_
   exceptions), not ORM types? ([Repository](#repository))
6. Are domain events `frozen=True`, drained _after_ commit, and published via
   the outbox when crossing process boundaries?
   ([Domain Events](#domain-events))
7. For each bounded context: do imports respect the boundary, enforced by
   `import-linter`? ([Bounded Context](#bounded-context), [Module](#module))
8. Does every cross-context reference use _id_ types, not entity types?
   ([Bounded Context](#bounded-context))
9. Is there an Anti-Corruption Layer at every boundary with an awkward upstream
   — and is it the _only_ place that imports the upstream's types?
   ([Anti-Corruption Layer](#anti-corruption-layer))
10. Does the Open Host Service have a stable
    [Published Language](#published-language) with versioning, and is the wire
    shape independent of the internal domain?
    ([Open Host Service](#open-host-service))
11. Is there a written context map? If three or more contexts exist and the map
    is not written down, it is wrong. ([Context Map](#context-map))
12. Anywhere a `*Service` is mutating fields on a dataclass: is that an
    [Anemic Domain Model](#aggregate-root)? Move the behavior onto the entity.
