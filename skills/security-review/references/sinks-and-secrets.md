# Sinks, secrets and PII in logs

Grep the added lines of the diff for these, then trace each hit from source to sink. A hit is a lead to investigate, never a finding by itself: `innerHTML = "<b>Loading</b>"` and `md5(file_bytes)` are fine.

Sink list from the anthropics/claude-plugins-official `security-guidance` plugin patterns (Apache-2.0, https://github.com/anthropics/claude-plugins-official) and getsentry/skills `security-review` quick patterns (Apache-2.0, https://github.com/getsentry/skills).

```bash
# Keeps the file (+++) and hunk (@@) headers so each hit has a file and line number.
git diff -U0 <base>...HEAD | grep -E '^\+\+\+ |^@@|^\+.*(<pattern>)'
```

## Dangerous sinks

| Class | Patterns |
|---|---|
| Code execution | `eval(`, `exec(`, `new Function`, `setTimeout("`, `vm.run`, `child_process.exec`, `execSync(`, `os.system`, `os.popen`, `from os import system`, `shell=True`, `Runtime.getRuntime().exec`, `exec.Command("sh"` or `"bash"` |
| Deserialization | `pickle.load`, `pickle.loads`, `Unpickler`, `joblib.load`, `pandas.read_pickle`, `numpy.load(..., allow_pickle=True)`, `marshal.loads`, `shelve.open`, `torch.load(` without `weights_only=True`, `yaml.load(` without `SafeLoader`, `yaml.unsafe_load`, `ObjectInputStream`, `activateDefaultTyping`, `enableDefaultTyping`, `XStream` |
| XML | `xml.etree`, `minidom`, `lxml.etree.parse`, `DocumentBuilderFactory`, `SAXParserFactory`, `XMLInputFactory` |
| HTML | `v-html`, `.innerHTML =`, `.outerHTML =`, `insertAdjacentHTML(`, `document.write`, `dangerouslySetInnerHTML`, `\|safe`, `mark_safe(`, `autoescape off`, `th:utext`, `<script src="http` without `integrity=` |
| SQL | `.raw(`, `.extra(`, `RawSQL(`, `cursor.execute(f"`, `execute("...` with `%` or `+`, `text(f"`, `createQuery(` or `createNativeQuery(` with `+` |
| TLS and crypto | `verify=False`, `rejectUnauthorized: false`, `NODE_TLS_REJECT_UNAUTHORIZED`, `InsecureSkipVerify: true`, `ssl._create_unverified_context`, `check_hostname = False`, `createCipher(`, `MODE_ECB`, `AES/ECB`, `Cipher.getInstance("AES")`, `md5(` or `sha1(` near passwords, `random.` or `Math.random()` near token or code generation |
| Redirects and URLs | `redirect(request.`, `HttpResponseRedirect(`, `router.push(route.query`, `window.location =`, `requests.get(` or `$fetch(` with a variable URL |
| GitHub Actions | `pull_request_target`, `workflow_run`, `${{ github.event.` or `${{ github.head_ref` inside `run:` or `script:` |

## Secrets

Patterns: `AKIA[0-9A-Z]{16}`, `-----BEGIN [A-Z ]*PRIVATE KEY`, `sk-[A-Za-z0-9_-]{20,}`, `sk-ant-`, `ghp_`, `gho_`, `github_pat_`, `xox[abprs]-`, `AIza[0-9A-Za-z_-]{35}`, `password\s*[:=]\s*['"][^'"]+`, `SECRET_KEY\s*=\s*['"]`, and secret-looking defaults such as `getenv("API_KEY", "<literal>")`. Also new files named `.env*`, `*.pem`, `*.key`, `*.p12`, `credentials.json` or `*.tfvars`.

- A secret committed in any commit of the branch is leaked even if a later commit removes it, because history keeps it. The fix is rotation, not deletion; say so in the finding.
- Mask the value in the report (first four characters, then `…`). Never paste a full secret into a report, PR comment or chat.
- Public identifiers (a publishable Stripe key, an Auth0 client ID for an SPA, a Sentry DSN) aren't secrets. Check the key type before reporting.
- `gitleaks` and `trufflehog` aren't installed on this machine. If the user installs one, run it on the branch's commits as a cross-check.

## PII in logs and telemetry

PII here means names, emails, phone numbers, addresses, government IDs, dates of birth, bank and payment details, and auth tokens or session IDs.

Flag added lines that send PII somewhere with broader access or longer retention than the source:

- `logger.*`, `print(`, `console.log(` with `request.data`, `request.body`, `request.headers`, a whole user, company or order object, a serializer's `.data`, or an exception message built from them.
- Sentry `send_default_pii=True`, breadcrumbs or `set_context` with request bodies, Datadog or other log shippers capturing full request or response bodies.
- Analytics and session-replay events carrying emails, names or tokens.
- Error responses returning stack traces, SQL or internal paths to clients (`DEBUG`, a catch-all handler returning `str(exc)`).
- Celery task arguments and results holding PII, since brokers, result backends and Flower keep them.

The finding names the field, the destination and who can read the destination. A field name in a log line that is never filled with personal data isn't a finding.
