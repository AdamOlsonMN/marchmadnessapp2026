# March Madness Bracket Dashboard

## Intranet / network access

The dev server is configured to listen on all interfaces (`host: true`). From the machine running the app:

1. **Start the API** (repo root): `PYTHONPATH=src uvicorn dashboard.api.main:app --host 127.0.0.1 --port 8000`
2. **Start the frontend**: `npm run dev`

Vite will print a **Network** URL (e.g. `http://192.168.1.5:5173`). Open that URL from any device on your network; API requests are proxied through the dev server so the backend can stay on localhost.

---

# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
