---
name: design-directions
description: Design 2-3 distinct, original, fully responsive visual directions for any product (website, web app, mobile, watch, TV, kiosk...) as the starting point for its design system. Use for any redesign, new UI, "make it look better/modern", layout or visual exploration, or before creating/updating design tokens and components. Framework-agnostic.
---

# Design directions

Goal: show the user 2-3 strong, distinct directions so they can choose one. Then the chosen direction feeds the design system (tokens, components, patterns). You design the **system's look**, not the whole app: a few representative screens are enough.

## 1. Before designing (ask, then remember)

Check memory and the repo first. Ask only about what is still unknown, in one batch:

- **Design system.** Look for tokens, a theme or design docs (`docs/design*`, `design-system*`, `tokens*`, `tailwind.config*`, `theme.*`, CSS custom properties). If there is none, ask: is there one somewhere, or an idea for one (brand, colors, fonts, references), or may I create one as the base?
- **Output tool.** Figma, Claude Design/Artifacts, Canva, another tool, or HTML + CSS (Tailwind allowed). If a connector exists for the chosen tool, use it. Otherwise write HTML.
- **Platform(s) and type of product.** Website, web app, mobile, watch, TV and so on. Add the audience if it is not obvious.
- **Constraints to keep.** Palette, fonts, logo, accessibility level.

Save every answer and every later choice (chosen direction, liked and disliked traits, tool, fonts) to persistent memory as a `feedback` or `project` memory. Read them back on the next run, and don't ask again.

## 2. Research (cheap)

Do 2-4 searches for the best current work **in this product category**. Use award and showcase sites (horizonx.so/explore, Awwwards, Godly, Mobbin, Land-book, Dribbble shots from studios) and the leading products in the space. Note concrete patterns worth borrowing. Take ideas from them; never copy them.

## 3. The bar

- **Original.** Each direction has its own identity. Never label one "X-style", and never copy a brand.
- **Clean, minimal, modern, rich.** Confident type hierarchy, generous whitespace, soft depth (layered surfaces, subtle borders and shadows), refined data visualisation, purposeful color.
- **The domain shows subtly,** through type, color, spacing and small details. Never through literal illustrations, skeuomorphism or themed gimmicks: no bottles for a wine app, no coins for finance.
- **Nothing generic or LLM-looking.** Banned:
  - default Tailwind or shadcn palettes, indigo/violet gradients, and purple-to-pink hero gradients;
  - the Inter/Roboto/Arial/system default stack, unless the user's system demands it;
  - centred-hero, three-feature-cards templates, uniform rounded-2xl everything, emoji icons, and lorem ipsum.
- **Fonts.** Pick distinctive, well-crafted sans or grotesk families that fit the layout. Display and text pairs are fine. **No serif** unless the user's system already uses it. Use real content in the user's language and locale (currency, dates).
- **Motion everywhere it helps.** Page and section transitions, hover, focus and press states, staggered list entry, number tweening, and scroll-linked effects. On websites, add 3D or depth effects where they help (CSS 3D transforms, WebGL/Three.js). Always respect `prefers-reduced-motion`.
- **Cursors match the context:** pointer, text, grab, not-allowed, progress.
- **100% responsive.** Design the breakpoints on purpose, from phone up to wide desktop, or the target device's sizes (watch, TV 10-ft UI). Never just shrink the desktop layout.
- **Accessible by default:** contrast AA, visible focus, semantic structure. Don't trade these away for looks.

## UX rules (every screen, every size)

Write them into the project's design docs (for example `docs/design/ux-regras.md`) and check every screenshot against them.

- **Layout.**
  - Use a real grid. Nothing wraps or breaks at any width, and nothing scrolls horizontally on a phone.
  - On mobile, buttons **stack full-width in a column**, never in a row that wraps. KPI and stat cards stack too.
  - Desktop form and dialog actions sit on the **right**: secondary, then primary.
- **Modals.** Follow the APG dialog pattern.
  - **Full screen on mobile**, with the actions in a **sticky footer**.
  - Trap focus, close on Esc, and return focus to the trigger on close.
