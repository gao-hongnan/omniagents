# Strategy

## Intent

Define a family of algorithms, encapsulate each one, and make them interchangeable. Strategy lets the algorithm vary independently from the clients that use it.

## Use When

Use Strategy whenever behavior varies along an axis the caller should control: sort order, pricing rule, retry policy, compression algorithm, or serialization format. If the variation is "what code runs," you probably have a Strategy.

## Prefer A Simpler Python Shape When

Do not pre-invent an interface when only one strategy exists. Write the concrete code and extract a strategy when the second case shows up. If the strategy has zero parameters and no behavior beyond returning a fixed value, it is a constant, not a strategy.

## Structure

Caller delegates the algorithm to the strategy without knowing which strategy it is.

```mermaid
sequenceDiagram
    participant C as checkout
    participant S as PricingStrategy
    participant O as Order
    C->>S: price(order)
    S->>O: items
    O-->>S: line items
    S-->>C: total cents
    Note over C,S: strategy can be standard, bulk_discount, or membership(20); caller does not care
```

## Strict-Typed Python Sketch

A plain `Callable` is the right strategy in Python. Save `Protocol` for when the strategy has state, multiple methods, or associated data.

```python
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LineItem:
    sku: str
    quantity: int
    price_cents: int


@dataclass(frozen=True, slots=True)
class Order:
    items: tuple[LineItem, ...]


type PricingStrategy = Callable[[Order], int]


def standard_pricing(order: Order) -> int:
    return sum(item.price_cents * item.quantity for item in order.items)


def bulk_discount_pricing(order: Order) -> int:
    total = standard_pricing(order)
    return total * 9 // 10 if total > 10_000 else total


def membership_pricing(member_discount_pct: int) -> PricingStrategy:
    def price(order: Order) -> int:
        total = standard_pricing(order)
        return total * (100 - member_discount_pct) // 100

    return price


def checkout(order: Order, price: PricingStrategy) -> int:
    return price(order)
```

Use a Protocol when the strategy has setup, teardown, shared state, or multiple related methods.

```python
from typing import Protocol


class CompressionStrategy(Protocol):
    extension: str
    def compress(self, data: bytes) -> bytes: ...
    def decompress(self, data: bytes) -> bytes: ...


class GzipStrategy:
    extension = ".gz"

    def compress(self, data: bytes) -> bytes:
        import gzip
        return gzip.compress(data)

    def decompress(self, data: bytes) -> bytes:
        import gzip
        return gzip.decompress(data)


class ZstdStrategy:
    def __init__(self, level: int = 3) -> None:
        self.extension = ".zst"
        self._level = level

    def compress(self, data: bytes) -> bytes:
        import zstandard
        return zstandard.ZstdCompressor(level=self._level).compress(data)

    def decompress(self, data: bytes) -> bytes:
        import zstandard
        return zstandard.ZstdDecompressor().decompress(data)
```

When strategy configuration crosses a boundary, validate the configuration with Pydantic, then construct the strategy from it. Do not make the strategy callable itself a `BaseModel`.

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated


class RetryPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_attempts: Annotated[int, Field(ge=1, le=10)]
    base_delay_s: Annotated[float, Field(gt=0, le=60.0)]
    backoff_multiplier: Annotated[float, Field(ge=1.0, le=10.0)] = 2.0


def make_retry_strategy(policy: RetryPolicy) -> Callable[[int], float]:
    def delay_for(attempt: int) -> float:
        return policy.base_delay_s * (policy.backoff_multiplier ** (attempt - 1))

    return delay_for
```

Rust contrast: when strategies form a closed set, Rust prefers an `enum` over `Box<dyn Trait>`.

```rust
enum CompressionStrategy {
    Gzip,
    Zstd { level: i32 },
}

impl CompressionStrategy {
    fn compress(&self, data: &[u8]) -> Vec<u8> {
        match self {
            Self::Gzip => gzip::compress(data),
            Self::Zstd { level } => zstd::compress(data, *level),
        }
    }
}
```

In Python, the analogue is discriminated union plus `match` for closed strategies, and `Protocol` for open ones. Closed sets get exhaustiveness; open sets get extensibility.

## Type-Safety Notes

`type PricingStrategy = Callable[[Order], int]` documents the shape at every call site. Protocols earn their cost when the strategy has multiple methods, configuration, or state. Avoid creating a Protocol with one `apply()` method; that is just a `Callable` with extra ceremony.

## Common Misuse

A Strategy hierarchy with one concrete class and a comment promising flexibility. Either delete the abstraction or commit to adding the second strategy now.

## Real-World Examples

- `sorted(items, key=lambda x: x.priority)`: `key` is a Strategy.
- `requests.Session(adapter=HTTPAdapter(...))`: the adapter is the connection-handling Strategy.
- `pandas.DataFrame.merge(how="left" | "right" | "inner" | "outer")`: internally dispatched by Strategy.
- `re.sub(pattern, repl, ...)` where `repl` is a function: Strategy for replacement.

## References

- Gamma et al., *Design Patterns* (1994), pp. 315-323.
- Refactoring Guru, [Strategy](https://refactoring.guru/design-patterns/strategy).
- Freeman and Robson, *Head First Design Patterns*, 2nd ed., ch. 1.
