# Emergency Simulation API V1

REST API + WebSocket layer for the MiroFish Emergency Response Simulation Engine.

## Overview

This API provides a complete interface for:
- Creating and managing emergency response simulations
- Adding emergency cases with patient data
- Running simulations with real-time updates
- Getting actionable intervention recommendations
- Real-time event streaming via WebSocket

## Base URL

```
http://localhost:5001/api/v1
```

## Authentication

Currently no authentication required (development mode).

## Endpoints

### Simulation Management

#### Create Simulation
```http
POST /api/v1/simulations
Content-Type: application/json

{
    "simulation_speed": 1.0,      // 1.0 = real-time, 10.0 = 10x speed
    "mode": "sequential",         // sequential, parallel, async
    "max_concurrent_cases": 100   // Max cases to handle
}
```

#### List Simulations
```http
GET /api/v1/simulations
```

#### Get Simulation Status
```http
GET /api/v1/simulations/{simulation_id}
```

#### Run Simulation
```http
POST /api/v1/simulations/{simulation_id}/run
Content-Type: application/json

{
    "duration_minutes": 60,
    "max_steps": 1000
}
```

#### Pause/Resume/Stop
```http
POST /api/v1/simulations/{simulation_id}/pause
POST /api/v1/simulations/{simulation_id}/resume
POST /api/v1/simulations/{simulation_id}/stop
```

#### Get Results
```http
GET /api/v1/simulations/{simulation_id}/results
```

### Case Management

#### Add Case
```http
POST /api/v1/simulations/{simulation_id}/cases
Content-Type: application/json

{
    "case_id": "optional_case_id",
    "severity": "critical",           // critical, severe, moderate, low
    "emergency_type": "fetal_distress", // fetal_distress, maternal_hemorrhage, etc.
    "location": {
        "lat": 28.61,
        "lng": 77.21,
        "address": "Sector 12, Noida, UP"
    },
    "patient": {
        "gestational_age_weeks": 38,
        "blood_type": "O_positive",
        "complications": ["late_decelerations"],
        "previous_cesarean": false,
        "multiple_gestation": false
    },
    "time_window_minutes": 30
}
```

#### List Cases
```http
GET /api/v1/simulations/{simulation_id}/cases
```

### Intervention Analysis

#### Get Analysis
```http
GET /api/v1/simulations/{simulation_id}/interventions/{case_id}
```

#### Get Critical Interventions
```http
GET /api/v1/simulations/{simulation_id}/interventions/{case_id}/critical?count=3
```

Query parameters:
- `format`: Output format - `detailed`, `brief`, `markdown`, `json` (default: `detailed`)

### Resources

#### Get All Resources
```http
GET /api/v1/resources
```

#### Find Nearest Resources
```http
GET /api/v1/resources/nearest?lat=28.61&lng=77.21&type=all
```

Query parameters:
- `lat`: Latitude (required)
- `lng`: Longitude (required)
- `type`: `hospital`, `ambulance`, or `all` (default: `all`)

### Health & Status

```http
GET /api/v1/health
GET /api/v1/status
```

## Response Format

All responses follow this format:

```json
{
    "success": true,
    "data": { ... }
}
```

On error:
```json
{
    "success": false,
    "error": "Error message"
}
```

## WebSocket Events

Connect to Socket.IO for real-time updates:

```javascript
const socket = io('http://localhost:5001');

socket.on('connect', () => {
    console.log('Connected');
    socket.emit('subscribe', { simulation_id: 'your_sim_id' });
});

socket.on('step', (data) => {
    console.log('Simulation step:', data);
});
```

### Event Types
- `step` - Simulation step completed
- `case_update` - Case status changed
- `agent_state` - Agent state changed
- `alert` - Critical alert

## Example Usage

### Python
```python
import requests

BASE = "http://localhost:5001/api/v1"

# Create simulation
resp = requests.post(f"{BASE}/simulations", json={"simulation_speed": 10.0})
sim_id = resp.json()["simulation_id"]

# Add case
case = {
    "severity": "critical",
    "emergency_type": "fetal_distress",
    "location": {"lat": 28.61, "lng": 77.21, "address": "Sector 12, Noida"},
    "patient": {
        "gestational_age_weeks": 38,
        "blood_type": "O_positive",
        "complications": ["late_decelerations"]
    },
    "time_window_minutes": 30
}
resp = requests.post(f"{BASE}/simulations/{sim_id}/cases", json=case)
case_id = resp.json()["case_id"]

# Run simulation
requests.post(f"{BASE}/simulations/{sim_id}/run", json={"duration_minutes": 10})

# Get intervention report
resp = requests.get(f"{BASE}/simulations/{sim_id}/interventions/{case_id}?format=brief")
print(resp.json()["report"])
```

## Running the Server

```bash
cd backend
pip install -r requirements.txt
python run.py
```

The server will start on `http://0.0.0.0:5001`.

## Testing

Run the test suite:
```bash
python tests/test_api_v1.py
```

## API Version

v1.0.0 - Initial release
