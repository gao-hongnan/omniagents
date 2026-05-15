---
name: docstrings
description: >-
  Use when writing or reviewing Python docstrings for public modules,
  classes, functions, methods, properties, generators, overloads, doctest
  examples, or generated Sphinx API documentation, especially when choosing
  NumPy vs Sphinx style or deciding which Parameters, Returns, Yields,
  Raises, Warns, Attributes, Notes, See Also, and Examples sections belong.
when_to_use: >-
  Trigger for Python public API documentation, numpydoc / Sphinx Napoleon
  output, missing or noisy docstrings, doctest examples, properties,
  dataclasses, Pydantic models, generators, async APIs, overloads,
  deprecated APIs, module docstrings, or reviews where docstrings repeat type
  annotations instead of documenting semantics, invariants, side effects, and
  edge cases.
disable-model-invocation: false
user-invocable: true
allowed-tools: []
model: inherit
paths:
  - "**/*.py"
  - "**/docs/**/*.rst"
  - "**/docs/**/*.md"
  - "**/pyproject.toml"
shell: bash
---

# Python Docstring Convention

The default style is **NumPy docstrings rendered through Sphinx Napoleon**.
Public APIs carry structured docstrings when the name alone does not explain
the contract. Type annotations are the source of truth for static types;
docstrings document semantics, invariants, side effects, examples, and
interface-level exceptions.

