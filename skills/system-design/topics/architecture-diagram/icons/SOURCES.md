# Icon sources

The skill stores no icon drawings. `icons/catalog.json` maps each icon key to
`family:name`, and `scripts/fetch_icons.py` downloads the icons a diagram uses
from the official source below into a cache outside the repo. The URLs,
versions and archive hashes live in `FAMILIES` in `scripts/fetch_icons.py`;
change them there and here together.

| Family | Source | Version | Terms | How a name maps to a file |
|---|---|---|---|---|
| `aws` | AWS Architecture Icons, "Icon package" zip from https://aws.amazon.com/architecture/icons/ | `07312026` (sha256 `d2d166c4…`) | AWS allows customers and partners to use the icons to create architecture diagrams and in materials such as whitepapers and presentations; the page grants no right to redistribute the files | the SVG file name without `.svg`, anywhere in the zip: `Arch_AWS-Lambda_64` is `Architecture-Service-Icons_07312026/Arch_Compute/64/Arch_AWS-Lambda_64.svg` |
| `azure` | Azure architecture icons, `Azure_Public_Service_Icons_V25.zip` from https://learn.microsoft.com/en-us/azure/architecture/icons/ | `V25` (sha256 `f293d992…`) | Microsoft permits the icons in architectural diagrams, training materials or documentation, and their copying and distribution only for that use; don't crop, flip, rotate or reshape them | the SVG file name without `.svg`: `10023-icon-service-Kubernetes-Services` |
| `gcp` | Google Cloud core product icons, `core-products-icons.zip` from https://cloud.google.com/icons | sha256 `6531a10f58bc…` (the URL has no version) | the page offers the icons "for your diagrams, technical documentation, and more" and states no license | the SVG file name without `.svg`: `BigQuery-512-color` |
| `gcp-category` | Google Cloud product category icons, `category-icons.zip` from https://cloud.google.com/icons | sha256 `e5bc3abd3527…` | as `gcp` | the SVG file name without `.svg`: `Databases-512-color` |
| `simple-icons` | npm `simple-icons`, https://cdn.jsdelivr.net/npm/simple-icons@16.36.0/icons/ | `16.36.0` | CC0 1.0 (`LICENSE.md`), except icons with their own `license` in `data/simple-icons.json`, such as `apachekafka` (Apache-2.0); logos stay their owners' trademarks | the slug: `postgresql` is `icons/postgresql.svg` |
| `logos` | gilbarbara/logos on GitHub, https://cdn.jsdelivr.net/gh/gilbarbara/logos@b9edc65f8946027cb5e2fe6c772e914cf3649fba/logos/ | commit `b9edc65f8946…` (the repo has no tags or npm package) | CC0 1.0 (`LICENSE.txt`); logos stay their owners' trademarks | the file name without `.svg`: `slack-icon` is `logos/slack-icon.svg` |
| `lucide` | npm `lucide-static`, https://cdn.jsdelivr.net/npm/lucide-static@1.66.0/icons/ | `1.66.0` | ISC (`LICENSE`); the icons derived from Feather are MIT | the icon name: `database` is `icons/database.svg` |
| `tabler` | npm `@tabler/icons`, https://cdn.jsdelivr.net/npm/@tabler/icons@3.50.0/icons/outline/ | `3.50.0` | MIT (`LICENSE`) | the icon name: `bucket` is `icons/outline/bucket.svg` |

Where the terms were read:

- AWS: https://aws.amazon.com/architecture/icons/ (the download links and the
  usage sentences; the package itself carries no terms file).
- Azure: the "Icon terms" section of
  https://learn.microsoft.com/en-us/azure/architecture/icons/ and
  `Microsoft_Terms_of_Use.pdf` inside the V25 zip, which say the same.
- Google Cloud: https://cloud.google.com/icons.
- Simple Icons, Lucide and Tabler: the `LICENSE` or `LICENSE.md` file of each
  pinned package on cdn.jsdelivr.net, and Simple Icons'
  `data/simple-icons.json` for per-icon licenses.
- gilbarbara/logos: `LICENSE.txt` at the pinned commit.

## Which family to use

- AWS, Azure and Google Cloud services: the vendor's own set.
- Other vendors and open-source products: Simple Icons, the vendor's logo as a
  one-color glyph.
- Generic shapes (user, database, queue, server): Lucide, with Tabler for the
  one shape Lucide lacks (`bucket`).
- Vendors with no official downloadable set and no Simple Icons entry
  (`openai`, `salesforce`, `sendgrid`, `slack`, `twilio`): the full-color logo
  from gilbarbara/logos, which is closer to the official logo than a one-color
  glyph.

## Pins and updates

The npm families are pinned by version in the URL, and `logos` by commit. The archive families are
pinned by sha256: when a vendor replaces the file behind the same URL, the fetch
stops with the new hash. To move to a new release, update the URL, version and
sha256 in `FAMILIES`, run `scripts/fetch_icons.py --list <family>` to check that
the names in `icons/catalog.json` still exist, and update this table.

## Redistribution

Rendered diagrams embed the icons. The AWS, Azure and Google Cloud terms allow
that in architecture diagrams and documentation, but none of them grants a
right to ship the icon files as a set in a repo, so the skill keeps only the
catalog and fetches the files on use. A rendered example committed to this repo would
embed vendor icons, so `assets/examples/` holds only the diagram source.
