# WRDT frontend

React 19 + Vite. All data comes from the API (`src/lib/api.js`); there is no mock data.

```bash
npm install
npm run dev      # dev server, proxies /api -> http://127.0.0.1:8000
npm run lint
npm run build    # outputs dist/
```

`VITE_API_BASE_URL` (see `.env.example`) is optional: leave blank to call the same-origin `/api/v1`.
It is baked in at build time.