This policy is anchored to [PEP 257](https://peps.python.org/pep-0257/) for
Python docstring placement and summary conventions, the
[numpydoc style guide](https://numpydoc.readthedocs.io/en/stable/format.html)
for NumPy section structure, and
[Sphinx Napoleon](https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html)
for rendered documentation behavior.

Prefer a short, useful docstring over a complete but noisy one. Omit sections
that do not apply.

## Baseline Rules

- Public means no leading underscore: public modules, classes, functions,
  methods, properties, dataclass fields, and Pydantic model fields. Sphinx
  autodoc can override underscore-based visibility with `:meta public:` /
  `:meta private:`, but do that only when the project already relies on those
  markers.
- Private helpers do not need docstrings unless they encode a non-obvious
  invariant that future maintainers must preserve.
- Use one style per project. Prefer NumPy style unless the project already
  consistently uses Sphinx field-list docstrings. Napoleon parses NumPy and
  Google style into reStructuredText before autodoc renders it.
- The summary line is one sentence in imperative or descriptive voice. It
  starts immediately after the opening triple quote and fits on one logical
  line when practical; this follows PEP 257's one-line docstring convention.
- The extended summary explains why the API exists or what contract is
  surprising. Do not repeat the function name in prose.
- Doctest examples must be runnable with `uv run python -m doctest <module>.py`
  unless the project has a dedicated doctest target. Python's `doctest`
  module executes interactive examples and verifies that they work as shown.
- Mark deprecated APIs near the top with `.. version-deprecated:: <version>`
  and a migration note. In Sphinx 9+, `version-deprecated` is the current
  directive name; `deprecated` remains an alias for older docs.

## NumPy Style

Use section names with underlines of matching length. Keep this order when
sections apply:

1. Summary line
2. Extended summary
3. `Parameters`
4. `Attributes`
5. `Returns` / `Yields`
6. `Raises`
7. `Warns`
8. `See Also`
9. `Notes`
10. `Examples`

```python
def divmod_safe(numerator: int, denominator: int) -> tuple[int, int]:
    """Return the quotient and remainder from integer division.

    Wraps ``divmod`` with an explicit zero-denominator contract so callers can
    recover without inspecting implementation details.

    Parameters
    ----------
    numerator
        Dividend used for integer division.
    denominator
        Divisor. Must be non-zero.

    Returns
    -------
    tuple[int, int]
        ``(quotient, remainder)`` as returned by ``divmod``.

    Raises
    ------
    ZeroDivisionError
        If ``denominator`` is zero.

    Examples
    --------
    >>> divmod_safe(7, 3)
    (2, 1)
    """
    return divmod(numerator, denominator)
```

### Type Information

- Do not duplicate parameter types when annotations are present. Write
  `name`, not `name : str`, unless the parameter is unannotated for a specific
  reason.
- In NumPy style, keep a return item/type line under `Returns` / `Yields` so
  Sphinx and numpydoc render the section correctly. The prose below that line
  explains semantics.
- For multiple return values, document names and meanings when the tuple is
  not self-evident.
- Do not describe `TypeVar`, `Literal`, or `Annotated` mechanics in prose.
  Explain the user-visible contract.

Wrong:

```python
def get(self, key: str) -> int | None:
    """Get a value.

    Parameters
    ----------
    key : str
        The key as a string.

    Returns
    -------
    int | None
        The int or None.
    """
```

Right:

```python
def get(self, key: str) -> int | None:
    """Look up a value without mutating cache order.

    Parameters
    ----------
    key
        Cache key. A miss is silent.

    Returns
    -------
    int | None
        Stored value when present, otherwise ``None``.
    """
```

## Required Sections By API Kind

- **Public function or method**: summary; `Parameters` when it accepts
  arguments other than `self` / `cls`; `Returns` when it returns a value;
  `Raises` for exceptions that are part of the interface; `Examples` for
  non-obvious behavior.
- **Generator or async generator**: use `Yields`, not `Returns`, for yielded
  values. Mention cleanup or cancellation semantics in `Notes` when relevant.
- **Public class**: summary and extended summary when useful; `Attributes`
  for public instance attributes; `Examples` for construction and common use.
  Method-specific behavior belongs on the method.
- **Dataclass or Pydantic model**: document public fields in `Attributes`
  unless the class is purely internal. Put validation constraints in prose
  when they affect callers.
- **Property**: docstring goes on the getter. Use a short sentence unless the
  property computes, caches, normalizes, or can raise.
- **Module**: one paragraph explaining why the module exists and where it
  fits. Document module-level public constants in an `Attributes` section or
  inline after the assignment; do not mix both styles in one module.
- **Overloads**: place the public docstring on the implementation, not on
  each `@overload` stub. Explain the dispatch rule once.

## Examples

Doctest examples use interactive-prompt style and include expected output.
Keep them short enough to scan in review.

```python
"""
Examples
--------
>>> cache = LRUCache[str, int](maxsize=2)
>>> cache.set("a", 1)
>>> cache.get("a")
1
>>> cache.get("missing") is None
True
"""
```

Avoid examples that silently pass without asserting anything:

```python
"""
Examples
--------
>>> result = expensive_operation()
"""
```

## Sphinx Field-List Style

Use this only when the consuming project already uses field-list docstrings.
Do not mix with NumPy style in the same project.

```python
def divmod_safe(numerator: int, denominator: int) -> tuple[int, int]:
    """Return the quotient and remainder from integer division.

    :param numerator: Dividend used for integer division.
    :param denominator: Divisor. Must be non-zero.
    :returns: ``(quotient, remainder)`` as returned by ``divmod``.
    :raises ZeroDivisionError: If ``denominator`` is zero.
    """
    return divmod(numerator, denominator)
```

## Anti-Patterns

- **Empty section placeholders.** Omit sections that do not apply. Never write
  `Raises\n------\nNone`.
- **Annotation repetition.** Do not write parameter prose that merely restates
  `key: str` or `items: Iterable[ItemT]`.
- **Docstring-as-comment.** `"""Get a value."""` on a method named `get` adds
  no information.
- **Implementation narration.** Do not document private steps unless they are
  part of the public contract.
- **Unrunnable doctests.** Examples without expected output or setup mislead
  reviewers and documentation readers.
- **Mixed styles.** Do not combine NumPy sections with Sphinx `:param:` tags.
- **Over-documenting obvious internals.** A private one-line helper should not
  grow a public-API docstring just to satisfy a template.

## References

- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/):
  baseline Python rules for where docstrings live, one-line summaries,
  multi-line docstrings, class docstrings, and attribute docstrings.
- [numpydoc Style Guide](https://numpydoc.readthedocs.io/en/stable/format.html):
  source for NumPy section structure, including `Parameters`, `Returns`,
  `Yields`, `Raises`, `Warns`, `See Also`, `Notes`, and `Examples`.
- [Sphinx Napoleon](https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html):
  parser that converts NumPy and Google style docstrings into
  reStructuredText for Sphinx.
- [Sphinx autodoc](https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html):
  source for how Sphinx imports objects, reads docstrings, handles public /
  private metadata, and renders type hints.
- [Sphinx reStructuredText directives](https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html):
  source for version-change directives such as `version-deprecated`.
- [Python `doctest`](https://docs.python.org/3/library/doctest.html):
  source for executable interactive examples in docstrings and documentation.

## Freshness

This skill is project policy, not a complete upstream reference. When applying
it to unfamiliar APIs, version-sensitive behavior, tool/checker disagreement,
or anything that may have changed since the skill was written, verify current
behavior against primary docs. Prefer Context7 MCP when available. If it is
unavailable, use web search restricted to official sources.

Primary sources:

- [PEP 257](https://peps.python.org/pep-0257/)
- [numpydoc](https://numpydoc.readthedocs.io/en/stable/format.html)
- [Sphinx Napoleon](https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html)
- [Sphinx autodoc](https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html)
- [Python doctest](https://docs.python.org/3/library/doctest.html)
