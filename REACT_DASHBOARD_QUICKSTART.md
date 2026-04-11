# 🎉 React Dashboard - Quick Start Guide

## ⚡ Fastest Path (3 Steps!)

### Step 1: Install Node.js

**If you don't have Node.js:**
1. Download from: https://nodejs.org/ (LTS version)
2. Install with default options
3. Verify: `node --version` (should show v18 or higher)

### Step 2: Install & Build

```bash
# Navigate to frontend directory
cd d:\NewStart\hackssss\theOne\chaosmesh-arena\frontend

# Install dependencies (first time only)
npm install

# Build for production
npm run build
```

Wait for build to complete (~30 seconds)

### Step 3: Start Server

```bash
# Go back to main directory
cd ..

# Start FastAPI server
python start_server.py
```

**Done!** Open: http://localhost:8000

---

## 🖥️ Two Ways to Use

### Option A: Production Mode (Recommended)

FastAPI serves the built React app:

```bash
# 1. Build frontend (once)
cd frontend
npm install
npm run build

# 2. Start server
cd ..
python start_server.py

# 3. Open browser
# http://localhost:8000
```

**Advantages:**
- ✅ Single server (port 8000)
- ✅ No CORS issues
- ✅ Production-optimized
- ✅ Fast loading

### Option B: Development Mode (For Changes)

Separate dev server with hot reload:

```bash
# Terminal 1: Start backend
python start_server.py

# Terminal 2: Start frontend dev server
cd frontend
npm run dev

# Open browser
# http://localhost:3000
```

**Advantages:**
- ✅ Hot reload (instant updates)
- ✅ Better debugging
- ✅ Source maps
- ✅ React DevTools support

---

## 🎮 What You'll See

### Dashboard Features

1. **Header** (Top)
   - System health status
   - Ollama & Redis status
   - Current episode ID
   - Version info

2. **Control Panel** (Left)
   - Select difficulty level (L1-L5)
   - "Start New Episode" button
   - Episode creation status

3. **Metrics Display** (Center/Right)
   - Cumulative reward chart
   - Service health cards
   - Error rates & latency

4. **Incident List** (Bottom Right)
   - Active incidents
   - Affected services/pods
   - Root cause info

5. **Status Bar** (Bottom)
   - Episode ID, step count
   - Current level & reward
   - Active incident count
   - Progress tracking

---

## 🐛 Troubleshooting

### "Node.js not found"

**Install Node.js:**
```bash
# Download from: https://nodejs.org/
# Use LTS version (v20.x recommended)
```

### "npm install fails"

**Try with clean install:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### "Build fails"

**Check Node version:**
```bash
node --version  # Must be 18+
npm --version   # Must be 9+
```

### "Frontend not showing"

**Rebuild and restart:**
```bash
cd frontend
npm run build
cd ..
python start_server.py
```

### "API connection error"

**Check backend is running:**
```bash
# Should see:
# INFO:     chaosmesh_ready                port=8000
```

**Check browser console (F12) for errors**

---

## 📊 First Time Usage

### 1. Open Dashboard
```
http://localhost:8000
```

### 2. Check System Health
Look at the header:
- ✅ Status: healthy
- ✅ Ollama: ✓
- ✅ Redis: ✓

### 3. Create Your First Episode
1. Select "L1 - Pod Crash"
2. Click "Start New Episode"
3. Wait ~2 seconds
4. See metrics update!

### 4. Watch It Work
- Reward chart updates automatically
- Service metrics refresh every 2 seconds
- Incidents appear in real-time
- Status bar shows progress

---

## 🎯 Key Differences from Gradio

| Aspect | React Dashboard | Old Gradio |
|--------|----------------|------------|
| Connection | ✅ Direct HTTP (always works) | ❌ WebSocket (often fails) |
| Setup | Install Node.js, run build | Already installed |
| Speed | ✅ Fast (150KB bundle) | ⚠️ Slow (2MB+ bundle) |
| Customization | ✅ Fully customizable | ⚠️ Limited |
| Auto-refresh | ✅ React Query (smart) | ⚠️ Manual polling |
| Mobile | ✅ Responsive | ❌ Not optimized |
| UI | ✅ Modern Tailwind | ⚠️ Gradio default |

---

## 📝 Development Workflow

### Making Changes

```bash
# Start dev server (Terminal 1)
cd frontend
npm run dev

# Make changes to src/components/*.tsx
# See instant updates in browser

# When done, build for production
npm run build
```

### Adding Components

```tsx
// src/components/MyComponent.tsx
import { useEnvState } from '../hooks/useApi'

export default function MyComponent() {
  const { data, isLoading } = useEnvState()
  
  return (
    <div className="card">
      <h2>My Component</h2>
      {/* Your UI */}
    </div>
  )
}
```

Then add to `App.tsx`:
```tsx
import MyComponent from './components/MyComponent'

// In App component:
<MyComponent />
```

---

## ✅ Success Checklist

After setup, you should:

- [ ] See dashboard at http://localhost:8000
- [ ] Header shows "Status: healthy"
- [ ] Can click "Start New Episode"
- [ ] Episode creates successfully
- [ ] Metrics update automatically
- [ ] No errors in browser console (F12)

**If all checked → You're ready to use! 🎉**

---

## 🚀 Next Steps

### Now You Can:

1. **Create Episodes** - Try all difficulty levels (L1-L5)
2. **Monitor Metrics** - Watch rewards and service health
3. **Track Incidents** - See real-time incident detection
4. **Customize UI** - Edit components in `src/components/`
5. **Add Features** - Build your own components

### Want More Features?

The React dashboard is fully extensible:
- Add more charts
- Create custom views
- Build agent debugging tools
- Add real-time chat
- Integrate WebSockets for live updates

---

## 💡 Pro Tips

1. **Use Dev Mode** when making changes (instant hot reload)
2. **Use Prod Mode** when just using the app (faster)
3. **Check browser console** (F12) for errors
4. **Use React DevTools** browser extension for debugging
5. **Keep backend running** while developing frontend

---

## 🎊 You're Done!

The React dashboard is now running and ready to use.

**No more Gradio connection issues!**
**No more "Waiting for episode..." forever!**
**Just a fast, reliable, modern dashboard that actually works!**

Enjoy your new React dashboard! 🚀
