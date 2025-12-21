# PROVENIQ Properties - Frontend

Next.js App Router frontend for the unified landlord platform.

## Tech Stack
- **Next.js 14** (App Router)
- **TypeScript**
- **TailwindCSS** + shadcn/ui
- **TanStack Query** for data fetching
- **React Hook Form** + Zod for forms
- **Firebase Web SDK** for auth

## Setup

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment
```bash
cp .env.local.example .env.local
# Edit .env.local with your Firebase config
```

### 3. Run Development Server
```bash
npm run dev
```

Open [http://localhost:3001](http://localhost:3001)

## Project Structure
```
src/
├── app/              # Next.js App Router pages
├── components/       # React components
│   └── ui/          # shadcn/ui components
└── lib/             # Utilities and API client
    ├── api.ts       # Backend API client
    ├── auth.tsx     # Firebase auth context
    ├── firebase.ts  # Firebase initialization
    └── utils.ts     # Utility functions
```

## Key Features
- Firebase Authentication
- Property/Unit/Lease management
- Inspection workflow with evidence upload
- Maintenance ticket management
- Mason AI advisory integration
