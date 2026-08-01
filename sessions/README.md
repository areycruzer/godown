# sessions/

Paste secrets here (gitignored). Default path — leave `SESSIONS_DIR` blank in `.env`.

| File | Contents |
|------|----------|
| `ak.txt` | JWT (one line) |
| `cookie_header.txt` | Full Cookie header |

Or set `IM_AK` / `IM_COOKIE` in `.env`.

```bash
python3 scripts/indiamart_login.py --mobile 10DIGIT
```

Then `USE_AK=true` and restart backend. Do not commit real files.
