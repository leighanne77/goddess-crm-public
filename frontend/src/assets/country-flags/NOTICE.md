# Country flag SVGs — attribution

These circular country-flag SVGs are sourced from the
**HatScripts/circle-flags** project, vendored into this repo at
`frontend/src/assets/country-flags/`.

- Upstream: https://github.com/HatScripts/circle-flags
- License: MIT
- Fetched via: `scripts/fetch_country_flags.py` (pulls from the
  `gh-pages` branch of the upstream repo)

The MIT license requires us to preserve the copyright + permission
notice. Reproduced below; the full license text lives in the upstream
repo.

```
MIT License

Copyright (c) HatScripts and contributors

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
```

To grow the set, add ISO codes to `scripts/fetch_country_flags.py`
`COUNTRY_CODES` and re-run, then run `make sync-country-codes` so the
TypeScript Literal union picks up the new files.
