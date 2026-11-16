# Code smell baseline

Used by the "Design" lane. Adapted from Matt Pocock's `code-review` skill (MIT, https://github.com/mattpocock/skills), which takes the smells from Martin Fowler's _Refactoring_, chapter 3.

Two rules bind the list:

- The repo's documented rules win. Where a repo rule, `CLAUDE.md`, `AGENTS.md` or `REVIEW.md` endorses something below, drop the smell.
- Each smell is a judgment call, written as "possible Feature Envy" with the hunk quoted. It goes in Consider or Noted, never Act on, and anything lint or the type check already enforces is skipped.

Match each one against the diff. The arrow gives the usual fix.

- Mysterious Name: a function, variable or type whose name doesn't say what it does or holds. → rename it; if no honest name comes, the design is unclear.
- Duplicated Code: the same logic shape in more than one hunk or file of the change. → extract the shared shape and call it from both, subject to the "Design" lane's rule on when two callers should stay apart.
- Feature Envy: a method that reads another object's data more than its own. → move the method next to that data.
- Data Clumps: the same few fields or parameters keep travelling together. → bundle them into one type and pass that.
- Primitive Obsession: a primitive or string standing in for a domain concept. → give the concept its own small type.
- Repeated Switches: the same `switch` or `if` cascade on the same type in several places of the change. → polymorphism, or one map both places share.
- Shotgun Surgery: one logical change forces scattered edits across many files. → gather what changes together into one module.
- Divergent Change: one file or module edited for several unrelated reasons. → split it so each module changes for one reason.
- Speculative Generality: abstractions, parameters or hooks for needs the ticket doesn't have. → delete them and inline until a real need shows up.
- Message Chains: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- Middle Man: a class or function that mostly delegates onward. → remove it and call the real target.
- Refused Bequest: a subclass that ignores or overrides most of what it inherits. → drop the inheritance and use composition.
