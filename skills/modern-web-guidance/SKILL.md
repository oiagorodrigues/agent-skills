---
name: modern-web-guidance
description: "Searches Google Chrome's curated guides on modern web platform best practices, and builds and publishes Manifest V3 Chrome extensions. MANDATORY: consult it FIRST for every HTML, CSS and client-side JavaScript task, because web APIs change fast and training data holds obsolete patterns. Trigger for modals, dialogs, popovers, anchor positioning, container queries, :has(), view transitions, scroll-driven animations, forms, autofill, validation, accessibility, custom selects and scrollbars, dark mode, Core Web Vitals (LCP, INP, CLS), fetch priority, passkeys, HTML sanitization, web components, built-in AI, WebAssembly, and layout or styles in React, Vue or Angular. Also use for Chrome extensions: manifest.json, content scripts, extension service workers, popups, side panels, chrome.* APIs, declarativeNetRequest, and Chrome Web Store publishing or rejections. Do NOT trigger for backend (database SQL, ORMs, Express API routes), CI/CD, Docker, GitHub Actions, local Python or Go scripts, ESLint or Git."
---

# Modern web guidance

Two topics from Google Chrome's modern-web-guidance plugin. Paths below are relative to `~/.agents/skills/modern-web-guidance/`. Inside a topic file, relative paths such as `references/extensions/permissions.md` are relative to that topic's folder.

## How to use

- Any HTML, CSS or client-side JavaScript task, including styles and layout inside React, Vue or Angular: before writing code, read `topics/modern-web-guidance/README.md` and follow its steps. Search the guides with `~/.agents/skills/modern-web-guidance/scripts/mwg search "query"`, retrieve the matching ids, check the code against them, and end the reply with a `### Modern Web Guidance` section.
- Building, debugging or publishing a Chrome extension: read `topics/chrome-extensions/README.md`, then the reference files it lists for the APIs in play. For the Prompt API inside an extension, use both topics.
- Backend (database SQL, ORMs, Express API routes), CI/CD, Docker, GitHub Actions, local Python or Go scripts, ESLint and Git: skip this skill.

`scripts/mwg` runs a vendored copy of the `modern-web-guidance` npm package (see `vendor/README.md`) with telemetry off and no network access. It needs Node.js 22 or newer on `PATH`. Never run the package through `npx`.

## Topics

- `topics/modern-web-guidance/README.md`: search, retrieve and apply web platform guides, and the browser support and fallback rules.
- `topics/chrome-extensions/README.md`: Manifest V3 rules, extension APIs, and Chrome Web Store publishing.
