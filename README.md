# ValueSignal Build Console

A local-first planning console for building **ValueSignal Lite** in ten independently testable phases. This repository is the roadmap—not the final financial product.

## Run

```bash
npm install
npm run dev
```

Open `http://localhost:3000`. Phase state, task completion, and notes use browser `localStorage`; no backend is required. Edit `src/data/phases.ts` to change the roadmap.

Routes: `/`, `/roadmap`, `/phase/[id]`, `/architecture`, `/notes`, `/debugging`, and `/resume-interview`.

ValueSignal Lite is framed as an educational research tool, not investment advice.
