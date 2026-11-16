---
name: java-practices
description: Java check commands and gotchas on top of engineering-practices. Covers the formatter, SpotBugs, Maven and Gradle tests, PIT mutation testing (JUnit 5 needs a temporary build change), PMD complexity and dead-code rules, plus BigDecimal, exceptions, clocks and exhaustive switches. Use whenever you write, change, test or review Java code, a pom.xml or a Gradle build, together with engineering-practices.
---

# Java practices

`engineering-practices` holds the rules that hold in any language; this skill adds the Java commands and the gotchas a strong model still gets wrong. The repo's own build and CI win. For a security pass, load `security-review`.

## Checks

Run what the build configures the way CI runs it. Use these where the repo has none.

| Check | Command |
|---|---|
| Format and lint | The repo's formatter (`mvn spotless:check` or `./gradlew spotlessCheck` where Spotless is configured); SpotBugs without a pom change: `mvn compile com.github.spotbugs:spotbugs-maven-plugin:check` |
| Types | The compiler: `mvn compile`, `./gradlew compileJava` |
| Tests | `mvn test -Dtest=Class#method` (add `-pl <module>` in a multi-module build), `./gradlew test --tests Class`; property-based tests with jqwik where the repo has it |
| Mutation | PIT, see "Mutation testing" below |
| Complexity | PMD `CognitiveComplexity` (default 15) and `CyclomaticComplexity` (default 10) from `category/java/design.xml`: `pmd check -d src/main/java -f text -R category/java/design.xml/CognitiveComplexity,category/java/design.xml/CyclomaticComplexity` (the PMD CLI is a global tool; ask before installing) |
| Dead code | PMD `UnusedPrivateMethod`, `UnusedPrivateField` and `UnusedLocalVariable` from `category/java/bestpractices.xml`, run the same way |
| Architecture boundaries | ArchUnit tests, where the repo has them |

## Mutation testing

Maven runs a plugin by its coordinates without a `pom.xml` change:

```bash
mvn test-compile org.pitest:pitest-maven:mutationCoverage -DtargetClasses='com.example.billing.*' -DtargetTests='com.example.billing.*'
```

PIT finds JUnit 5 tests only through `pitest-junit5-plugin`, a plugin dependency that has to go in the `pom.xml` (or the Gradle build, which also needs the PIT plugin itself). Adding it is a build change: add it for the local run and restore the file from a backup copy before committing, unless the team agrees to keep it. Reports land in `target/pit-reports/`.

Done when every surviving mutant in the changed classes is killed by a new assertion or noted as equivalent.

## Java gotchas

- Build `BigDecimal` from a string (`new BigDecimal("0.10")`) and compare with `compareTo`; `equals` also compares scale, so `2.0` and `2.00` differ.
- Measure durations with `System.nanoTime()`; read the current time from an injected `Clock` so tests can control it.
- Switch over an enum as a switch expression (`return switch (status) { ... };`), and over a sealed interface with patterns, with no `default` branch, so a new case fails to compile. A plain `switch` statement over an enum isn't checked for exhaustiveness. Pattern switches need Java 21; check the repo's release first.
- Wrap a checked exception with its cause (`throw new PaymentFailedException(orderId, e)`). After catching `InterruptedException`, restore the flag with `Thread.currentThread().interrupt()` or rethrow.
- Return `Optional` instead of `null` from lookups, and never call `get()` without a check; don't use `Optional` for fields or parameters. A lookup with no results returns an empty collection, never `null`.
- Use records for DTOs and value objects where the repo's Java version has them (16 and later); JPA entities can't be records.
