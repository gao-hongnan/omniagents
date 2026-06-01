# Behavioral GoF Patterns

Use these pages when behavior, workflow, notification, dispatch, state
transitions, or algorithm choice is the design problem.

| Pattern                                               | Use when                                                                                    |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| [Chain of Responsibility](chain-of-responsibility.md) | You need a configurable handler pipeline with short-circuiting.                             |
| [Command](command.md)                                 | You need to queue, audit, retry, dispatch, or undo an action.                               |
| [Interpreter](interpreter.md)                         | You need to evaluate a small DSL represented as an AST.                                     |
| [Iterator](iterator.md)                               | You need lazy traversal without exposing representation.                                    |
| [Mediator](mediator.md)                               | You need to coordinate many participants without many-to-many references.                   |
| [Memento](memento.md)                                 | You need opaque save/restore tokens for undo or snapshots.                                  |
| [Observer](observer.md)                               | You need decoupled fan-out notification.                                                    |
| [State](state.md)                                     | Behavior depends on state and legal transitions.                                            |
| [Strategy](strategy.md)                               | The caller should choose an interchangeable algorithm.                                      |
| [Template Method](template-method.md)                 | A fixed workflow has a few varying steps, usually better injected as composition in Python. |
| [Visitor](visitor.md)                                 | Many operations run over a fixed type hierarchy.                                            |

Interpreter is part of the GoF catalogue but is not listed in Refactoring Guru's
public catalog list.
