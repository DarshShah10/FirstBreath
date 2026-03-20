# MiroFish Emergency Response Dashboard

Modern React TypeScript dashboard for the MiroFish Emergency Response Simulation System.

## Features

- **Real-time Simulation Monitoring** - Track ambulance dispatch, hospital preparation, and patient outcomes
- **Emergency Case Management** - Create and submit new emergency cases for simulation
- **Actionable Intervention Reports** - Get WHO/HOW/WHEN recommendations for optimal response
- **Resource Overview** - View hospitals, ambulances, and routes in the Delhi/NCR region
- **Modern UI/UX** - Clean, professional medical/healthcare design

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast builds
- **React Router** for navigation
- **Lucide React** for icons
- **Axios** for API calls
- **Socket.IO Client** for real-time updates

## Getting Started

### Prerequisites

- Node.js 18+
- MiroFish Backend running on `http://localhost:5001`

### Installation

```bash
cd dashboard
npm install
```

### Development

```bash
npm run dev
```

The dashboard will be available at `http://localhost:3000`

### Build

```bash
npm run build
```

## API Integration

The dashboard connects to the MiroFish Backend API at `/api/v1`:

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/simulations` | Create a new simulation |
| `GET /api/v1/simulations` | List all simulations |
| `GET /api/v1/simulations/:id` | Get simulation status |
| `POST /api/v1/simulations/:id/run` | Run a simulation |
| `POST /api/v1/simulations/:id/cases` | Add emergency case |
| `GET /api/v1/simulations/:id/interventions/:caseId` | Get intervention report |
| `GET /api/v1/resources` | Get all resources |

## Project Structure

```
dashboard/
├── src/
│   ├── api/
│   │   └── index.ts        # API service functions
│   ├── components/         # Reusable components
│   ├── hooks/              # Custom React hooks
│   │   ├── index.ts           # Hooks exports
│   │   ├── useSocket.ts       # Socket.IO real-time connection
│   │   └── useSimulationPolling.ts  # Polling fallback
│   ├── pages/
│   │   ├── Dashboard.tsx   # Main dashboard page
│   │   ├── Dashboard.css
│   │   ├── Simulation.tsx  # Simulation monitoring page
│   │   └── Simulation.css
│   ├── styles/
│   │   └── global.css     # Global styles
│   ├── types/
│   │   └── index.ts       # TypeScript type definitions
│   ├── App.tsx            # Root component
│   ├── main.tsx           # Entry point
│   └── vite-env.d.ts      # Vite type definitions
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## Real-time Updates

The dashboard supports real-time updates via Socket.IO with automatic polling fallback:

### Socket.IO Hook (`useSocket.ts`)
Provides real-time WebSocket connection to the backend:
- Automatic connection/reconnection
- Event handling for `step`, `case_update`, `agent_state`, `alert`
- Subscribe/unsubscribe to simulation rooms

### Polling Hook (`useSimulationPolling.ts`)
Fallback mechanism when WebSocket is unavailable:
- Configurable polling interval
- Automatic state updates
- Results fetching on simulation completion

### Connection Status
The Simulation page displays real-time connection status:
- **Live** (green) - Socket.IO connected
- **Polling** (gray) - Fallback polling mode
- **Offline** (gray) - No connection

## Configuration

The Vite dev server proxies `/api` requests to `http://localhost:5001`. Update `vite.config.ts` to change the backend URL.

## Screenshots

### Dashboard
- Stats overview (simulations, hospitals, ambulances, routes)
- Quick actions (create simulation, report emergency)
- Recent simulations list
- Resource availability

### Simulation View
- Real-time simulation time display
- Control panel (run, pause, stop)
- Agent status monitoring
- Intervention recommendations panel
- Response timeline

## License

MIT
