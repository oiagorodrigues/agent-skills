# Vue and TypeScript SPAs, Nuxt and Node

Browser rules adapted from cloudflare/security-audit-skill `CLIENT-SIDE.md` (MIT, https://github.com/cloudflare/security-audit-skill) and getsentry/skills `security-review` (Apache-2.0, https://github.com/getsentry/skills).

## Contents

- Vue SPA: XSS
- Vue SPA: tokens, storage and logout
- Vue SPA: redirects and navigation
- Vue SPA: other browser boundaries
- Nuxt server code
- Node services
- Boundary validation with Zod
- Proving it

## Vue SPA: XSS

Vue escapes `{{ }}` and attribute bindings, so a finding needs one of the escape hatches below plus a value another user or company can set (product descriptions, notes, names, messages, API data from a partner, LLM output).

- `v-html` with any such value. It needs a sanitizer (DOMPurify) with a configuration that drops scripts, event handlers and `javascript:` URLs, applied right before rendering.
- `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` in components, directives or plain TS helpers.
- `:href`, `:src`, `:action` or `window.location` bound to user data. Vue doesn't block `javascript:` or `data:` URLs, so check the scheme is `https:` or the path is relative.
- `v-bind="objectFromApi"` spreads attributes, including event handlers, from data.
- Markdown rendered to HTML (`marked`, `markdown-it` with `html: true`) and then `v-html` without sanitizing.
- Runtime template compilation of user strings (`compile()`, a `template:` option built from data), and Vue mounted on server HTML that contains user text with `{{ }}` (client-side template injection).
- `eval`, `new Function`, `setTimeout("string")`.

## Vue SPA: tokens, storage and logout

A token in `localStorage` is a finding only together with a reader that has less authority than the owner (an XSS path in the same origin) or with use after it should be gone (survives logout or account switch). Check:

- Auth0 SPA SDK `cacheLocation: "localstorage"` with refresh tokens, and whether an XSS path exists.
- Pinia persisted state, `localStorage`, `sessionStorage` and IndexedDB holding tokens, PII or another company's data after logout or company switch.
- Logout clears stores, storage and caches, and the next user on the same browser sees nothing from the previous one.

## Vue SPA: redirects and navigation

- `router.push(route.query.redirect)`, `window.location = params.next`, Auth0 `appState.returnTo` and similar. Accept only relative paths that start with one `/` (reject `//host`, `/\host` and full URLs), or an exact allowlist of origins.
- `window.open(url)` with user data, and `target="_blank"` links to user-supplied URLs.

## Vue SPA: other browser boundaries

- Authorization in route guards, `v-if` or hidden buttons is UI only. When the diff adds a permission check only on the client, confirm the API enforces the same rule, or report the API gap.
- `postMessage` listeners must compare `event.origin` to an exact allowlist. Substring, `startsWith` or unanchored regex checks don't count. Sending sensitive data with target origin `"*"` is a leak.
- Build-time variables (`VITE_*`, `VUE_APP_*`, `import.meta.env`) ship in the bundle. Any secret there is public.
- `<script src>` from a CDN without `integrity` and `crossorigin`. Analytics and session-replay tools receiving PII or tokens.
- Production source maps are a low-severity disclosure unless they reveal secrets.

## Nuxt server code

- Every handler in `server/api` and `server/routes` checks the session and the company on its own. A Nuxt route middleware runs in the app, so it doesn't protect server handlers.
- `runtimeConfig.public` ships to the browser. Secrets belong in private `runtimeConfig` keys.
- SSR payload and `useState` serialize into the HTML. Server-only data (other users' records, internal flags, tokens) must not enter them.
- Server routes that proxy or fetch (`$fetch(userUrl)`, `routeRules` proxies) are SSRF candidates. Block private ranges and `169.254.169.254`, and re-check after redirects.
- Cookies set by the server: `httpOnly`, `secure`, `sameSite`.

## Node services

- `child_process.exec` or `execSync` with interpolated input. Use `execFile` or `spawn` with an argument array and no shell.
- `eval`, `new Function`, `vm.runInContext`. The `vm` module isn't a sandbox.
- Paths: `path.join(base, userPath)` needs `path.resolve` and a check that the result starts with `base + path.sep`.
- Prototype pollution: a recursive merge or path assignment of request data (`lodash.merge`, `set`, custom deep merge) accepting `__proto__`, `constructor` or `prototype` keys. It's a finding only with a gadget that later reads the polluted property in a security decision or sink.
- `jsonwebtoken`: `verify` with an explicit `algorithms` list and audience. `jwt.decode` results must never be trusted.
- CORS that reflects `Origin` while allowing credentials. `express.static` serving dotfiles or the project root.
- User input compiled into a `RegExp` (ReDoS), `Math.random()` for tokens, `crypto.createCipher` and ECB mode, `rejectUnauthorized: false` and `NODE_TLS_REJECT_UNAUTHORIZED=0`.

## Boundary validation with Zod

Where the repo validates with Zod (or another schema library), check every untrusted input in the diff for a parse before use: request bodies, query strings and route params, webhook payloads, env vars, LLM output, `localStorage` and `postMessage` data.

- `JSON.parse(x) as T`, a type annotation on `await res.json()` or a `body as Order` cast is no validation. A finding needs the unchecked value to reach a sink or a security decision.
- Nuxt and h3: `readValidatedBody(event, schema.parse)` and `getValidatedQuery` reject bad input with a 400; a plain `readBody(event)` passed on to a write is unvalidated.
- `z.object` strips unknown keys. A `z.looseObject`, `.passthrough()` or `z.record` result spread into an ORM or database write is mass assignment (`role`, `companyId`, `isAdmin`).
- A `safeParse` call whose `success: false` branch logs and then carries on with the raw input.

## Proving it

For XSS, render the component in a Vitest or Playwright test with a payload such as `<img src=x onerror="window.__xss=1">` and assert `window.__xss` stays undefined. For open redirects, unit-test the redirect helper with `//evil.example`, `/\evil.example` and `javascript:alert(1)`. Run only against a local dev server or test harness.