- **Filters.**
  - A panel on desktop. **Full screen on mobile**, with "Limpar" and "Aplicar" always visible and an **X that closes without applying**. The filter trigger stays visible on mobile.
  - Active filters show as removable chips.
- **Lists and tables.**
  - Search, filters, **sortable column headers**, row actions as icon buttons, and **pagination** (total, page size, prev/next).
  - Bulk actions: "N selected", a **⋯ menu** with the actions, and "clear selection".
  - On mobile, a table becomes cards with the row actions in the top-right, and the selected-row background follows the container's rounded corners.
  - Row actions open a **modal**, not a drawer or a new page.
- **Icon vs label.**
  - A recognisable action is an **icon button with a tooltip and the same aria-label**.
  - Keep icon + text for the lone primary action of a screen and for destructive or ambiguous actions.
  - Be minimal: cut text that an icon, a number or a layout already says.
- **Tooltips.**
  - Open after a **~300 ms delay**.
  - Render in a portal with collision handling (flip/shift), so they are never clipped by a container or the viewport.
  - Never the only place important information lives, since touch screens can't hover.
- **Popovers, menus and dropdowns.** They **close on click outside** and on Esc.
- **Forms.**
  - Label above the field, placeholders as examples (no "exemplo:" helper text), inline errors.
  - **Input masks** for currency, date, time, phone and document numbers.
  - A **custom select** must follow the APG select-only combobox: arrows, Enter, Esc, type-ahead.
- **Touch targets.** At least 24 px (WCAG 2.5.8); aim for 44 px on touch UIs.
- **Motion.**
  - Animate everything that appears or disappears, page changes and hover. Use about 150-250 ms for UI and up to 400 ms for large surfaces, with standard easing.
  - Animate transform and opacity without reflow; a collapsing sidebar must not jump.
  - Always respect `prefers-reduced-motion`.

References:
- NN/g tooltips: https://www.nngroup.com/articles/tooltip-guidelines/
- Material 3 motion: https://m3.material.io/styles/motion/easing-and-duration
- Apple HIG layout: https://developer.apple.com/design/human-interface-guidelines/layout
- WAI-ARIA APG dialog: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- WAI-ARIA APG menu button: https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/
- WAI-ARIA APG select-only combobox: https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-select-only/
- Baymard input masking: https://baymard.com/blog/input-masking-form-field
- WCAG 2.5.8 target size: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html

## 4. Deliver

- **2-3 directions that differ in structure and feel,** not just in color. Examples of how they can differ: navigation model, density, layout rhythm, how surfaces and depth are built, how key data is shown.
- **Each direction shows 3-4 representative screens or states** of the user's product, with real-looking data.
- **HTML output:** one self-contained file per direction in the project's design docs folder, e.g. `docs/design/<round>/direction-N.html`. CDNs are allowed. Also produce full-page screenshots at a phone width and a desktop width. Look at each screenshot once and fix anything broken.
- **Notes:** a ≤ 40-line README with one paragraph per direction (the idea and what makes it distinct), the reference links, and a recommendation.
- **Open the results** for the user and ask which one to pick, or what to combine.
- **Screenshots at phone and desktop width for every screen.** Look at each one against the UX rules and fix anything broken before showing it. Mobile matters most.
- **Never decide on your own** a product or layout question that the user's list doesn't cover. Put it under "Decisões para aprovar" or "Decisions to approve".
- **When the design moves into implementation,** every screen of the product gets the new system, not only the screens that were mocked. Nobody says the work is done until the running app has been checked in a browser, screen by screen, against the mockups and the checklist.

## 5. Iterate, then hand off

Adjust from the feedback. Keep what the user liked and drop what they didn't, and record both in memory. Never overcorrect: if the user calls a direction "too plain" or "too loud", aim for the middle, not the opposite extreme.

Once a direction is chosen, write or update the project's existing design docs (tokens: color, type, spacing, radius, shadow, motion; plus components, states and patterns). Don't start a parallel set of docs. Building the application screens comes after that, as separate work.

Keep token use low: few searches, few iterations of screenshots, short reports.
