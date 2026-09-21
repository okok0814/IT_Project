# Fashion Search Frontend

React frontend prototype for the fashion-search project.

## Scope of this week

- React + Vite project setup
- React Router navigation
- Static pages:
  - `/` — Home
  - `/search/image` — Image search
  - `/search/text` — Text search
  - `/results` — Results
- Reusable components (`Header`, `FilterSidebar`, `ProductCard`)
- Static/mock results only
- Backend is intentionally **not connected yet**

## Run locally

Open PowerShell / CMD in this folder and run:

```bash
npm install
npm run dev
```

Then open the URL shown by Vite, normally:

```text
http://localhost:5173
```

## After turning off the computer

You normally do **not** need to run `npm install` again.
Just open the project folder and run:

```bash
npm run dev
```

Run `npm install` again only when `node_modules` is missing or dependencies changed.

## Future API integration

The UI is prepared for these existing backend routes:

```text
POST /api/v1/search/image
POST /api/v1/search/text
```

The result cards already include a similarity-style score so the next step can replace mock data with API data.
