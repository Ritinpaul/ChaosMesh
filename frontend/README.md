# ChaosMesh Arena - React Dashboard

## 🚀 Getting Started

### Prerequisites

- **Node.js 18+** ([Download](https://nodejs.org/))
- **npm** (comes with Node.js)

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

### Development Mode

```bash
# Start development server (with hot reload)
npm run dev
```

The dashboard will be available at: **http://localhost:3000**

The dev server automatically proxies API requests to `http://localhost:8000`

### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

The built files will be in `frontend/dist/` and served by FastAPI at `http://localhost:8000/`

## 📦 Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool (super fast!)
- **TailwindCSS** - Styling
- **React Query** - Data fetching & caching
- **Recharts** - Charts and graphs
- **Axios** - HTTP client
- **Lucide React** - Icons

## 🎨 Features

### ✅ Working Features

- **Real-time Updates** - Auto-refreshes every 2 seconds
- **Episode Control** - Create episodes (L1-L5)
- **Metrics Display** - Reward charts & service health
- **Incident Viewer** - See active incidents with details
- **Status Bar** - Episode progress tracking
- **System Health** - Ollama & Redis status
- **Error Handling** - Loading states & error messages

### 🎯 What It Does

1. **Header** - Shows system status (Ollama, Redis, active episode)
2. **Control Panel** - Select level and start new episodes
3. **Metrics Display** - Visualize rewards and service health
4. **Incident List** - View active incidents with affected services/pods
5. **Status Bar** - Track episode progress in real-time

## 📁 Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts          # API client (axios)
│   ├── components/
│   │   ├── Header.tsx          # Top header with health status
│   │   ├── StatusBar.tsx       # Bottom status bar
│   │   ├── ControlPanel.tsx    # Episode creation controls
│   │   ├── MetricsDisplay.tsx  # Charts and metrics
│   │   └── IncidentList.tsx    # Active incidents
│   ├── hooks/
│   │   └── useApi.ts           # React Query hooks
│   ├── types/
│   │   └── api.ts              # TypeScript interfaces
│   ├── App.tsx                 # Main app component
│   ├── main.tsx                # Entry point
│   └── index.css               # Global styles
├── public/                     # Static assets
├── index.html                  # HTML template
├── package.json                # Dependencies
├── vite.config.ts              # Vite configuration
├── tailwind.config.js          # Tailwind configuration
└── tsconfig.json               # TypeScript configuration
```

## 🔌 API Integration

The dashboard connects to these endpoints:

```typescript
GET  /health          # System health
POST /env/reset       # Create episode
GET  /env/state       # Get current state
POST /env/step        # Take action
POST /demo/inject     # Inject incident
```

All requests include the `X-API-Key` header (configured in `src/api/client.ts`)

## 🎮 Usage

### Starting an Episode

1. Open dashboard at `http://localhost:3000` (dev) or `http://localhost:8000` (prod)
2. Select a difficulty level (L1-L5)
3. Click "Start New Episode"
4. Watch metrics update in real-time

### Viewing Data

- **Auto-refresh**: Data updates every 2 seconds automatically
- **Metrics**: See reward history and service health
- **Incidents**: View active incidents with details
- **Status Bar**: Track progress at the bottom

## 🐛 Troubleshooting

### Frontend Won't Start

**Check Node.js version:**
```bash
node --version  # Should be 18+
```

**Reinstall dependencies:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### API Connection Errors

**Make sure backend is running:**
```bash
# In chaosmesh-arena directory
python start_server.py
```

**Check CORS settings in `.env`:**
```bash
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### Build Errors

**Clear cache and rebuild:**
```bash
npm run build -- --force
```

## 🚀 Deployment

### Option 1: Serve with FastAPI

```bash
# Build frontend
cd frontend
npm run build

# Start FastAPI (serves React at /)
cd ..
python start_server.py

# Open http://localhost:8000
```

### Option 2: Separate Frontend Server

```bash
# Terminal 1: Backend
python start_server.py

# Terminal 2: Frontend
cd frontend
npm run dev

# Open http://localhost:3000
```

## 📊 Performance

- **Auto-refresh**: Every 2 seconds (configurable in `src/main.tsx`)
- **Caching**: React Query caches responses
- **Bundle size**: ~150KB gzipped
- **Load time**: <1 second

## 🔧 Configuration

### Change API URL

Edit `frontend/.env`:
```bash
VITE_API_URL=http://localhost:8000
```

### Change Refresh Interval

Edit `frontend/src/main.tsx`:
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 5000, // Change to 5 seconds
    },
  },
})
```

### Customize Styling

Edit `frontend/tailwind.config.js`:
```javascript
theme: {
  extend: {
    colors: {
      primary: {
        DEFAULT: '#your-color',
      }
    }
  }
}
```

## ✅ Advantages Over Gradio

| Feature | React Dashboard | Gradio Dashboard |
|---------|----------------|------------------|
| **Connection** | ✅ Direct HTTP | ❌ WebSocket issues |
| **Performance** | ✅ Fast & responsive | ⚠️ Slower |
| **Customization** | ✅ Fully customizable | ⚠️ Limited |
| **Auto-refresh** | ✅ React Query | ❌ Manual polling |
| **Error handling** | ✅ Built-in | ⚠️ Basic |
| **Type safety** | ✅ TypeScript | ❌ None |
| **Bundle size** | ✅ 150KB | ❌ 2MB+ |

## 📝 Development Tips

### Hot Reload

Vite provides instant hot module replacement. Changes appear instantly without full page reload.

### Type Safety

TypeScript catches errors before runtime:
```typescript
// ✅ Type-safe
const level: number = 1

// ❌ TypeScript error
const level: number = "1"
```

### React Query DevTools

Add DevTools for debugging:
```bash
npm install @tanstack/react-query-devtools
```

```tsx
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'

// In App.tsx
<ReactQueryDevtools initialIsOpen={false} />
```

## 🎯 Next Steps

Ready to use! Just:

1. **Install Node.js** (if not installed)
2. **Run `npm install`** in `frontend/` directory
3. **Run `npm run dev`** to start development
4. **Open http://localhost:3000**

The dashboard will connect to your FastAPI backend and start showing real-time data!

## 🤝 Contributing

Want to add features?

1. Create new component in `src/components/`
2. Add to `App.tsx`
3. Use React Query hooks for data
4. Style with Tailwind classes

Example:
```tsx
// src/components/MyFeature.tsx
import { useEnvState } from '../hooks/useApi'

export default function MyFeature() {
  const { data, isLoading } = useEnvState()
  
  return (
    <div className="card">
      <h2>My Feature</h2>
      {/* Your code */}
    </div>
  )
}
```

---

**Made with ❤️ using React + Vite + TypeScript + TailwindCSS**
