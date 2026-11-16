# Django and DRF

Cross-company access (IDOR, querysets, object permissions, buyer and seller sides) lives in `~/.agents/skills/django-expert/references/access-and-performance-review.md`, section "Access review". Run that method first for every endpoint, task and export the change touches. This file covers the rest of the Django surface.

Method and false-positive rules adapted from getsentry/skills `security-review` and `django-access-review` (Apache-2.0, https://github.com/getsentry/skills).

## Contents

- Serializers and mass assignment
- Raw SQL and request-driven ORM calls
- Authentication, CSRF and sessions
- Templates and redirects
- File uploads and exports
- Celery tasks
- Admin
- Settings
- Webhooks and outbound requests
- Proving it

## Serializers and mass assignment

- `fields = "__all__"` or `exclude = [...]` on a writable serializer makes every future model field writable. Flag it on any serializer used for create or update.
- Writable fields that the server should own: `company`, `owner`, `created_by`, buyer or seller IDs, `status`, prices and totals, `is_staff`, roles, approval flags. Check `read_only_fields` and whether `perform_create` sets them from the request user instead of the body.
- `PrimaryKeyRelatedField(queryset=Model.objects.all())` and `SlugRelatedField` let a user attach another company's object by ID. The queryset must be scoped to the requesting company (usually in `get_fields()` or `__init__` with `self.context["request"]`).
- `serializer.save(**request.data)`, `Model.objects.create(**request.data)` and `update_or_create(defaults=request.data)` bypass field restrictions.
- Nested writable serializers: check that each nested object belongs to the parent and the requesting company.
- Output side: a serializer that shows fields to the wrong audience (the other party's cost or margin, internal notes, another company's contacts), or `depth = N` that serializes whole related objects.

## Raw SQL and request-driven ORM calls

- Flag `.raw()`, `.extra()`, `RawSQL()` and `cursor.execute()` when the SQL string is built with f-strings, `%` or `+`. Parameters passed as a separate list are safe.
- `filter(**request.GET.dict())`, `order_by(request.GET["sort"])` and `values(*fields_from_request)` let the user filter or sort on fields they can't see (for example `owner__password` or another company's relation), which leaks values through result order or counts. They need an allowlist. django-filter with `fields = "__all__"` has the same problem.
- Multi-tenant scoping that only lives in a default manager disappears on `Model._base_manager`, `all_objects`, raw SQL, `.union()` and aggregate queries. Check that the new query keeps it.

## Authentication, CSRF and sessions

- New views with `permission_classes = [AllowAny]`, `authentication_classes = []`, or no class at all when `DEFAULT_PERMISSION_CLASSES` is permissive. Read the settings before deciding.
- DRF enforces CSRF only for `SessionAuthentication` on authenticated requests. `@csrf_exempt` on a cookie-authenticated view that changes state is a finding. Token or JWT-only endpoints don't need CSRF.
- JWT and Auth0: signature verified with a pinned algorithm, `aud`, `iss` and `exp` checked. `verify_signature: False`, `options={"verify_aud": False}` or decoding without a key on any path that trusts the result is a finding.
- Role checks: `is_staff` and `is_superuser` mean Django staff, which is different from an admin of a customer company. Check the diff uses the right one.
- Company switching: if the active company comes from a session value, header or URL kwarg, find where membership in that company is checked.
- Login, password reset and invite flows: token single use and expiry, rotation of the session on login, invalidation on password change, rate limits.

## Templates and redirects

- `|safe`, `mark_safe(...)`, `{% autoescape off %}` and `format_html` called with an already formatted string, on any value that users or other companies can set. `{{ data|json_script:"id" }}` is the safe way to pass data to JavaScript.
- `redirect(request.GET["next"])` and `HttpResponseRedirect(user_value)` need `url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=True)`.

## File uploads and exports

- File type checked by content, not by extension or client `Content-Type`. Size limits through `DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE` and the field or view.
- `upload_to` or storage keys built from the user's filename allow path traversal or overwriting another company's file. Generate the key.
- Uploaded files served from the app's own domain with an HTML or SVG content type give stored XSS. Serve them as attachments, from a separate domain, or through signed S3 URLs.
- S3 storage: `default_acl="public-read"`, `querystring_auth=False` or long expiry on private files, and keys that don't include the company.
- Pillow on untrusted images: decompression bombs (`Image.MAX_IMAGE_PIXELS`). Zip or tar extraction: path traversal (zip slip).
- CSV or XLSX exports with user-controlled cells starting with `=`, `+`, `-` or `@` run as formulas when opened in Excel. Exports must also apply the same company scoping as the list endpoint.

## Celery tasks

- A task argument is a trust boundary. A task that takes an object ID must fetch it scoped to the company that requested the work, or re-check access, especially when the task is enqueued from a webhook or an endpoint.
- `CELERY_ACCEPT_CONTENT` or the task serializer including `pickle` means anyone who can write to the broker gets code execution. Flag it unless the broker is provably private (then "Needs validation").
- `send_task(name_from_request)` or dynamic task names from input.
- Retries that repeat side effects (charges, emails, external API writes) need an idempotency key or a done check.
- Task logs and failure payloads (Sentry, result backend) holding PII or tokens.

## Admin

- New `ModelAdmin` exposing secrets, bank details or tokens in `list_display`, `readonly_fields` or change forms to every staff user.
- Admin actions that act on querysets without `has_*_permission` checks, and custom admin views not wrapped in `admin_site.admin_view`.
- Impersonation or "login as" features: who can use them, and whether they are logged.

## Settings

- `DEBUG = True` reachable in production, `ALLOWED_HOSTS = ["*"]`, `SECRET_KEY = os.environ.get("SECRET_KEY", "<literal>")` (a fallback secret is a committed secret).
- `CORS_ALLOW_ALL_ORIGINS = True` or origin regexes with `CORS_ALLOW_CREDENTIALS = True`. Unanchored regexes in `CORS_ALLOWED_ORIGIN_REGEXES` and `CSRF_TRUSTED_ORIGINS`.
- `SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST` trust headers that the load balancer must strip. Whether it does is a "Needs validation" fact unless the ingress config is in the repo.
- Cookie flags: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`.

## Webhooks and outbound requests

- Incoming webhooks: signature checked over the raw body with `hmac.compare_digest`, timestamp checked against replay, idempotent handling, and the account ID in the payload mapped to the right company before any write.
- Outbound requests to URLs a user can set (webhook targets, "import from URL", image fetch): block private and link-local ranges including `169.254.169.254`, re-check after redirects, set timeouts. A URL from settings is server-controlled and not SSRF.

## Proving it

Write the proof as a DRF test with two companies: create an object for company A, authenticate as a user of company B with `APIClient.force_authenticate`, call the endpoint, and assert 403 or 404. A test that passes on the base branch and fails on the PR branch is the strongest proof. For Celery, call the task function directly with company B's context and company A's object ID.
