# Functional & Algebraic Patterns in Strictly-Typed Python

Patterns that come from ML-family languages (Haskell, OCaml, F#, Rust, Scala)
and translate _usefully_ into Python 3.13+. Not every functional idiom earns its
keep here — Python is not Haskell and pretending otherwise produces tortured
code. The patterns in this file all pass one test: they make a real Python
program _easier to type, easier to test, and harder to misuse_ than the
imperative-and-exceptions baseline. Anything that fails that test (free monads,
profunctor optics, fancy effect systems) is intentionally absent.

The single thread through everything below is Wlaschin's mantra: **make illegal
states unrepresentable**. The compiler is the cheapest test in the codebase.
Push correctness into the type, then most of the runtime checks disappear.

## How to use this file

Read top-down on a first pass — patterns build on each other. After that, jump
to the section you need. Each entry follows the same shape:

1. **Intent** — what it gives you.
2. **When to reach for it** — concrete triggers.
3. **Sketch** — strict-typed Python 3.13+. Where another language is more
   natural (Rust for `Result<T, E>`, F# for ADTs), a secondary sketch follows
   the Python one.
4. **Type-safety notes** — what mypy/pyright catch.
5. **When NOT to use** — the overkill threshold.
6. **Real-world examples** — named libraries or systems.
7. **Anti-pattern variant** — common misuse.
8. **References** — book and chapter.

Conventions (non-negotiable):

- `Protocol` over `ABC`; PEP 695 generics (`class Foo[T]:`); PEP 604 unions
  (`X | Y`).
- `Self`, `Final`, `@override`. No `Any`. Use the annotation-evaluation policy
  in `SKILL.md` conventions; the `python:typings` sister skill has the full
  canonical reference if it is also loaded.
- Every Python block is written to target `mypy --strict` and
  `pyright --strict`.

---

## Result / Either

**Intent.** Encode "this operation may fail" in the _return type_ instead of the
control flow. A function's signature lists every failure mode the caller must
handle; nothing fails by throwing past the type.

**When to reach for it.**

- The failure is a _domain_ outcome (validation failed, payment declined,
  rate-limited), not a programmer error or unexpected I/O fault.
- The same call site has multiple failure modes that should be distinguished
  without a chain of `except` blocks.
- You want exhaustive checking — `mypy --strict` should fail the build when a
  new variant is added and a caller forgets to handle it.

**Sketch — Python.**

```python
from dataclasses import dataclass
from typing import Final, Literal, Protocol, assert_never, cast

@dataclass(frozen=True, slots=True)
class Ok[T]:
    tag: Literal["ok"]
    value: T

@dataclass(frozen=True, slots=True)
class Err[E]:
    tag: Literal["err"]
    error: E

type Result[T, E] = Ok[T] | Err[E]

def ok[T](value: T) -> Result[T, object]:
    return Ok(tag="ok", value=value)

def err[E](error: E) -> Result[object, E]:
    return Err(tag="err", error=error)
```

The `tag` field is what makes this a proper _tagged_ union for `match`
exhaustiveness. Pyright and mypy can both narrow on
`Literal["ok"] | Literal["err"]`, so a forgotten case becomes a type error, not
a runtime surprise.

```python
@dataclass(frozen=True, slots=True)
class InvalidEmail:
    raw: str

@dataclass(frozen=True, slots=True)
class Disposable:
    domain: str

type EmailError = InvalidEmail | Disposable

def parse_email(raw: str) -> Result[str, EmailError]:
    if "@" not in raw:
        return Err(tag="err", error=InvalidEmail(raw=raw))
    if raw.endswith("@mailinator.com"):
        return Err(tag="err", error=Disposable(domain="mailinator.com"))
    return Ok(tag="ok", value=raw.lower())

def describe(r: Result[str, EmailError]) -> str:
    match r:
        case Ok(value=email):
            return f"valid: {email}"
        case Err(error=InvalidEmail(raw=raw)):
            return f"missing @: {raw!r}"
        case Err(error=Disposable(domain=d)):
            return f"disposable provider: {d}"
        case _ as never:
            assert_never(never)
```

`assert_never` is the load-bearing piece. Add `Banned` to `EmailError` and
_every_ `match` like this becomes a type error until you handle the new case.
That's what we are paying for.

**Sketch — Rust (the reference implementation).**

```rust
enum EmailError { InvalidEmail(String), Disposable(String) }

fn parse_email(raw: &str) -> Result<String, EmailError> {
    if !raw.contains('@') {
        return Err(EmailError::InvalidEmail(raw.to_string()));
    }
    if raw.ends_with("@mailinator.com") {
        return Err(EmailError::Disposable("mailinator.com".to_string()));
    }
    Ok(raw.to_lowercase())
}

fn welcome(raw: &str) -> Result<String, EmailError> {
    let email = parse_email(raw)?;            // early-return on Err
    let normalized = canonicalize(&email)?;   // chains
    Ok(format!("hi {}", normalized))
}
```

The `?` operator is what Python lacks. Each `?` says "if this is `Err`, return
it; otherwise unwrap and continue." It collapses the railway pattern to a single
character. Python forces you to write the railway pattern explicitly (see
[Railway-Oriented Programming](#railway-oriented-programming)).

**Type-safety notes.**

- Make `Result` a `type` alias of a tagged union, not an opaque class with
  `.is_ok()`. That way `match` narrowing works, and you do not need a method to
  peek at the value.
- `frozen=True, slots=True` makes the variants hashable, fast, and immutable.
  They behave like values, which is what you want.
- Variance: `Result[T, E]` is covariant in both arguments because Python type
  variables on PEP 695 generics default to inference and the variants are
  read-only via `frozen=True`.
- Always exhaust the match with `assert_never`. A bare `case _:` that does not
  call `assert_never` silently swallows new variants.

**When NOT to use.**

- The error is _not_ a domain outcome — a `ConnectionResetError` from a socket
  should bubble up as an exception, not be encoded as `Err`. Reserve `Result`
  for things the _business_ cares about.
- A single-call-site one-shot with one failure mode.
  `parse_email(raw) -> str | None` is fine. Wrapping it in `Result` for one
  variant is overkill.
- Hot loops in numeric code. The allocation per call is real and you don't need
  it.

**Real-world examples.**

- The [`returns`](https://github.com/dry-python/returns) Python library —
  `Result[T, E]` plus monadic combinators (`bind`, `map`, `do_notation`).
- Rust's standard library — `Result<T, E>` is _the_ error type; exceptions don't
  exist.
- `pydantic.ValidationError` is the un-functional cousin: it throws. Wrapping
  `BaseModel.model_validate` in a helper that returns
  `Result[Model, ValidationError]` is a common refactor when validation is on
  the happy-path branching, not an exception.

**Anti-pattern variant.**

```python
# DON'T: untyped, exception-mixed, opaque Result.
class Result:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
    def is_ok(self) -> bool:
        return self.error is None
```

This buys nothing over `value: T | None`. The whole point of `Result` is that
the type checker enforces handling — this version forces every caller to
remember the convention.

**References.**

- _The Rust Programming Language_, ch. 9, "Recoverable Errors with `Result`."
- Wlaschin, _Domain Modeling Made Functional_, ch. 10, "Implementation: Working
  with Errors."

---

## Option / Maybe / Optional

**Intent.** Express "this value may be absent" in a way the compiler enforces
_and_ that composes well with downstream operations.

**When to reach for it.**

- A lookup that may miss (`get_user(id) -> User | None`).
- A field that's optional in the domain model.
- A pipeline step that may legitimately produce nothing (`first_match`,
  `parse`).

**Sketch — Python.** In Python, `T | None` is the idiomatic Option. There is no
good reason to build a separate `Maybe[T]` type; the narrowing rules already
work:

```python
def first[T](items: Iterable[T], pred: Callable[[T], bool]) -> T | None:
    for item in items:
        if pred(item):
            return item
    return None

def shout(s: str | None) -> str:
    if s is None:
        return ""
    return s.upper()       # mypy narrows: s is str here
```

To combine optional values without nested `if x is not None:` ladders, a thin
helper:

```python
def map_opt[T, U](value: T | None, fn: Callable[[T], U]) -> U | None:
    return None if value is None else fn(value)

def flat_map_opt[T, U](value: T | None, fn: Callable[[T], U | None]) -> U | None:
    return None if value is None else fn(value)
```

That's a poor man's `?.` from Kotlin/Swift. Three+ nested calls means you really
want `Result` with a `MissingX` variant instead — then _why_ the value was
absent travels with the failure.

**Sketch — Rust / Haskell.**

```rust
fn welcome(raw: &str) -> Option<String> {
    let uid = parse_user_id(raw)?;     // None propagates
    let user = find_user(uid)?;
    Some(format!("hi {}", user.email.to_lowercase()))
}
```

```haskell
welcome :: String -> Maybe String
welcome raw = do
    uid <- parseUserId raw
    u   <- findUser uid
    pure (toLower (email u))
```

**Type-safety notes.**

- Use `T | None`, not `Optional[T]`. They're equivalent; `T | None` reads better
  next to `X | Y | Z`.
- Never default a parameter to `None` to mean "use the default" — that hides
  intent. If you need an optional override, name a sentinel or accept a
  `T | None` _and_ document the semantics.
- Distinguish _absent_ from _empty_. `[]` and `None` are not the same; pick one
  and stay consistent.

**When NOT to use.**

- When the failure has a _reason_ the caller cares about.
  `find_user_by_email("x") -> User | None` says nothing about _why_ the lookup
  missed. If "the user is banned" matters, `Result[User, UserLookupError]` is
  the right shape.
- Constructing a wrapped `Maybe[T]` class in Python. Skip the wrapper.

**Real-world examples.**

- Rust `Option<T>` and the `?` operator on it.
- Kotlin/Swift `T?` with the `?.` and `?:` operators.
- SQLAlchemy `session.get(Model, pk) -> Model | None`.

**Anti-pattern variant.**

```python
# DON'T: returning a sentinel that the caller might mistake for a real value.
EMPTY_USER: Final[User] = User(id="0", email="")  # a "null object"

def find_user(id: str) -> User:
    return _users.get(id, EMPTY_USER)
```

Now every caller has to remember to compare against `EMPTY_USER`. The type
system can't help. Return `User | None` and let the type tell the truth.

**References.**

- _The Rust Programming Language_, ch. 6, "Enums and Pattern Matching."
- Hutton, _Programming in Haskell_, ch. 12, "Monads and More" — the `Maybe`
  instance.

---

## Algebraic Data Types

**Intent.** Model a domain value as a _closed_ set of named alternatives (sum)
and tuples of named fields (product), so that the type checker enforces that
every alternative is handled and every required field is present.

**When to reach for it.**

- The domain has a fixed set of variants (event types, command types, payment
  methods, parser states).
- You want pattern-match exhaustiveness — adding a variant becomes a build error
  everywhere it matters.
- You want to _encode rules_ into the type. "An order is either Draft or Placed;
  only a Placed order has a placed*at." The two states are different \_types*,
  not the same type with a nullable field.

**Sketch — Python (sum types via tagged unions).**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, assert_never

@dataclass(frozen=True, slots=True)
class DraftOrder:
    tag: Literal["draft"]
    items: tuple[LineItem, ...]

@dataclass(frozen=True, slots=True)
class PlacedOrder:
    tag: Literal["placed"]
    items: tuple[LineItem, ...]
    placed_at: datetime
    confirmation: str

@dataclass(frozen=True, slots=True)
class CancelledOrder:
    tag: Literal["cancelled"]
    items: tuple[LineItem, ...]
    cancelled_at: datetime
    reason: str

type Order = DraftOrder | PlacedOrder | CancelledOrder

def describe(order: Order) -> str:
    match order:
        case DraftOrder(items=items):
            return f"draft with {len(items)} items"
        case PlacedOrder(confirmation=conf, placed_at=at):
            return f"placed {conf} at {at.isoformat()}"
        case CancelledOrder(reason=r):
            return f"cancelled: {r}"
        case _ as never:
            assert_never(never)
```

Adding `RefundedOrder` to the union turns _every_ `match` over `Order` in the
codebase into a type error until handled. That's the property you're paying for.

**Sketch — Python (Pydantic discriminated unions).**

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Discriminator, TypeAdapter

class CardPayment(BaseModel):
    method: Literal["card"] = "card"
    last_four: str
    network: Literal["visa", "mastercard", "amex"]

class BankPayment(BaseModel):
    method: Literal["bank"] = "bank"
    account_last_four: str

class CryptoPayment(BaseModel):
    method: Literal["crypto"] = "crypto"
    chain: Literal["btc", "eth", "sol"]
    tx_hash: str

Payment = Annotated[CardPayment | BankPayment | CryptoPayment, Discriminator("method")]
PaymentAdapter: Final[TypeAdapter[Payment]] = TypeAdapter(Payment)

parsed: Payment = PaymentAdapter.validate_python(
    {"method": "card", "last_four": "4242", "network": "visa"},
)
```

`Discriminator("method")` tells Pydantic _and_ the type checker which field
selects the variant. Without it, Pydantic falls back to "try each in order,"
which is slow and loses static type narrowing.

**Sketch — F# (the reference syntax).**

```fsharp
type Order =
    | Draft     of items: LineItem list
    | Placed    of items: LineItem list * placedAt: DateTime * confirmation: string
    | Cancelled of items: LineItem list * cancelledAt: DateTime * reason: string

let describe order =
    match order with
    | Draft items                    -> sprintf "draft with %d items" (List.length items)
    | Placed (_, _, conf)            -> sprintf "placed %s" conf
    | Cancelled (_, _, reason)       -> sprintf "cancelled: %s" reason
```

F# enforces exhaustiveness with no `assert_never` ceremony — adding a variant is
a hard compile error. Python gets _most_ of the way there with `Literal`
discriminators plus `assert_never`. The 80% solution.

**Type-safety notes.**

- Always include the `Literal[...]` tag. Pyright/mypy use it for narrowing
  inside `match`. Without it, you get structural matching against field shape,
  which is fragile.
- `frozen=True` on every variant. ADT values should be immutable; mutation
  defeats the reasoning.
- Use `tuple[X, ...]` for collections in ADT fields, not `list[X]`. Lists
  invalidate `frozen=True`'s guarantee — you can mutate the list even though the
  dataclass is frozen.
- Prefer `type Foo = A | B | C` (PEP 695) over `Foo: TypeAlias = ...` — it's the
  new canonical form.

**When NOT to use.**

- The variants share _all_ their data and differ only by name. That's a single
  type with an enum tag, not an ADT.
- The set of variants is open (plugin types, user-defined extensions). ADTs are
  _closed_; if the set isn't, you want a Protocol with a registry.

**Real-world examples.**

- Rust enums: `Option<T>`, `Result<T, E>`, `serde_json::Value`.
- Pydantic v2's discriminated unions used everywhere webhook payloads are
  parsed.
- Python's [`returns`](https://github.com/dry-python/returns) and
  [`expression`](https://github.com/dbrattli/Expression) libraries — both ship
  `Result` and `Option` as ADTs with combinators.
- The `ast` module — every node is a tagged-union variant.

**Anti-pattern variant.**

```python
# DON'T: enum + nullable fields = "stringly-tagged record" with no exhaustiveness.
@dataclass
class Order:
    status: Literal["draft", "placed", "cancelled"]
    items: list[LineItem]
    placed_at: datetime | None        # only set when status == "placed"
    confirmation: str | None          # only set when status == "placed"
    cancelled_at: datetime | None     # only set when status == "cancelled"
    reason: str | None                # only set when status == "cancelled"
```

Every caller has to remember the implicit invariant ("if status is placed then
placed_at is not None"). The type checker can't enforce it. Use the variant
version above.

**References.**

- Wlaschin, _Domain Modeling Made Functional_, ch. 6, "Integrity and Consistency
  in the Domain."
- _The Rust Programming Language_, ch. 6, "Enums and Pattern Matching."
- Granin, _Functional Design and Architecture_, ch. 4, "Domain Model Design with
  ADTs."

---

## Immutability

**Intent.** Treat values as values: once constructed, never mutated. Mutation
becomes the _explicit_ operation (build a new value), so concurrent access,
time-travel debugging, and referential reasoning all become possible.

**When to reach for it.**

- Always for value objects (see DDD). A `Money` that mutates is a bug.
- Domain events. Once `OrderPlaced` is published, its fields cannot change.
- Configuration. Loaded once, used everywhere; mutating a config midway is a
  defect.
- Anywhere two threads might read the same object.

**Sketch — Python.**

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

@dataclass(frozen=True, slots=True)
class Money:
    amount_cents: int
    currency: str

    def add(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError(f"cannot add {self.currency} and {other.currency}")
        return replace(self, amount_cents=self.amount_cents + other.amount_cents)

# Module-level constant: Final tells the checker nobody is allowed to rebind it.
DEFAULT_CURRENCY: Final[str] = "USD"

# Read-only API surfaces:
def total(items: Sequence[LineItem]) -> Money: ...
def index_by_id(items: Sequence[LineItem]) -> Mapping[str, LineItem]: ...
```

Three rules that catch most mutation bugs:

1. `frozen=True` on every dataclass that represents a value.
2. `Sequence` over `list`, `Mapping` over `dict` _in function signatures_.
   Internally you can use a `list` to build the result, then return it as a
   `Sequence`. Callers can't mutate what they received.
3. `Final` on module-level constants and on attributes that should not be
   reassigned.

**Defensive copying.** Frozen dataclasses are _shallowly_ immutable. A
`list[LineItem]` field is mutable through the field reference even though the
dataclass is frozen — fix by storing `tuple[LineItem, ...]`. Update via
`dataclasses.replace(cart, items=cart.items + (extra,))` or `attrs.evolve`.

**Sketch — F# (records are immutable by default).**

```fsharp
type Money = { Amount: int; Currency: string }
let usd2 = { usd with Amount = 200 }     // copy with one field changed
```

F#, OCaml, and Haskell give you immutability for free; Python makes you ask for
it.

**Type-safety notes.**

- `frozen=True` blocks `instance.field = new_value` at runtime, and pyright/mypy
  flag it statically.
- `slots=True` saves memory and prevents arbitrary attribute injection.
- `Final` is enforced statically by mypy/pyright; it doesn't change runtime
  behavior, but the build fails when someone reassigns.
- A `Sequence[T]` parameter cannot be appended to inside the function —
  `mypy --strict` rejects `arg.append(x)`. That's the protection.

**When NOT to use.**

- Genuinely mutable state owned by one component — a counter inside a
  long-running loop, a cache. Wrapping it in `frozen=True` and `replace`-ing on
  every increment burns allocations for no reason.
- Hot inner loops where the GC pressure of "new value per step" dominates.
  Profile first.

**Real-world examples.**

- Pydantic v2 models with `model_config = ConfigDict(frozen=True)`.
- `attrs` with `@frozen` for higher-performance immutable records.
- Clojure's persistent data structures — the immutable-by-default extreme.

**Anti-pattern variant.**

```python
# Mutable value object, eventually concurrency bug.
class Money:
    def __init__(self, amount: int, currency: str) -> None:
        self.amount = amount
        self.currency = currency

    def add(self, other: "Money") -> None:
        self.amount += other.amount
```

`Money.add` _mutates_ `self`. A function that takes `Money` can no longer treat
it as a value. Two threads adding to the same `Money` race; one will lose.
Frozen dataclass with `add` returning a new `Money` removes the entire class of
bug.

**References.**

- Wlaschin, _Domain Modeling Made Functional_, ch. 5, "A Functional
  Architecture."
- Bloch, _Effective Java_, item 17, "Minimize Mutability." (Translates wholesale
  to Python.)

---

## Composition and Pipelines

**Intent.** Build a complex transformation by composing small functions, each of
which does one thing. The pipeline reads top-to-bottom in the order data flows.

**When to reach for it.**

- A multi-step transformation: parse → validate → enrich → persist.
- A data pipeline where each step has a single input and a single output type.
- Anywhere `data.method().method().method()` would be more natural than nested
  calls.

**Sketch — Python.** Python's type system can't generically represent "function
1: A→B, function 2: B→C, ..." in a single typed signature with arbitrary length.
So pipelines come in three honest shapes:

```python
from collections.abc import Callable
from dataclasses import dataclass
from functools import reduce

# Option 1: chain explicitly. Most readable, type-checker happy.
result: Account = persist(enrich(validate(parse(raw))))

# Option 2: bind step results to names. Verbose but obvious.
parsed    = parse(raw)
validated = validate(parsed)
enriched  = enrich(validated)
result    = persist(enriched)

# Option 3: fluent wrapper. Pyright follows the chain.
@dataclass(frozen=True, slots=True)
class Pipe[T]:
    value: T
    def then[U](self, fn: Callable[[T], U]) -> "Pipe[U]":
        return Pipe(value=fn(self.value))

result_account: Account = (
    Pipe(value=raw).then(parse).then(validate).then(enrich).then(persist).value
)
```

Option 3 is the closest pure-Python gets to F#'s `|>`. It type-checks, but
allocates per step.

**Sketch — F# (the reference syntax).**

```fsharp
let processOrder raw =
    raw
    |> parse
    |> validate
    |> enrich
    |> persist
```

`|>` is just `let x = f y` reversed. Python doesn't give you the operator and
`pipe`-style helpers don't generalize cleanly across changing types — so Python
pipelines tend to be explicit chains. That's fine.

**Functional `reduce` for _homogeneous_ pipelines.**

```python
from functools import reduce

steps: list[Callable[[Document], Document]] = [
    strip_whitespace, lower_case_keys, remove_empty_fields, validate_schema,
]
final_doc: Document = reduce(lambda doc, step: step(doc), steps, raw_doc)
```

This works because every step has the same input/output type. For varying types,
write the chain.

**Type-safety notes.**

- `pipe[T, U]` cannot type the heterogeneous case. Don't pretend it can. Either
  chain explicitly or use a fluent `Pipe[T]` wrapper.
- `reduce` over `Callable[[T], T]` is the only typed `reduce` shape that pyright
  handles cleanly without `cast`.

**When NOT to use.**

- Two steps. `validate(parse(raw))` is fine.
- The pipeline contains side-effecting steps that should be visible in tests.
  Chained calls hide where the I/O happens; explicit lines surface it.

**Real-world examples.**

- Toolz / cytoolz — Python's pipeline-helper libraries.
- Pandas `df.assign(...).query(...).groupby(...).agg(...)` — the most common
  pipeline in Python.
- Polars / SQLAlchemy `select(...).where(...).group_by(...)` — fluent builders
  are pipelines.

**Anti-pattern variant.**

```python
# Composition theatre with imported `compose` for two functions.
from functools import reduce
from toolz import compose
shout_loud = compose(str.upper, str.strip)
print(shout_loud("  hi  "))
```

For two functions, `str.strip("  hi  ").upper()` is shorter, faster, more
readable, and uses the standard library. Reach for `compose` when the chain is
genuinely long and reused.

**References.**

- Wlaschin, _Domain Modeling Made Functional_, ch. 9, "Implementation: Composing
  a Pipeline."
- Hughes, "Why Functional Programming Matters," 1990 — the original argument for
  composition.

---

## Currying and Partial Application

**Intent.** Fix some arguments of a function up front and produce a new function
that takes the rest later. Useful when the same prefix recurs across many call
sites.

**When to reach for it.**

- A handler signature requires `Callable[[Request], Response]` and you have
  `Callable[[Config, Request], Response]`. Partial-apply the config.
- A logger call site repeats the same `tags=...` everywhere. Bind the tags once.
- A retry decorator wants `Callable[[], T]` and you have `Callable[[A, B], T]`.
  Bind A and B.

**Sketch — Python.** `functools.partial` is the answer 95% of the time:

```python
from functools import partial
from typing import Callable

def fetch(client: HttpClient, timeout: float, url: str) -> bytes:
    return client.get(url, timeout=timeout).content

# Bind the parts that don't change per call:
fetch_with_default: Callable[[str], bytes] = partial(fetch, default_client, 5.0)

body = fetch_with_default("https://example.com/v1/users")
```

`partial` is typed in the standard library; pyright/mypy infer the resulting
signature.

**True currying** — turning `f(a, b, c)` into `f(a)(b)(c)` — is rarely worth it
in Python. Compared to `partial(operator.mul, 2)`, a hand-rolled `curry2` saves
no characters and reads worse. Reach for it only when downstream tooling demands
strictly-unary functions (some FP libraries do).

**Sketch — Haskell (where currying is the default).**

```haskell
multiply :: Int -> Int -> Int
multiply x y = x * y

double :: Int -> Int
double = multiply 2          -- partial application is free
```

Every function is curried by default. Python is the opposite — explicit is
better than implicit, so partial application is opt-in via `partial`.

**Type-safety notes.**

- `functools.partial` returns `partial[T]`; pyright/mypy infer the resulting
  signature.
- `partial` does NOT propagate `Callable` _parameter names_ — frameworks that
  require keyword-only call sites need verification after binding.
- A `lambda` is often clearer than `partial`:
  `lambda url: fetch(default_client, 5.0, url)` is more obvious than
  `partial(fetch, default_client, 5.0)`.

**When NOT to use.**

- The bound argument is _itself_ state. `partial(send_email, smtp_client)` looks
  tempting, but you've now hidden the `smtp_client` dependency from every caller
  and from every test. Pass it explicitly or inject it.
- The function takes more than ~3 args. `partial(fn, a, b, c)` quickly becomes
  positionally-ambiguous; switch to a class with `__call__` or a closure with
  named bindings.

**Real-world examples.**

- `pytest`'s `monkeypatch.setattr(target, partial(real_fn, prebound))` style.
- Async middleware: `partial(handler, request_context)` produces a 0-arg
  callable to schedule.
- The `returns` library exposes `curry` for use with its `Reader` monad.

**Anti-pattern variant.**

```python
# Partial-applying a service to hide it from the call site.
process_order = partial(_process_order_impl, payment_gateway, fraud_checker, audit_log)

def handle_request(req: Request) -> Response:
    return process_order(req)        # what does this depend on? unclear without reading the
                                     # module top.
```

The function now has hidden dependencies that don't show up in its signature.
Tests can't substitute them. Use dependency injection (constructor or function
parameter) instead.

**References.**

- Hutton, _Programming in Haskell_, ch. 4, "Curried Functions."
- Wlaschin, _Domain Modeling Made Functional_, ch. 8, "Understanding Functions."

---

## Railway-Oriented Programming

**Intent.** Compose a chain of `Result`-returning operations so that failure
short-circuits through the chain without exception throwing or nested
`if`-checks. The "happy path" is one rail; the "error path" is the other; each
step takes a value off the happy path and either keeps it there or kicks it onto
the error path.

**When to reach for it.**

- Validation pipelines: parse → check rules → check rules → produce.
- Multi-step domain operations where every step can fail with a different
  reason.
- Anywhere the call site would otherwise be a chain of `try/except` or nested
  `if r.is_err(): return r`.

**Sketch — Python (combinators).** Reuse the `Ok` / `Err` / `Result` from
[Result / Either](#result--either):

```python
def map_r[T, U, E](r: Result[T, E], fn: Callable[[T], U]) -> Result[U, E]:
    match r:
        case Ok(value=v):  return Ok(tag="ok", value=fn(v))
        case Err() as e:   return e
        case _ as never:   assert_never(never)

def bind_r[T, U, E](r: Result[T, E], fn: Callable[[T], Result[U, E]]) -> Result[U, E]:
    match r:
        case Ok(value=v):  return fn(v)
        case Err() as e:   return e
        case _ as never:   assert_never(never)
```

`map_r` lifts a plain function onto the railway. `bind_r` (a.k.a. `flat_map`,
`>>=`) chains a `Result`-returning step. **Production Python rarely uses the
lambda-staircase form** — the procedural shape reads better and pyright narrows
it correctly:

```python
def register(raw: dict[str, str]) -> Result[Account, RegistrationError]:
    email_r = parse_email(raw.get("email", ""))
    if isinstance(email_r, Err):
        return email_r
    pwd_r = parse_password(raw.get("password", ""))
    if isinstance(pwd_r, Err):
        return pwd_r
    taken_r = check_not_taken(email_r.value)
    if isinstance(taken_r, Err):
        return taken_r
    return Ok(tag="ok", value=create_account(email_r.value, pwd_r.value))
```

The lambda-staircase (`bind_r(..., lambda x: bind_r(...))`) is for short, pure
pipelines only.

**The `returns` library** provides cleaner syntax via `flow`/`bind` if you take
the dependency:

```python
from returns.pipeline import flow
from returns.pointfree import bind

result = flow(raw, parse_email_v2, bind(parse_password_v2), bind(create_account_v2))
```

`flow` and `bind` from `returns` are typed via heroic gymnastics; pyright
occasionally chokes. Evaluate on your code before adopting.

**Sketch — F# (where this pattern was named).**

```fsharp
let register raw =
    raw
    |> parseEmail
    |> Result.bind parsePassword
    |> Result.bind checkNotTaken
    |> Result.bind createAccount
```

In F# the pipeline reads as data flowing through stages. In Rust, the same shape
with `?`:

```rust
fn register(raw: &Raw) -> Result<Account, RegistrationError> {
    let email = parse_email(&raw.email)?;
    let pwd   = parse_password(&raw.password)?;
    check_not_taken(&email)?;
    Ok(create_account(email, pwd))
}
```

**Type-safety notes.**

- All steps in a railway must agree on the _error_ type `E`. If steps fail with
  different errors, lift each into a common error union:
  `type RegistrationError = InvalidEmail | WeakPassword | EmailTaken`.
- A step that returns `Result[T, EmailError]` cannot directly chain into a step
  that returns `Result[T, PasswordError]`. Adapt with `map_err`:

```python
def map_err_r[T, E, F](r: Result[T, E], fn: Callable[[E], F]) -> Result[T, F]:
    match r:
        case Ok() as ok:
            return ok
        case Err(error=e):
            return Err(tag="err", error=fn(e))
        case _ as never:
            assert_never(never)
```

**When NOT to use.**

- A linear chain with one or two steps. The procedural form is fine for `n ≤ 2`.
- Steps that legitimately throw exceptions for non-domain reasons (DB connection
  drops, serialization errors). Don't `Result`-ify infrastructure faults; let
  them throw.

**Real-world examples.**

- F# core libraries — the canonical implementation; Wlaschin's "Railway-Oriented
  Programming" series at fsharpforfunandprofit.com is the source.
- Rust's `?` operator — railway built into the language.
- Python `returns` library's `Result.bind` and `flow`/`pipe` helpers.

**Anti-pattern variant.**

```python
# DON'T: throw exceptions inside the railway. Defeats the whole point.
def register(raw: dict[str, str]) -> Result[Account, RegistrationError]:
    try:
        email = _validate_email(raw["email"])    # raises ValueError
        pwd   = _validate_password(raw["password"])
        return Ok(tag="ok", value=create_account(email, pwd))
    except ValueError as e:
        return Err(tag="err", error=InvalidEmail(raw=str(e)))
```

If `_validate_email` raises, you've reverted to exception-driven control flow
with `Result` as cosmetic packaging. Either commit to `Result` end-to-end
(validators return `Result`) or don't bother.

**References.**

- Wlaschin, "Railway-Oriented Programming,"
  [fsharpforfunandprofit.com/rop](https://fsharpforfunandprofit.com/rop/)
  (2013).
- Wlaschin, _Domain Modeling Made Functional_, ch. 10, "Implementation: Working
  with Errors."
- _The Rust Programming Language_, ch. 9, on the `?` operator.

---

## Lenses and Optics

**Intent.** Read or write a deeply-nested field in an immutable structure
without writing copy-and-replace boilerplate at every level.

**When to reach for it.**

- The domain has a 3+-deep immutable structure
  (`Account → Profile → Address → ZipCode`) and several use cases need to update
  one leaf field while preserving the rest.
- You want optic _composition_: "give me a lens from Account to Address"
  composed with "from Address to ZipCode" yielding "from Account to ZipCode."

**Honest assessment for Python.** Lenses earn their keep in Haskell, F#, and
Scala, where the language has the syntax and the type system to make them
concise. Python's `dataclasses.replace` and `attrs.evolve` already cover the
common case at one level of nesting. **For nesting deeper than two, Python
lenses become uglier than the alternative.**

**Sketch — Python at one level (just use `replace`).**

```python
from dataclasses import dataclass, replace

@dataclass(frozen=True, slots=True)
class Address:
    street: str
    zip_code: str

@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    address: Address

@dataclass(frozen=True, slots=True)
class Account:
    id: str
    profile: Profile

# One level deep — natural.
def with_name(account: Account, name: str) -> Account:
    return replace(account, profile=replace(account.profile, name=name))

# Three levels deep — painful but readable.
def with_zip(account: Account, zip_code: str) -> Account:
    return replace(
        account,
        profile=replace(
            account.profile,
            address=replace(account.profile.address, zip_code=zip_code),
        ),
    )
```

**Sketch — Python with a lens helper.** Build it only if 5+ deep paths share an
update target.

```python
@dataclass(frozen=True, slots=True)
class Lens[S, A]:
    """Read-write access to an `A` inside an `S`, immutably."""
    get: Callable[[S], A]
    set: Callable[[S, A], S]

    def then[B](self, other: "Lens[A, B]") -> "Lens[S, B]":
        return Lens(
            get=lambda s: other.get(self.get(s)),
            set=lambda s, b: self.set(s, other.set(self.get(s), b)),
        )

profile_l: Final[Lens[Account, Profile]] = Lens(lambda a: a.profile, lambda a, p: replace(a, profile=p))
address_l: Final[Lens[Profile, Address]] = Lens(lambda p: p.address, lambda p, a: replace(p, address=a))
zip_l:     Final[Lens[Address, str]]     = Lens(lambda a: a.zip_code, lambda a, z: replace(a, zip_code=z))

account_zip: Final[Lens[Account, str]] = profile_l.then(address_l).then(zip_l)
new_account = account_zip.set(account, "94110")
```

12 lines of plumbing for 6 lines of `replace`. Break-even is when many call
sites need the same deep path.

**Sketch — Haskell (where lenses shine).**

```haskell
import Control.Lens
makeLenses ''Address
makeLenses ''Profile
makeLenses ''Account
newAccount = account & profileL . address . zip .~ "94110"
```

Three levels deep, one operator. Python doesn't get there.

**When NOT to use.**

- Mutable structures. Lenses are for _immutable_ updates; with mutation you just
  write `account.profile.address.zip_code = "94110"`.
- One-shot deep updates. Inline `replace` is fine.
- Nesting of two levels or fewer. The plumbing-to-payload ratio doesn't pay.

**Real-world examples.**

- [pyrsistent](https://github.com/tobgu/pyrsistent) — persistent collections
  with `set_in` and `transform` for nested updates.
- [Lenses](https://github.com/ingolemo/python-lenses) — a typed lens library for
  Python; not widely adopted because the deep-Python use case is small.
- Haskell's `lens` library and `microlens` — the reference for what optics can
  be.

**Anti-pattern variant.**

```python
# DON'T: import a heavyweight lens library to do one update.
import lenses
new_account = lenses.bind(account).profile.address.zip_code.set("94110")
```

Reads cute on the page; brings a dependency, untyped at the leaf, and is slower
than the explicit `replace` ladder for a one-off use case. Reach for the library
only when you have many such updates _and_ the nesting is deep.

**References.**

- van Laarhoven, "CPS based functional references," 2009 — the original blog
  post that defined modern lenses.
- Kmett's `lens` package documentation, Hackage.

---

## Totality and Smart Constructors

**Intent.** A _total_ function returns a valid value for every value of its
declared input type. Achieve totality by making the input type so precise that
_no_ input is invalid. Smart constructors are the gate: they're the only way to
build the precise type, and they validate on the way in.

**When to reach for it.**

- Primitive obsession. `def send(email: str, body: str)` accepts `""`,
  `"not an email"`, and `"💩"`. None of those should typecheck.
- A function whose precondition is "non-empty list," "positive int," or "valid
  IBAN."
- A field that must always be in [0, 100]. You don't want `int`; you want
  `Percentage`.

**Sketch — Python.** Three escalating tools: `NewType` for label-only, frozen
dataclass with `__post_init__` for validating constructors that raise, and a
smart constructor returning `Result` for railway-friendly validation.

```python
from dataclasses import dataclass
from typing import NewType, Final
import re

# Label-only — escapes primitive obsession, NO runtime validation.
UserId = NewType("UserId", str)

# Validated, raising — the simple case:
EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        if not EMAIL_RE.match(self.value):
            raise ValueError(f"invalid email: {self.value!r}")

# Validated, Result-returning — preferred for railway code:
@dataclass(frozen=True, slots=True)
class _Email:
    value: str

@dataclass(frozen=True, slots=True)
class InvalidEmail:
    raw: str
    reason: str

def make_email(raw: str) -> Result[_Email, InvalidEmail]:
    if "@" not in raw:
        return Err(tag="err", error=InvalidEmail(raw=raw, reason="missing @"))
    if not EMAIL_RE.match(raw):
        return Err(tag="err", error=InvalidEmail(raw=raw, reason="malformed"))
    return Ok(tag="ok", value=_Email(value=raw.lower()))
```

`def send(to: _Email, body: str)` cannot be called with arbitrary strings. The
_only_ way to get an `_Email` is `make_email`. Same pattern for `Percentage`
(range), `NonEmpty[T]` (non-empty list — `first` becomes total: no `IndexError`
possible), `IBAN`, etc.

**Sketch — F# (the cleanest expression).**

```fsharp
type Email = private Email of string

module Email =
    let create (raw: string) =
        if not (raw.Contains "@") then Error "missing @"
        else Ok (Email (raw.ToLowerInvariant()))
```

`private` makes _only_ the `Email` module able to construct one — outside
callers go through `Email.create`. Python has no module-level visibility;
convention is leading-underscore on the type and code-review enforcement.

**Type-safety notes.**

- `__post_init__` runs after `__init__` and can raise. Frozen dataclasses still
  allow this — raising inside `__post_init__` is the validated-construction
  path.
- `NewType` is _not_ a runtime check. It's purely a static-type label. Use it
  when you want to distinguish `UserId` from `str` in signatures but don't need
  validation. Use a frozen dataclass when you do need validation.
- A smart constructor that returns `Result` is preferable to one that raises,
  because it composes into railway code.

**When NOT to use.**

- Trivial wrappers around `str` or `int` with no validation and no risk of
  confusion. A one-off `customer_name: str` parameter doesn't need a
  `CustomerName` newtype.
- Throwaway scripts. Smart constructors pay off in long-lived code where the
  `Email` flows through dozens of functions.

**Real-world examples.**

- Pydantic models with field validators (`@field_validator`) — every `BaseModel`
  is a smart constructor.
- Django form fields that validate on `clean_<field>`.
- Wlaschin's _Domain Modeling Made Functional_ uses this pattern as the spine of
  every chapter.

**Anti-pattern variant.**

```python
# DON'T: validate at the call site, every time.
def send_email(to: str, body: str) -> None:
    if "@" not in to:
        raise ValueError("invalid email")     # repeated at every call site
    ...

# Smart-constructor refactor: validate once.
def send_email(to: Email, body: str) -> None:
    ...                                       # `Email` is already valid by construction
```

The first form means the validation logic — and the validation bug — is
duplicated everywhere `send_email` is called. The second form makes "you have an
`Email`" mean exactly "you have a validated email."

**References.**

- Wlaschin, _Domain Modeling Made Functional_, ch. 4, "Understanding Types," and
  ch. 6, "Integrity and Consistency in the Domain."
- Granin, _Functional Design and Architecture_, ch. 3, "Domain Modeling and
  Smart Constructors."
- Brady, _Type-Driven Development with Idris_ — totality as a first principle.

---

## Functor / Applicative / Monad

**Intent.** Three abstractions for "things that wrap a value." `map` lifts a
plain function onto the wrapped value; `apply` lifts a wrapped function onto a
wrapped value; `bind` lifts a _wrapped-value-returning_ function.

**Honest take for Python.** You will rarely write a `Functor` or `Monad`
typeclass in Python. The language doesn't reward typeclass programming —
higher-kinded types like `class M[F[_]]` ("a monad over `F`") are not
expressible in mypy or pyright. **The takeaway** is the _shapes_ and the _laws_
— they tell you when an API is well behaved.

**The three laws (informally).**

1. **Functor.** `map(id) == id` and `map(f).map(g) == map(g ∘ f)`.
2. **Applicative.** `apply` lets you combine _independent_ wrapped values; the
   canonical use is accumulating multiple validation errors instead of failing
   fast.
3. **Monad.** `bind` chains _dependent_ steps. The laws (left/right identity,
   associativity) guarantee `bind` composition doesn't depend on grouping —
   i.e., the railway pattern.

**When the shape matters in Python.**

- _Functor._ `Result[T, E].map`, `[f(x) for x in xs]`, `pd.Series.apply`. Use
  whenever you want to transform inside the wrapper without unwrapping.
- _Applicative._ Validating several independent inputs and accumulating _all_
  errors. `bind` is fail-fast; applicative validation collects.
- _Monad._ The next step depends on the previous one (railway pattern, asyncio
  chains).

**Sketch — Python (Functor for `Result`).**

```python
def map_r[T, U, E](r: Result[T, E], fn: Callable[[T], U]) -> Result[U, E]:
    match r:
        case Ok(value=v):
            return Ok(tag="ok", value=fn(v))
        case Err() as e:
            return e
        case _ as never:
            assert_never(never)

# Functor laws hold:
#   map_r(r, id) == r
#   map_r(map_r(r, f), g) == map_r(r, lambda x: g(f(x)))
```

There is no Python typeclass that says "this is a Functor"; the abstraction
lives in the shape and the laws, not in a class hierarchy.

**Applicative validation — the practical case.** Collect errors, don't fail
fast. Pydantic and `attrs.validators` do this internally; here is the
hand-rolled version:

```python
@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    reason: str

type Validation[T] = list[FieldError] | T

def validate_person(raw: dict[str, str]) -> Validation[Person]:
    errors: list[FieldError] = []
    name_v  = validate_name(raw.get("name", ""))
    email_v = validate_email(raw.get("email", ""))
    age_v   = validate_age(raw.get("age", ""))
    for v in (name_v, email_v, age_v):
        if isinstance(v, list):
            errors.extend(v)
    if errors:
        return errors
    assert not isinstance(name_v, list)
    assert not isinstance(email_v, list)
    assert not isinstance(age_v, list)
    return Person(name=name_v, email=email_v, age=age_v)
```

**Sketch — Haskell (where the abstraction is native).**

```haskell
instance Applicative Result where
    pure = Ok
    Ok f   <*> Ok x   = Ok (f x)
    Err es <*> Err fs = Err (es ++ fs)
    Err es <*> _      = Err es
    _      <*> Err es = Err es
```

That's the _whole_ applicative instance — Python can't get there without
higher-kinded types.

**When NOT to use.**

- You're writing your own `Monad` typeclass in Python. Stop — pyright won't
  follow it. Use `match`-on-`Result` and `bind_r`.
- You don't need _both_ laws _and_ `map`/`bind`. Then it's not a monad, it's a
  class with two methods. Just write the methods.

**Real-world examples.**

- `returns` library — `Functor`, `Applicative`, `Monad` for `Result`, `Maybe`,
  `Future`, `IO`.
- `expression` library — F#-flavored Python with `Result`, `Option`, `Try`.
- Haskell's `mtl` — the canonical monad-transformer library.

**Anti-pattern variant.** Simulating Haskell's do-notation in Python with
generators. Pyright can't follow the yield types; you reinvent `for/yield` with
worse ergonomics. Use explicit `if isinstance(r, Err): return r` or `returns`.

**References.**

- Hutton, _Programming in Haskell_, chs. 12-16, "Monads and More" / "Effects."
- Granin, _Functional Design and Architecture_, ch. 6, "Free Monads and Effects
  in Haskell" (read for the _intuition_; do not port wholesale).
- Wlaschin, "Understanding Functor and Monad with a Bag of Peanuts,"
  fsharpforfunandprofit.com.

---

## When to Use What

A short decision tree.

1. **A function may fail with one well-known reason** → return `T | None`. Done.
2. **A function may fail with several reasons the caller distinguishes** →
   return `Result[T, ErrorADT]`.
3. **Several `Result`-returning steps in a row, each depending on the previous**
   → write the chain procedurally with `if isinstance(r, Err): return r`. Reach
   for `returns` or a custom `bind` only when 3+ such chains accumulate.
4. **Several `Result`-returning validations of _independent_ inputs** →
   applicative-style error accumulation. Use `pydantic.BaseModel` for the common
   case; hand-roll for tight control.
5. **A primitive type at a boundary that matters** (email, money, percentage,
   user id) → smart constructor returning `Result` plus a `frozen=True` newtype.
6. **Closed set of variants in the domain** → ADT (frozen-dataclass tagged
   union). Match exhaustively with `assert_never`.
7. **All values that flow through this region of code should be immutable** →
   `frozen=True`, `slots=True`, `tuple` instead of `list` for fields,
   `Sequence`/`Mapping` in signatures.
8. **A 3+-step transformation pipeline** → write the chain explicitly. Reach for
   `pipe` / `Pipe[T]` / `reduce` only if the pipeline is itself data (stages
   declared dynamically).
9. **Deep nested updates of immutable values** → `dataclasses.replace` ladder up
   to two levels; build a `Lens[S, A]` if four+ deep paths share an update
   target.
10. **You're tempted to write `Monad[F[_]]`** → don't.

---

## Review Checklist

Use during code review. Items map to anchors above.

1. Does every domain failure return `Result` rather than raise?
   ([Result / Either](#result--either))
2. Are `Result.match` blocks closed with `assert_never`? Adding a variant must
   break the build. ([Algebraic Data Types](#algebraic-data-types))
3. Are value objects `frozen=True` with `tuple` fields, not `list`?
   ([Immutability](#immutability))
4. Are public function signatures using `Sequence`/`Mapping`, reserving
   `list`/`dict` for internal builders? ([Immutability](#immutability))
5. Are primitives at boundaries wrapped in newtypes with smart constructors?
   ([Totality and Smart Constructors](#totality-and-smart-constructors))
6. Are sum types tagged with `Literal[...]`, so pyright can narrow inside
   `match`? ([Algebraic Data Types](#algebraic-data-types))
7. For Pydantic-heavy stacks: are unions annotated with `Discriminator(...)`, or
   is Pydantic doing slow trial-parsing?
   ([Algebraic Data Types](#algebraic-data-types))
8. Is partial application hiding a hard dependency from the call site? Replace
   with explicit injection.
   ([Currying and Partial Application](#currying-and-partial-application))
9. For long railway chains: are _all_ errors a single union type, or is the code
   juggling incompatible error types via try/except?
   ([Railway-Oriented Programming](#railway-oriented-programming))
10. Are there nested `replace` ladders >3 levels? Either redesign the data or
    build a typed `Lens`. ([Lenses and Optics](#lenses-and-optics))
