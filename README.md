# ClientSense - A Memory-Powered Freelancer Client Intelligence Agent

ClientSense is a hackathon project built for HackwithHyderabad 3.0 that helps freelancers remember how their clients actually behave across engagements and uses that memory to brief them before new work and proactively flag recurring risk patterns during active projects.

## Features

1. **Log an Interaction** - Freeform text input to log client interactions (calls, emails, milestones, payments)
2. **Client Brief ("Brief me")** - Generates structured brief covering:
   - Payment behavior pattern (on-time / late, with evidence)
   - Revision/scope behavior pattern
   - Communication style notes
   - Red flags with evidence counts
   - Concrete actionable recommendation
3. **Proactive Nudge** - Shows inline flags when new interactions match known patterns

## Technology Stack

- **Backend**: Python (FastAPI)
- **Frontend**: Plain HTML/CSS/JS (single-page application)
- **Memory System**: Hindsight Cloud (https://hindsight.vectorize.io/)
- **LLM Provider**: Groq (openai/gpt-oss-120b or qwen/qwen3-32b)

## Hindsight Memory Integration

ClientSense uses Hindsight's three core operations:
- **retain()**: Stores every client interaction with metadata (client name, timestamp, project details)
- **recall()**: Retrieves interaction history for a specific client when generating briefs
- **reflect()**: Performs agentic reasoning over memory to generate insights and proactive nudges

### Configuration

The memory bank is configured with:
- **Mission**: "I am a business advisor for an independent freelancer. My job is to help them avoid repeating past mistakes with specific clients, spot risk patterns early, and negotiate better terms based on real history."
- **Directives**:
  - "Always cite specific evidence (dates, counts, quotes) when flagging a pattern or risk"
  - "Flag payment risk only when supported by 2 or more instances"
  - "Never fabricate a pattern not backed by retained memory"
- **Disposition**: Moderate skepticism (for honest, not overly agreeable briefs)

## Synthetic Data

The system includes seed data for 3 fictional clients to demonstrate the value proposition:
1. **TechCorp Startup** - Fast payer, low revision count, frequent informal scope-creep
2. **Bloom & Co Boutique** - Chronically late payer (25-35 days against net-15), revision-heavy (5-6 rounds), warm/friendly tone
3. **Meridian Agency** - Strict contract adherence, pays on time, but goes silent then demands rush turnarounds

Each client has 8-12 realistic interaction logs across a 6-month timeline.

## Installation & Setup

### Prerequisites
- Python 3.11+
- Node.js (for frontend development, though plain HTML/JS works without build steps)
- Hindsight Cloud account (apply promo code MEMHACK99 for $50 credit)
- Groq API key

### Backend Setup
1. Clone the repository
2. Navigate to the backend directory: `cd backend`
3. Install dependencies: `pip install -r requirements.txt`
4. Configure environment variables in `.env`:
   ```
   HINDSIGHT_API_KEY=your_hindsight_api_key_here
   HINDSIGHT_ORG_ID=your_org_id_here
   HINDSIGHT_PROJECT_ID=your_project_id_here
   GROQ_API_KEY=your_groq_api_key_here
   APP_NAME=ClientSense
   DEBUG=True
   ```
5. Seed synthetic data: `python ../scripts/seed_data.py`
6. Start the server: `python -m app.main`

### Frontend Setup
1. Open `frontend/index.html` in a web browser
2. The frontend will automatically connect to the backend at `http://localhost:8000`
3. To change the backend URL, edit `frontend/js/brief.js`

## Usage

### Demo Path (Optimized for Presentation)
1. Show a brand-new client with zero history getting a generic, unhelpful brief
2. Switch to "Bloom & Co Boutique" (has 6 months of seeded history) and generate a brief
   - Should surface the late-payment pattern with evidence and revision-count prediction
3. Log a new interaction live ("Bloom & Co asked for a 4th revision") and show the proactive nudge firing immediately
   - Should reference the specific historical pattern it's matching against

### Three Core Flows

#### 1. Log an Interaction
- Enter client name and interaction details in the Log Interaction view
- On submit, calls Hindsight's `retain()` operation
- Shows confirmation and running timeline of past interactions

#### 2. Client Brief ("Brief me")
- Enter client name and click "Get Brief"
- Calls Hindsight's `recall()` to get interaction history
- Uses `reflect()` to generate structured brief covering payment, revisions, communication, red flags, and recommendation
- Displays as clean structured card/summary

#### 3. Proactive Nudge
- After logging a new interaction, automatically runs a quick `reflect()` check
- If new log matches recognized patterns (e.g., another revision request matching revision-heavy history)
- Surfaces inline flag/alert with specific evidence it's matching against
- Feels real-time, not requiring separate button click

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /log-interaction` - Log a client interaction
- `POST /client-brief` - Generate client brief
- `POST /check-nudge` - Check for proactive nudges (called internally after logging)

## Project Structure

```
client-sense/
├── backend/                    # Python/FastAPI backend
│   ├── app/                    # Application code
│   │   ├── main.py             # FastAPI application
│   │   ├── hindsight_client.py # Hindsight API wrapper
│   │   └── config.py           # Configuration management
│   ├── requirements.txt        # Python dependencies
│   ├── .env                    # Environment variables (not in repo)
│   └── test_*.py              # Test scripts
├── frontend/                   # Frontend assets
│   ├── index.html              # Main application page
│   ├── css/                    # Stylesheets
│   │   └── style.css
│   └── js/                     # JavaScript files
│       └── brief.js            # Brief me functionality
├── scripts/                    # Utility scripts
│   └── seed_data.py            # Synthetic data seeder
└── README.md                   # This file
```

## Development Approach

Following the specified build order:
1. ✅ Set up Hindsight Cloud account and configure memory bank
2. ✅ Write and run synthetic data seed script
3. ✅ Build "Brief me" flow end-to-end first (core value proposition)
4. 🔨 Build "Log an interaction" flow
5. 🔨 Build "Proactive nudge" flow
6. 🔨 Wire up minimal, clean frontend for all three flows
7. 🔨 Test full demo path multiple times end-to-end
8. 🔨 Write GitHub README documenting setup and Hindsight usage

## Notes for Demo

- The system is designed to work with real Hindsight memory - no fabricated behavior
- Error handling is implemented around Groq LLM calls (via Hindsight's reflect operation)
- No authentication system needed for MVP (single hardcoded freelancer "user")
- Clean, well-architected code prioritized over feature count

## License

MIT License - see LICENSE file for details