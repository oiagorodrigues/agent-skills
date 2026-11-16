# Python, Java and Rust services

For Python outside Django (FastAPI, Flask, ETL jobs, Lambdas, scripts) and for Java and Rust services. Read the build file first (`pyproject.toml`, `pom.xml`, `build.gradle`, `Cargo.toml`) to learn the framework and versions; don't assume them. Sink lists adapted from getsentry/skills `security-review` (Apache-2.0, https://github.com/getsentry/skills) and the anthropics/claude-plugins-official `security-guidance` patterns (Apache-2.0, https://github.com/anthropics/claude-plugins-official).

## Python

- Commands: `subprocess` with `shell=True` or a single string built from input, `os.system`, `os.popen`. Use an argument list without a shell.
- Code and object loading: `eval`, `exec`, `pickle`, `cPickle`, `dill`, `joblib.load`, `marshal`, `shelve`, `torch.load` without `weights_only=True`, `yaml.load` without `SafeLoader` (`yaml.safe_load` is fine) on data from users, queues, caches or S3 objects others can write.
- XML from outside: stdlib `xml.etree`, `minidom` and `lxml` with default settings allow entity attacks. Use `defusedxml`.
- Archives: `tarfile.extractall` without `filter="data"`, and zip members with `..` or absolute paths.
- SQL: f-strings or `%` in `cursor.execute`, SQLAlchemy `text(f"...")`. Bound parameters are safe.
- Templates: Jinja2 `Environment(autoescape=False)` rendering HTML, or `Template(user_string)` (server-side template injection).
- FastAPI: auth as a dependency on every router or route that needs it, `response_model` so internal fields don't leak, Pydantic models with `extra="allow"` bound to ORM writes (mass assignment).
- Outbound HTTP: `verify=False`, no `timeout`, URLs from users (SSRF).
- Randomness and hashing: `random` for tokens (use `secrets`), `md5` or `sha1` for passwords. Checksums and cache keys with `md5` are fine.
- ETL and data jobs: connection strings with passwords in logs or error messages, PII copied into tables or buckets with broader access than the source, credentials in job arguments that show up in process lists or Airflow UI.
- Lambdas and queue consumers: the event body is untrusted. Fields like `company_id` or `user_id` inside it are claims unless a signed envelope or the trigger's configuration binds them.

## Java

- SQL: string concatenation in JDBC `Statement`, JPA `createQuery("..." + x)`, `createNativeQuery`, Spring Data `@Query` built with concatenation. `PreparedStatement` and named parameters are safe.
- Deserialization: `ObjectInputStream.readObject` on untrusted bytes; Jackson `enableDefaultTyping`, `activateDefaultTyping` or `@JsonTypeInfo(use = JsonTypeInfo.Id.CLASS)` on input types; XStream; SnakeYAML `new Yaml().load` before 2.0 without `SafeConstructor`. These lead to code execution through gadget classes.
- XML: `DocumentBuilderFactory`, `SAXParserFactory`, `XMLInputFactory` and `TransformerFactory` without disabling DTDs and external entities.
- Spring Security: new paths under `permitAll()`, matcher order that lets a broad rule win, `csrf().disable()` with cookie sessions, service methods without `@PreAuthorize` when the project uses method security, actuator exposure (`management.endpoints.web.exposure.include=*`, `/actuator/env`, `/actuator/heapdump`).
- Mass assignment: binding request bodies or `@ModelAttribute` straight onto JPA entities. Use DTOs, or `@InitBinder` with allowed fields.
- Expression and template injection: `SpelExpressionParser.parseExpression(input)`, Thymeleaf `th:utext` and `__${...}__` preprocessing with user data, OGNL.
- Commands and files: `Runtime.exec` with a concatenated string, `new File(base, userName)` without a canonical-path check.
- Crypto and TLS: `java.util.Random` for tokens (use `SecureRandom`), trust-all `X509TrustManager` or `HostnameVerifier`, `Cipher.getInstance("AES")` (defaults to ECB).
- Logging: Log4j 2 older than 2.17.1 (Log4Shell family), user input written to logs without neutralizing newlines, PII in log lines.

## Rust

- SQL: `format!` into `sqlx::query(...)` or Diesel `sql_query`. `sqlx::query!` and `.bind(...)` are parameterized.
- Commands: `Command::new("sh").arg("-c")` with interpolated input. Pass arguments with `.arg` and no shell.
- Paths: `base.join(user_path)` replaces `base` when `user_path` is absolute, and `..` still escapes. Canonicalize and check `starts_with(base)`.
- Panics on input (`unwrap`, `expect`, indexing, slicing a `str` off a char boundary) end the request or task, and the whole process when the profile sets `panic = "abort"`. That's a denial-of-service finding when an unauthenticated caller can trigger it.
- Integers: `as` casts truncate silently, and arithmetic wraps in release builds unless `overflow-checks = true`. Check sizes, offsets and money that come from input.
- `unsafe`, FFI, `transmute`, `from_raw_parts` and `get_unchecked` reached by input-derived lengths or indexes. Prove undefined behavior with `cargo +nightly miri test` on a test that feeds the input.
- Mass assignment: a request body deserialized straight into a struct that is written to the database, carrying fields such as `role` or `company_id`. Deserialize into a request type and copy the allowed fields.
- TLS and randomness: reqwest `danger_accept_invalid_certs(true)` or `danger_accept_invalid_hostnames(true)`; `fastrand` or `SmallRng` for tokens (use `OsRng` or `rand::rng()`/`thread_rng()`).

## Proving it

Write a unit or integration test that feeds the payload to the entry point (FastAPI `TestClient`, Flask test client, Spring `MockMvc`, a Rust integration test under `tests/`) with dummy data. For deserialization, show that attacker-controlled bytes reach the call; don't build a gadget chain.
