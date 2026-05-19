# Iterator

## Intent

Provide a way to access the elements of an aggregate object sequentially without exposing its underlying representation. Decouple traversal from data structure.

## Use When

Almost never as a manual class. Python made Iterator into syntax. Reach for the explicit shape only when traversal is stateful in ways `yield` cannot express cleanly, such as interleaved producers or bidirectional cursors, or when implementing a custom mapping or sequence type.

## Prefer A Simpler Python Shape When

For most cases, write `def walk() -> Iterator[ItemT]: yield from something`. Anything `yield from` already solves does not need an OO Iterator class. If a caller needs a list, they can call `list(walk())`.

## Structure

The container returns a fresh generator for each traversal. The rare manual cursor owns traversal state explicitly.

## Strict-Typed Python Sketch

Generator-based traversal of a binary tree:

```python
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class BinaryTree[ItemT]:
    value: ItemT
    left: "BinaryTree[ItemT] | None" = None
    right: "BinaryTree[ItemT] | None" = None

    def in_order(self) -> Iterator[ItemT]:
        if self.left is not None:
            yield from self.left.in_order()
        yield self.value
        if self.right is not None:
            yield from self.right.in_order()
```

Manual class form for the rare bidirectional-cursor case:

```python
class HistoryCursor[ItemT]:
    def __init__(self, items: list[ItemT]) -> None:
        self._items = items
        self._index = -1

    def forward(self) -> ItemT:
        if self._index + 1 >= len(self._items):
            raise StopIteration
        self._index += 1
        return self._items[self._index]

    def backward(self) -> ItemT:
        if self._index <= 0:
            raise StopIteration
        self._index -= 1
        return self._items[self._index]
```

## Type-Safety Notes

Annotate generators as `Iterator[ItemT]` or `Generator[ItemT, None, None]` when you need to send values in. PEP 695's `def f[ItemT](...) -> Iterator[ItemT]:` is the cleanest generic function form. Avoid annotating with `list[ItemT]` "just in case" the caller wants a list; that materializes the whole sequence and defeats lazy semantics.

## Common Misuse

A class with `__iter__(self)` returning `self` and `__next__` walking an internal list, then trying to iterate it twice. Once exhausted, manual iterators do not restart, and the second `for` loop sees nothing. Make the container iterable by defining `__iter__` to return a fresh generator.

## Real-World Examples

- `os.walk(path)` is a generator-based iterator returning `(dirpath, dirnames, filenames)`.
- `itertools.chain`, `groupby`, and `tee` are iterator combinators.
- `csv.reader` returns an iterator over rows; `pandas.DataFrame.iterrows()` is an iterator over `(index, row)` tuples.

## References

- Gamma et al., *Design Patterns* (1994), pp. 257-271.
- Refactoring Guru, [Iterator](https://refactoring.guru/design-patterns/iterator).
- Python documentation for `collections.abc.Iterator`.
