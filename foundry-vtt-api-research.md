# Foundry VTT API Research Report

**Date:** 2026-02-19
**Scope:** REST API, WebSocket API, Community Modules, Data Model
**Foundry VTT Versions Covered:** V11, V12, V13

---

## Executive Summary

1. **Foundry VTT has NO native REST API.** The core application is a Node.js/Express server that serves a web client, but does not expose documented REST endpoints for external programmatic access. All data manipulation is performed through an internal client-side JavaScript API and socket.io WebSocket communication.

2. **Three community solutions bridge this gap:** The **foundryvtt-rest-api** module (ThreeHats) provides a production-ready REST API via a WebSocket relay architecture; **Palantiri** provides JSONRPC over WebSocket; and the legacy **fvtt-module-api** (kakaroto) provides simple HTTP access through an in-browser endpoint.

3. **Foundry's internal API is rich and well-documented.** The Document CRUD system (create/update/delete) works uniformly across all entity types (Actors, Items, Scenes, Tokens, JournalEntries, Playlists, etc.) with standardized methods and hooks.

4. **The Token/Actor relationship is critical to understand.** Linked tokens point directly to world Actors; unlinked tokens use an ActorDelta document that stores only the differences from the base Actor, creating "synthetic actors."

5. **Modules like Tagger and FXMaster provide additional programmatic control.** Tagger enables metadata tagging and querying of any placeable object; FXMaster provides weather/particle/filter effects controllable via macros and flags.

---

## Table of Contents

1. [Foundry VTT Native Server Architecture](#1-foundry-vtt-native-server-architecture)
2. [Community REST API Modules](#2-community-rest-api-modules)
3. [WebSocket / Socket.io API](#3-websocket--socketio-api)
4. [Foundry VTT Data Model](#4-foundry-vtt-data-model)
5. [Document CRUD Operations](#5-document-crud-operations)
6. [Tagger Module API](#6-tagger-module-api)
7. [FXMaster Module API](#7-fxmaster-module-api)
8. [Authentication Methods](#8-authentication-methods)
9. [Bibliography](#9-bibliography)

---

## 1. Foundry VTT Native Server Architecture

### What Foundry VTT IS

Foundry VTT is a Node.js application that:
- Runs an Express.js HTTP server serving the game client (HTML/JS/CSS)
- Uses **socket.io v4** for real-time bidirectional communication between server and clients
- Stores world data in NeDB (flat-file JSON-like databases) or LevelDB (V11+)
- Exposes a rich **client-side JavaScript API** accessible from the browser console, macros, and modules

### Native HTTP Routes (Limited)

Foundry's Express server handles these routes internally, but they are **not documented as a public API**:

| Route | Purpose | Notes |
|-------|---------|-------|
| `/` | Serve the setup/login page | Redirects based on state |
| `/join` | Join a world session | Requires session cookie |
| `/game` | Main game interface | Requires authenticated session |
| `/setup` | Server administration | Requires admin password |
| `/license` | License management | Setup phase only |
| `/players` | Player management | Within active world |
| `/stream` | A/V streaming | WebRTC signaling |

**Important:** These are internal routes for the web client. There is NO official REST API for external programmatic access. The Foundry team has acknowledged feature requests for HTTP authentication/API tokens (GitHub Issue #3568) but has not implemented a public REST API.

### Package Release API (The One True REST Endpoint)

The **only** official REST API endpoint Foundry provides is for **package management**:

```
POST https://api.foundryvtt.com/_api/packages/release_version/
```

This allows module/system developers to programmatically publish package releases. It is NOT for world data manipulation.

---

## 2. Community REST API Modules

### 2.1 foundryvtt-rest-api (ThreeHats) -- RECOMMENDED

**GitHub:** https://github.com/ThreeHats/foundryvtt-rest-api
**Relay Server:** https://github.com/ThreeHats/foundryvtt-rest-api-relay
**Public Instance:** https://foundryvtt-rest-api-relay.fly.dev
**License:** MIT

#### Architecture

```
External App  --(REST/HTTP)-->  Relay Server  --(WebSocket)-->  Foundry Module
                                (Express.js)                    (in-browser)
```

The system has three components:
1. **Foundry VTT Module** - Installed in Foundry, maintains a persistent WebSocket connection to the relay
2. **Relay Server** - Node.js/Express.js backend that translates REST requests into WebSocket messages
3. **External Applications** - Your tools that make standard HTTP requests to the relay

#### Installation

Manifest URL:
```
https://github.com/ThreeHats/foundryvtt-rest-api/releases/latest/download/module.json
```

#### Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| WebSocket Relay URL | `wss://foundryvtt-rest-api-relay.fly.dev/` | Relay connection endpoint |
| API Key | (required) | Authentication credential |
| Log Level | `info` | Logging verbosity |
| Ping Interval | 30s | Keep-alive frequency |
| Max Reconnect Attempts | 20 | Retry limit on disconnect |
| Reconnect Base Delay | 1000ms | Exponential backoff base |

#### Authentication

All requests require the `x-api-key` header:

```bash
curl -X GET "https://foundryvtt-rest-api-relay.fly.dev/api/search" \
  -H "x-api-key: YOUR_API_KEY" \
  -H "x-client-id: YOUR_CLIENT_ID" \
  -G -d "query=goblin" -d "type=Actor"
```

#### API Endpoint Categories

| Endpoint Group | Path Prefix | Purpose |
|----------------|-------------|---------|
| Clients | `/clients` | List connected Foundry worlds/instances |
| Get | `/get` | Read entities (actors, items, scenes, etc.) |
| Create | `/create` | Create new entities |
| Update | `/update` | Modify existing entities |
| Delete | `/delete` | Remove entities |
| Search | `/api/search` | Query/filter entities by type and term |
| Roll | `/roll` | Execute dice rolls |
| Macro | `/macro` | Invoke macros remotely |
| Encounter | `/encounter` | Combat/initiative management |
| DnD5e | `/dnd5e` | D&D 5th Edition specific operations |
| Structure | `/structure` | World metadata and schema info |
| Session | `/session` | Headless Foundry automation |

#### Search Endpoint (Documented)

```bash
GET /api/search
Headers:
  x-api-key: <your-api-key>
  x-client-id: <your-client-id>
Query Parameters:
  query: <search-term>     # e.g., "goblin"
  type: <document-type>    # e.g., "Actor", "Item", "Scene", "JournalEntry"
```

#### Supported Document Types

- **Actors** (characters, NPCs, creatures)
- **Items** (equipment, spells, abilities)
- **Scenes** (maps, environments)
- **Macros** (automation scripts)
- **JournalEntries** (notes, lore)
- **Playlists** (audio)
- **Combat encounters** (initiative, turns)

#### Rate Limiting (Public Relay)

| Tier | Limit |
|------|-------|
| Free | 100 requests/month, 1000/day |
| Premium ($5/mo) | Unlimited |
| Self-hosted | Configurable (set to 999999999 to disable) |

#### Self-Hosting the Relay

Docker Compose:
```yaml
services:
  relay:
    image: threehats/foundryvtt-rest-api-relay:2.1.0
    ports:
      - "3010:3010"
    environment:
      - DB_TYPE=sqlite       # or postgresql, redis, memory
      - NODE_ENV=production
      - PORT=3010
      - WEBSOCKET_PING_INTERVAL_MS=20000
      - CLIENT_CLEANUP_INTERVAL_MS=15000
      - FREE_API_REQUESTS_LIMIT=999999999
      - DAILY_REQUEST_LIMIT=999999999
    volumes:
      - ./data:/app/data
```

### 2.2 Palantiri (JSONRPC WebSocket Proxy)

**GitHub:** https://github.com/dustinlacewell/fvtt-palantiri

#### Architecture

Unlike typical client-server models, Palantiri **reverses the connection**: your application runs a WebSocket server, and the Palantiri Foundry module connects to it as a client (because browsers cannot act as WebSocket servers).

Default connection: `ws://localhost:3000`

#### Protocol: JSONRPC 2.0

```json
{
  "id": 0,
  "jsonrpc": "2.0",
  "method": "namespace.methodName",
  "params": [/* arguments */]
}
```

#### Supported Namespaces (9 Entity Collections)

| Namespace | Entity Type |
|-----------|------------|
| `actors` | Actor documents |
| `items` | Item documents |
| `scenes` | Scene documents |
| `journal` | JournalEntry documents |
| `playlists` | Playlist documents |
| `messages` | ChatMessage documents |
| `tables` | RollTable documents |
| `folders` | Folder documents |
| `users` | User documents |

#### Standard Methods (Available on ALL Namespaces)

| Method | Signature | Description |
|--------|-----------|-------------|
| `all` | `(keys?: string[])` | Get all entities, optionally filter properties |
| `one` | `(id: string)` | Get single entity by ID |
| `get` | `(id: string, key: string)` | Get specific property value |
| `set` | `(id: string, key: string, val: any)` | Update property value |
| `find` | `(key: string, val: any)` | First entity matching property |
| `filter` | `(key: string, val: any)` | All entities matching property |
| `toggle` | `(id: string, key: string)` | Invert boolean property |
| `remove` | `(id: string)` | Delete entity |
| `getFlag` | `(id: string, scope: string, key: string)` | Access namespaced metadata |
| `setFlag` | `(id: string, scope: string, key: string, val: any)` | Store namespaced metadata |

#### Example (Node.js)

```javascript
const WebSocket = require('ws');
const wss = new WebSocket.Server({ port: 3000 });

wss.on('connection', ws => {
  // Receive response
  ws.on('message', msg => {
    const response = JSON.parse(msg);
    console.log(response.result);
  });

  // Request all users (only name and _id fields)
  ws.send(JSON.stringify({
    id: 0,
    jsonrpc: "2.0",
    method: "users.all",
    params: [["name", "_id"]]
  }));

  // Get a specific actor
  ws.send(JSON.stringify({
    id: 1,
    jsonrpc: "2.0",
    method: "actors.one",
    params: ["ACTOR_ID_HERE"]
  }));

  // Update an actor's name
  ws.send(JSON.stringify({
    id: 2,
    jsonrpc: "2.0",
    method: "actors.set",
    params: ["ACTOR_ID_HERE", "name", "New Name"]
  }));

  // Delete an item
  ws.send(JSON.stringify({
    id: 3,
    jsonrpc: "2.0",
    method: "items.remove",
    params: ["ITEM_ID_HERE"]
  }));
});
```

### 2.3 fvtt-module-api (kakaroto) -- Legacy/PoC

**GitHub:** https://github.com/kakaroto/fvtt-module-api

**Status:** Proof of concept, limited maintenance

#### Access

All requests go through:
```
GET /modules/api/api.html?name=<method>&arg0=<json>&arg1=<json>...
```

#### Authentication

Requires the user to be **already logged in with the same browser**. All API calls execute with that user's permissions.

#### Request Format

| Parameter | Description |
|-----------|-------------|
| `name` | API function to call |
| `arg0` - `arg9` | Up to 10 URL-encoded JSON arguments |

#### Response Format

```json
{
  "success": true,
  "result": { /* response data */ },
  "error": null
}
```

#### Examples

```bash
# Get world data
GET /modules/api/api.html?name=world

# Update a playlist sound
GET /modules/api/api.html?name=updatePlaylistSound&arg0={"parentId":"PLAYLIST_ID","data":{"_id":"SOUND_ID","playing":true}}&arg1={"embeddedName":"PlaylistSound"}
```

### 2.4 PlaneShift

**GitHub:** https://github.com/cclloyd/planeshift

**Architecture:** NestJS REST API that uses Puppeteer for headless browser automation to interact with a running Foundry instance.

#### Key Features
- **Authentication:** Discord OAuth, OIDC, API Keys, or no auth
- **Evaluate Endpoint:** Dynamic execution of arbitrary Foundry game operations
- **Supported Version:** FoundryVTT v12
- **Deployment:** Docker Compose recommended
- Requires a dedicated player account (recommended name: `APIUser`)

---

## 3. WebSocket / Socket.io API

### 3.1 How Foundry Uses Socket.io

Foundry Core uses **socket.io v4** for all real-time communication:

- The server maintains socket connections with all connected clients
- The active socket is exposed at `game.socket` in the client
- All document CRUD operations are transmitted via socket events
- The standard socket.io documentation applies directly to Foundry's usage

### 3.2 Module Socket Communication

Before a module can send/receive socket events, it must:

1. Set `"socket": true` in the module's `manifest.json`
2. Emit events with the pattern: `module.{module-name}` or `system.{system-id}`

```javascript
// In module.json:
{
  "socket": true
}

// Emitting a socket event:
game.socket.emit("module.my-cool-module", {
  action: "doSomething",
  data: { key: "value" }
});

// Listening for socket events:
game.socket.on("module.my-cool-module", (data) => {
  console.log("Received:", data);
});
```

### 3.3 Internal Socket Events (Core)

Foundry's core uses these socket event patterns internally:

| Event Pattern | Purpose |
|--------------|---------|
| `modifyDocument` | Single document CRUD operation |
| `manageDocuments` | Batch document operations |
| `module.{name}` | Module-specific communication |
| `system.{id}` | Game system communication |

The `SocketInterface` class provides:
- **`dispatch(eventName, request)`** - Send socket requests to other clients
  - Returns `Promise<SocketResponse>`
  - Parameters: event name string and `DocumentSocketRequest` object

### 3.4 CONFIG.queries Alternative

Modules can register handler functions in `CONFIG.queries` for structured inter-client communication, providing predefined request/response patterns.

### 3.5 External WebSocket Connection

**Direct external connection to Foundry's socket.io is NOT straightforward.** Foundry's socket.io server requires:
1. A valid session cookie (obtained by authenticating through the web UI)
2. Proper socket.io handshake
3. The connection to come from within the game client context

**Community solutions for external WebSocket access:**

1. **foundryvtt-rest-api** - Bridges via relay server (recommended)
2. **Palantiri** - Reverse WebSocket proxy (your app is the server)
3. **Mindflayer** - External hardware token control via WebSocket
4. **socketlib** - Library for easier module-to-module socket communication within Foundry

### 3.6 Connecting Externally (Advanced)

If you need direct socket.io access, you would need to:

```javascript
// 1. Authenticate and get a session cookie
// POST to /join with credentials

// 2. Connect via socket.io client
const io = require("socket.io-client");
const socket = io("http://localhost:30000", {
  extraHeaders: {
    Cookie: "session=<session-cookie-value>"
  }
});

// 3. Listen for events
socket.on("modifyDocument", (data) => {
  console.log("Document modified:", data);
});
```

**Warning:** This is not officially supported and may break between versions.

---

## 4. Foundry VTT Data Model

### 4.1 Document Hierarchy

All Foundry data is organized as **Documents**. The base `Document` class provides standardized CRUD operations. Documents can be:

- **Primary Documents** - Top-level entities stored in collections
- **Embedded Documents** - Nested within primary documents

```
World
├── Actors (collection)
│   ├── Actor
│   │   ├── Items (embedded)
│   │   ├── ActiveEffects (embedded)
│   │   └── PrototypeToken (embedded data)
│   └── ...
├── Items (collection)
├── Scenes (collection)
│   ├── Scene
│   │   ├── Tokens (embedded)
│   │   ├── Walls (embedded)
│   │   ├── AmbientLights (embedded)
│   │   ├── AmbientSounds (embedded)
│   │   ├── Drawings (embedded)
│   │   ├── Tiles (embedded)
│   │   ├── MeasuredTemplates (embedded)
│   │   ├── Notes (embedded)
│   │   └── Regions (embedded, V13+)
│   └── ...
├── JournalEntries (collection)
│   └── JournalEntry
│       └── JournalEntryPages (embedded)
├── Playlists (collection)
│   └── Playlist
│       └── PlaylistSounds (embedded)
├── RollTables (collection)
├── Macros (collection)
├── ChatMessages (collection)
├── Combats (collection)
│   └── Combat
│       └── Combatants (embedded)
├── Folders (collection)
└── Users (collection)
```

### 4.2 SceneData Schema (V13)

```typescript
interface SceneData {
  // Identity
  _id: string | null;
  name: string;                    // Required
  _stats: DocumentStats;
  folder: string | null;
  sort: number;
  flags: DocumentFlags;
  ownership: object;

  // Visual Configuration
  background: TextureData | null;  // Background image/video
  backgroundColor: string | null;  // Canvas background color
  foreground: string | null;       // Foreground overlay
  foregroundElevation: number;
  thumb: string | null;            // Thumbnail image
  width: number;
  height: number;
  padding: number;                 // Buffer space proportion

  // Grid
  grid: GridData;                  // Grid configuration

  // Navigation
  navigation: boolean;             // Show in nav bar
  navName: string;                 // Override display name
  navOrder: number;                // Nav bar sort order
  active: boolean;                 // Currently active scene

  // Embedded Document Collections
  tokens: TokenData[];
  walls: WallData[];
  lights: AmbientLightData[];
  sounds: AmbientSoundData[];
  drawings: DrawingData[];
  tiles: TileData[];
  templates: MeasuredTemplateData[];
  notes: NoteData[];
  regions: RegionData[];           // V13+

  // Vision & Fog
  tokenVision: boolean;            // Require vision to see?
  fog: {
    exploration: boolean;          // Track fog exploration?
    colors: {
      explored: string | null;     // Tint for explored areas
      unexplored: string | null;   // Tint for unexplored areas
    };
    overlay: string | null;        // Fog overlay image/video
    reset: number | null;          // Last reset timestamp
  };

  // Environment
  environment: SceneEnvironmentData;
  weather: string;                 // Named weather effect

  // Audio
  playlist: string | null;        // Auto-play playlist ID
  playlistSound: string | null;   // Specific sound from playlist

  // Journal
  journal: string | null;         // Linked JournalEntry ID
  journalEntryPage: string | null;

  // Initial View
  initial: {
    x: number | null;
    y: number | null;
    scale: number | null;
  };
}
```

### 4.3 TokenData / PrototypeToken Schema (V13)

```typescript
interface TokenData {
  _id: string;
  name: string;
  actorId: string;           // Reference to world Actor
  actorLink: boolean;        // TRUE = linked, FALSE = unlinked/synthetic

  // Position & Dimensions
  x: number;
  y: number;
  elevation: number;
  width: number;             // Grid units
  height: number;            // Grid units
  rotation: number;          // Angle in degrees
  sort: number;

  // Appearance
  texture: TextureData;      // Token image/video
  alpha: number;             // Opacity (0-1)
  hidden: boolean;           // Hidden from players
  locked: boolean;
  lockRotation: boolean;
  shape: number;

  // Display Settings
  displayName: number;       // When to show name (NONE=0, CONTROL=10, etc.)
  displayBars: number;       // When to show bars
  disposition: number;       // HOSTILE=-1, NEUTRAL=0, FRIENDLY=1

  // Resource Bars
  bar1: {                    // Usually HP
    attribute: string;       // e.g., "attributes.hp"
  };
  bar2: {                    // Secondary resource
    attribute: string;
  };

  // Vision & Detection
  sight: {
    enabled: boolean;
    range: number;           // Vision range
    angle: number;           // Vision cone angle
    visionMode: string;      // e.g., "basic", "darkvision"
    attenuation: number;
    brightness: number;
    saturation: number;
    contrast: number;
    color: string | null;
  };
  detectionModes: Array<{
    id: string;
    enabled: boolean;
    range: number;
  }>;

  // Light Emission
  light: LightData;          // Embedded light source config

  // Movement
  movementAction: string;
  _movementHistory: Array<object>;

  // Actor Delta (for unlinked tokens)
  delta: ActorDelta;         // Stores differences from base actor

  // Rings (V12+)
  ring: object;
  turnMarker: object;
  occludable: object;

  // Regions (V13+)
  _regions: string[];

  flags: DocumentFlags;
}
```

### 4.4 Prototype Tokens vs Placed Tokens

```
Actor (in Actors sidebar)
├── prototypeToken          <-- PrototypeToken (configuration template)
│   ├── name, texture, sight, light, displayName, etc.
│   └── This defines DEFAULTS for new tokens
│
└── When dragged to canvas:
    └── TokenDocument       <-- Placed Token (in Scene.tokens)
        ├── Copies prototypeToken settings
        ├── Gets unique _id
        ├── Gets x, y coordinates
        │
        ├── If actorLink = true:
        │   └── Points to world Actor directly
        │       Changes to Actor = changes to Token display
        │       Only ONE logical entity
        │
        └── If actorLink = false:
            └── Creates ActorDelta
                ├── Stores ONLY differences from base Actor
                ├── Has own Items collection
                ├── Has own ActiveEffects collection
                └── Constructs "synthetic actor" on access
```

**Key behavioral differences:**

| Aspect | Linked Token | Unlinked Token |
|--------|-------------|----------------|
| Actor Data | Shared with world Actor | Independent copy via ActorDelta |
| HP Changes | Affect world Actor | Affect only this token |
| Item Changes | Affect world Actor | Affect only this token |
| Use Case | Unique NPCs, PCs | Monsters, minions, duplicates |
| Data Storage | Minimal (just position) | ActorDelta (differences only) |

**Code examples (V11+):**

```javascript
// Creating a linked token
await Token.create({
  actorId: actor.id,
  actorLink: true,
  x: 500, y: 500
}, { parent: canvas.scene });

// Creating an unlinked token with modifications
await Token.create({
  actorId: actor.id,
  actorLink: false,
  delta: {
    name: "Goblin Captain",
    system: { attributes: { hp: { value: 30, max: 30 } } }
  },
  x: 700, y: 500
}, { parent: canvas.scene });

// Updating a token actor (works for both linked and unlinked)
await token.actor.update({ name: "Furious Goblin" });

// Re-linking an unlinked token field to base actor
await token.delta.update({ name: null });

// Bulk update tokens in a scene
const updates = canvas.scene.tokens.map(t => ({
  _id: t.id,
  delta: { name: "Hobgoblin" }
}));
await canvas.scene.updateEmbeddedDocuments("Token", updates);
```

### 4.5 WallData Schema

```typescript
interface WallData {
  _id: string | null;
  c: number[];        // Coordinates: [x0, y0, x1, y1]
  dir: number;        // Direction of effect (0=both, 1=left, 2=right)
  door: number;       // Door type (0=none, 1=door, 2=secret)
  doorSound: string;  // Sound effect on open/close
  ds: number;         // Door state (0=closed, 1=open, 2=locked)
  light: number;      // Light restriction (0=normal, 1=limited, etc.)
  move: number;       // Movement restriction type
  sight: number;      // Vision restriction type
  sound: number;      // Audio restriction type
  threshold: WallThresholdData;  // Proximity threshold config
  flags: DocumentFlags;
}
```

**Wall restriction type values:**
- `0` = NONE (wall does not block)
- `1` = NORMAL (wall blocks)
- `2` = LIMITED (wall is one-way or limited)

### 4.6 LightData Schema (Used by AmbientLight and Token)

```typescript
interface LightData {
  alpha: number;        // Opacity (0-1)
  angle: number;        // Emission angle (degrees, 360 = full circle)
  animation: {          // Animation configuration
    type: string;       // e.g., "torch", "pulse", "flicker"
    speed: number;      // Animation speed
    intensity: number;  // Animation intensity
    reverse: boolean;
  };
  attenuation: number;  // Light falloff (0-1)
  bright: number;       // Bright light radius (grid units)
  color: string;        // Light color (hex)
  coloration: number;   // Coloration mode
  contrast: number;     // Contrast adjustment (-1 to 1)
  darkness: {           // Darkness activation thresholds
    min: number;
    max: number;
  };
  dim: number;          // Dim light radius (grid units)
  luminosity: number;   // Luminosity adjustment
  negative: boolean;    // Whether this creates darkness
  priority: number;     // Rendering priority
  saturation: number;   // Saturation adjustment (-1 to 1)
  shadows: number;      // Shadow intensity (0-1)
}
```

### 4.7 AmbientSoundData Schema

```typescript
interface AmbientSoundData {
  _id: string;
  x: number;           // Position X
  y: number;           // Position Y
  radius: number;      // Audible radius
  path: string;        // Audio file path
  repeat: boolean;     // Loop playback
  volume: number;      // Volume level (0-1)
  walls: boolean;      // Blocked by walls?
  easing: boolean;     // Volume easing
  hidden: boolean;     // Hidden from players
  darkness: {
    min: number;
    max: number;
  };
  effects: string[];   // Applied effects
  flags: DocumentFlags;
}
```

### 4.8 ActorData Schema (Core Fields)

```typescript
interface ActorData {
  _id: string;
  name: string;
  type: string;          // System-defined (e.g., "character", "npc")
  img: string;           // Actor portrait image
  system: object;        // System-specific data (e.g., D&D stats)
  prototypeToken: PrototypeToken;  // Default token configuration
  items: ItemData[];     // Owned items
  effects: ActiveEffectData[];     // Active effects
  folder: string | null;
  sort: number;
  ownership: object;     // Permission levels per user
  flags: DocumentFlags;
  _stats: DocumentStats;
}
```

### 4.9 ItemData Schema (Core Fields)

```typescript
interface ItemData {
  _id: string;
  name: string;
  type: string;          // System-defined (e.g., "weapon", "spell")
  img: string;           // Item image
  system: object;        // System-specific data
  effects: ActiveEffectData[];
  folder: string | null;
  sort: number;
  ownership: object;
  flags: DocumentFlags;
  _stats: DocumentStats;
}
```

### 4.10 JournalEntryData Schema

```typescript
interface JournalEntryData {
  _id: string;
  name: string;
  pages: JournalEntryPageData[];  // Content pages (V10+)
  folder: string | null;
  sort: number;
  ownership: object;
  flags: DocumentFlags;
  _stats: DocumentStats;
}

interface JournalEntryPageData {
  _id: string;
  name: string;
  type: string;      // "text", "image", "video", "pdf"
  title: {
    show: boolean;
    level: number;   // Heading level
  };
  text: {
    content: string;    // HTML content
    format: number;     // 1 = HTML, 2 = Markdown
    markdown: string;   // Raw markdown (if format=2)
  };
  image: {
    caption: string;
    src: string;
  };
  video: {
    controls: boolean;
    loop: boolean;
    autoplay: boolean;
    volume: number;
    timestamp: number;
    width: number;
    height: number;
  };
  src: string;       // Source path for image/video/pdf
  sort: number;
  ownership: object;
  flags: DocumentFlags;
}
```

### 4.11 PlaylistData Schema

```typescript
interface PlaylistData {
  _id: string;
  name: string;
  description: string;
  sounds: PlaylistSoundData[];
  mode: number;          // 0=sequential, 1=shuffle, 2=simultaneous
  playing: boolean;      // Currently playing?
  fade: number;          // Fade duration (ms)
  folder: string | null;
  sort: number;
  seed: number;          // Shuffle seed
  ownership: object;
  flags: DocumentFlags;
  _stats: DocumentStats;
}

interface PlaylistSoundData {
  _id: string;
  name: string;
  description: string;
  path: string;          // Audio file path
  playing: boolean;
  repeat: boolean;       // Loop
  volume: number;        // 0-1
  fade: number;          // Fade duration
  sort: number;
  flags: DocumentFlags;
}
```

---

## 5. Document CRUD Operations

### 5.1 Standardized Methods

All Document types share these static and instance methods:

```javascript
// ===== CREATE =====

// Create a single document
const actor = await Actor.create({
  name: "New Character",
  type: "character",
  img: "icons/svg/mystery-man.svg"
});

// Create multiple documents at once
const actors = await Actor.createDocuments([
  { name: "Guard 1", type: "npc" },
  { name: "Guard 2", type: "npc" }
]);

// Create embedded documents (e.g., Items on an Actor)
const items = await actor.createEmbeddedDocuments("Item", [
  { name: "Sword", type: "weapon" },
  { name: "Shield", type: "equipment" }
]);

// ===== READ =====

// Get by ID
const actor = game.actors.get("ACTOR_ID");

// Get by name
const actor = game.actors.getName("Character Name");

// Get all actors
const allActors = game.actors.contents;

// Filter actors
const npcs = game.actors.filter(a => a.type === "npc");

// Access embedded documents
const items = actor.items;
const effects = actor.effects;

// Access scene tokens
const tokens = canvas.tokens.placeables;
const controlled = canvas.tokens.controlled;  // Selected tokens
const combatTokens = canvas.tokens.placeables.filter(t => t.inCombat);

// ===== UPDATE =====

// Update a document
await actor.update({
  name: "Updated Name",
  "system.attributes.hp.value": 25
});

// Update embedded documents
await actor.updateEmbeddedDocuments("Item", [
  { _id: "ITEM_ID", name: "Magic Sword" }
]);

// Update scene embedded documents (tokens, walls, lights)
await canvas.scene.updateEmbeddedDocuments("Token", [
  { _id: token.id, x: 500, y: 500, rotation: 90 }
]);

await canvas.scene.updateEmbeddedDocuments("AmbientLight", [
  { _id: lightId, "config.bright": 30, "config.dim": 60 }
]);

// ===== DELETE =====

// Delete a document
await actor.delete();

// Delete multiple by ID
await Actor.deleteDocuments(["ID1", "ID2"]);

// Delete embedded documents
await actor.deleteEmbeddedDocuments("Item", ["ITEM_ID_1", "ITEM_ID_2"]);

// Delete all tokens from a scene
const tokenIds = canvas.scene.tokens.map(t => t.id);
await canvas.scene.deleteEmbeddedDocuments("Token", tokenIds);
```

### 5.2 Event Lifecycle / Hooks

Each CRUD operation fires hooks in this order:

```
pre<Operation><DocumentType>    // e.g., preCreateActor, preUpdateToken
<operation><DocumentType>       // e.g., createActor, updateToken
```

```javascript
// Hook into document creation
Hooks.on("preCreateActor", (document, data, options, userId) => {
  // Modify data before creation
  // Return false to prevent creation
});

Hooks.on("createActor", (document, options, userId) => {
  // React after creation
});

Hooks.on("preUpdateToken", (document, changes, options, userId) => {
  // Intercept token updates
});

Hooks.on("updateToken", (document, changes, options, userId) => {
  // React to token movement, visibility changes, etc.
});

Hooks.on("deleteActor", (document, options, userId) => {
  // Cleanup after deletion
});
```

### 5.3 Flags System

Flags provide namespaced key-value storage on any document, used extensively by modules:

```javascript
// Set a flag
await actor.setFlag("my-module", "customProperty", { key: "value" });

// Get a flag
const value = actor.getFlag("my-module", "customProperty");

// Unset a flag
await actor.unsetFlag("my-module", "customProperty");
```

### 5.4 Scene Manipulation Examples

```javascript
// Create a new scene
const scene = await Scene.create({
  name: "Dark Cave",
  background: { src: "path/to/cave-map.webp" },
  width: 4000,
  height: 3000,
  grid: { size: 100, type: 1 },
  tokenVision: true,
  fog: { exploration: true }
});

// Add walls to a scene
await scene.createEmbeddedDocuments("Wall", [
  { c: [100, 100, 500, 100], move: 1, sight: 1, sound: 1, light: 1 },
  { c: [500, 100, 500, 500], move: 1, sight: 1, sound: 1, light: 1 },
  // Door wall
  { c: [200, 100, 300, 100], door: 1, ds: 0, move: 1, sight: 1 }
]);

// Add ambient lights
await scene.createEmbeddedDocuments("AmbientLight", [{
  x: 500, y: 500,
  config: {
    bright: 20,
    dim: 40,
    color: "#ff9900",
    alpha: 0.5,
    angle: 360,
    animation: { type: "torch", speed: 5, intensity: 5 }
  }
}]);

// Add ambient sounds
await scene.createEmbeddedDocuments("AmbientSound", [{
  x: 300, y: 300,
  radius: 20,
  path: "audio/waterfall.ogg",
  volume: 0.8,
  repeat: true,
  walls: true,
  easing: true
}]);

// Place a token
const actor = game.actors.getName("Goblin");
const tokenData = await actor.getTokenDocument({ x: 500, y: 500 });
await scene.createEmbeddedDocuments("Token", [tokenData]);
```

---

## 6. Tagger Module API

**Package:** https://foundryvtt.com/packages/tagger
**GitHub:** https://github.com/fantasycalendar/FoundryVTT-Tagger

### Overview

Tagger allows you to tag any PlaceableObject (Tokens, Tiles, Walls, Lights, Sounds, Drawings, MeasuredTemplates, Notes) with string tags, then query them via a powerful API.

### Tag Rules

| Pattern | Replacement |
|---------|-------------|
| `{#}` | Auto-incrementing number based on scene object count |
| `{id}` | Unique identifier |

Example: `"enemy_{#}_goblin"` becomes `"enemy_1_goblin"`, `"enemy_2_goblin"`, etc.

### Complete API Reference

```javascript
// ===== GET TAGS =====

// Get all tags from an object
const tags = Tagger.getTags(token);
// Returns: ["tag1", "tag2", "tag3"]

// ===== SET TAGS (replace all) =====
await Tagger.setTags(token, ["enemy", "goblin", "patrol_1"]);
// or comma-separated string:
await Tagger.setTags(token, "enemy, goblin, patrol_1");

// ===== ADD TAGS (append) =====
await Tagger.addTags(token, "boss");
await Tagger.addTags([token1, token2], ["tag1", "tag2"]);

// ===== REMOVE TAGS =====
await Tagger.removeTags(token, "patrol_1");

// ===== TOGGLE TAGS =====
await Tagger.toggleTags(token, "highlighted");
// Adds if absent, removes if present

// ===== CLEAR ALL TAGS =====
await Tagger.clearAllTags(token);

// ===== CHECK TAGS =====
const has = Tagger.hasTags(token, "enemy");
// Returns: true/false

const hasOptions = Tagger.hasTags(token, ["enemy", "boss"], {
  matchAny: true,         // Match ANY tag (OR logic). Default: false (AND)
  matchExactly: false,    // Require ONLY these tags, no others
  caseInsensitive: true   // Ignore case
});

// ===== FIND BY TAG (most powerful method) =====

// Find all objects with a specific tag
const enemies = Tagger.getByTag("enemy");
// Returns: Array of PlaceableObjects

// Find with options
const results = Tagger.getByTag("enemy", {
  matchAny: true,          // Match if any tag matches
  matchExactly: false,     // Require exact tag set
  caseInsensitive: true,   // Ignore case
  allScenes: false,        // Search ALL scenes, not just current
  sceneId: "SCENE_ID",    // Search specific scene
  objects: canvas.tokens.placeables,  // Search within subset
  ignore: [someToken]      // Exclude specific objects
});

// Find with regex
const patrol = Tagger.getByTag(/patrol_\d+/);

// Find across all scenes
const allEnemies = Tagger.getByTag("enemy", { allScenes: true });

// ===== APPLY TAG RULES =====
await Tagger.applyTagRules(token);
// Processes {#} and {id} patterns in existing tags
```

### Usage with the REST API

When using Tagger through the foundryvtt-rest-api, you would execute Tagger methods via the macro execution endpoint, since Tagger operates on the client-side API:

```javascript
// Via macro execution through REST API
const macro = `
  const enemies = Tagger.getByTag("enemy");
  return enemies.map(e => ({
    id: e.id,
    name: e.document.name,
    x: e.x,
    y: e.y
  }));
`;
```

---

## 7. FXMaster Module API

**Package:** https://foundryvtt.com/packages/fxmaster/
**GitHub:** https://github.com/gambit07/fxmaster

### Overview

FXMaster provides two categories of visual effects:
1. **Particle Effects** - Weather (rain, snow, fog), animals (bats, crows, spiders), other particles
2. **Filter Effects** - Color overlays, underwater distortion, lightning flashes

### Data Storage

FXMaster stores effect configurations using **Foundry's flag system** on Scene documents:

```javascript
// Effects are stored as flags on the scene
canvas.scene.getFlag("fxmaster", "effects");

// Clear all effects
await canvas.scene.unsetFlag("fxmaster", "effects");
```

### Available Particle Effects

| Effect Key | Description |
|-----------|-------------|
| `rain` | Rain particles |
| `snow` | Snowfall |
| `snowstorm` | Heavy snow with wind |
| `fog` | Fog/mist |
| `clouds` | Cloud cover |
| `embers` | Floating embers |
| `bubbles` | Underwater bubbles |
| `autumnleaves` | Falling leaves |
| `sakura` | Cherry blossom petals |
| `crows` | Flying crows |
| `bats` | Flying bats |
| `spiders` | Crawling spiders |

### Available Filter Effects

| Effect Key | Description |
|-----------|-------------|
| `color` | Color overlay |
| `underwater` | Underwater distortion |
| `lightning` | Lightning flashes |
| `predator` | Predator-style cloaking |
| `bloom` | Bloom/glow |
| `oldfilm` | Old film grain |

### Programmatic Usage

```javascript
// Effects are registered in CONFIG
// CONFIG.fxmaster.particleEffects (replaces deprecated CONFIG.fxmaster.weather)
// CONFIG.fxmaster.filterEffects

// Setting effects on a scene via flags
await canvas.scene.setFlag("fxmaster", "effects", {
  "rain_effect": {
    type: "rain",
    options: {
      density: 0.5,       // Particle density
      speed: 1.0,         // Particle speed
      direction: 180,     // Direction in degrees
      scale: 1.0,         // Particle scale
      tint: null,         // Optional color tint
      // Additional type-specific options
    }
  }
});

// Clearing a specific effect
const effects = canvas.scene.getFlag("fxmaster", "effects") || {};
delete effects["rain_effect"];
await canvas.scene.setFlag("fxmaster", "effects", effects);

// Clearing ALL effects
await canvas.scene.unsetFlag("fxmaster", "effects");
```

### Performance Scaling

Particle count automatically scales with Foundry's Performance Mode:
- Maximum: 100%
- High: 75%
- Medium: 50%
- Low: 25%

### Region Behaviors (V12+)

FXMaster also provides **Region behaviors** for localized particle effects:
- "FXMaster: Particle Effects" region behavior
- Effects only render within the defined region

---

## 8. Authentication Methods

### 8.1 Foundry VTT Native Authentication

Foundry uses **session-based authentication**:

1. **Admin Password** - Set in options.json, used for setup screen
2. **User Passwords** - Per-user passwords for world access
3. **Session Cookie** - Set after successful login at `/join`

There are **no API keys or tokens** in the core product.

### 8.2 foundryvtt-rest-api Authentication

- **API Key** in `x-api-key` header
- **Client ID** in `x-client-id` header
- Keys obtained from relay server registration

### 8.3 PlaneShift Authentication

- Discord OAuth
- OIDC (OpenID Connect)
- API Keys
- Configurable "no auth" mode

### 8.4 fvtt-module-api Authentication

- Relies on existing browser session
- No independent authentication

### 8.5 Palantiri Authentication

- No authentication layer documented
- Security relies on localhost-only connection

---

## 9. Bibliography

### Official Sources

1. [Foundry Virtual Tabletop - API Documentation (Version 13)](https://foundryvtt.com/api/)
2. [SceneData Schema (V13)](https://foundryvtt.com/api/interfaces/foundry.documents.types.SceneData.html)
3. [WallData Schema (V13)](https://foundryvtt.com/api/interfaces/foundry.documents.types.WallData.html)
4. [LightData Class (V13)](https://foundryvtt.com/api/classes/foundry.data.LightData.html)
5. [PrototypeToken Class (V13)](https://foundryvtt.com/api/classes/foundry.data.PrototypeToken.html)
6. [TokenDocument Class (V13)](https://foundryvtt.com/api/classes/foundry.documents.TokenDocument.html)
7. [SocketInterface Class (V13)](https://foundryvtt.com/api/classes/foundry.helpers.SocketInterface.html)
8. [Actor Class (V13)](https://foundryvtt.com/api/classes/foundry.documents.Actor.html)
9. [Version 11 Token/ActorDelta Changes](https://foundryvtt.com/article/v11-actor-delta/)
10. [Package Release API](https://foundryvtt.com/article/package-release-api/)
11. [Tokens Article](https://foundryvtt.com/article/tokens/)
12. [Actors Article](https://foundryvtt.com/article/actors/)
13. [Scenes Article](https://foundryvtt.com/article/scenes/)
14. [Lighting Article](https://foundryvtt.com/article/lighting/)
15. [Ambient Sounds Article](https://foundryvtt.com/article/ambient-sound/)
16. [Macro Commands](https://foundryvtt.com/article/macros/)

### Community Wiki

17. [Foundry VTT Community Wiki - Sockets](https://foundryvtt.wiki/en/development/api/sockets)
18. [Foundry VTT Community Wiki - Document](https://foundryvtt.wiki/en/development/api/document)
19. [Foundry VTT Community Wiki - Data Model](https://foundryvtt.wiki/en/development/api/DataModel)
20. [Foundry VTT Community Wiki - API Documentation](https://foundryvtt.wiki/en/development/api)
21. [Foundry VTT Community Wiki - Actor](https://foundryvtt.wiki/en/development/api/document/actor)

### Community Modules (GitHub)

22. [ThreeHats/foundryvtt-rest-api](https://github.com/ThreeHats/foundryvtt-rest-api) - REST API module
23. [ThreeHats/foundryvtt-rest-api-relay](https://github.com/ThreeHats/foundryvtt-rest-api-relay) - REST API relay server
24. [dustinlacewell/fvtt-palantiri](https://github.com/dustinlacewell/fvtt-palantiri) - WebSocket JSONRPC proxy
25. [kakaroto/fvtt-module-api](https://github.com/kakaroto/fvtt-module-api) - HTTP API module (legacy)
26. [cclloyd/planeshift](https://github.com/cclloyd/planeshift) - NestJS REST API with Puppeteer
27. [fantasycalendar/FoundryVTT-Tagger](https://github.com/fantasycalendar/FoundryVTT-Tagger) - Object tagging module
28. [gambit07/fxmaster](https://github.com/gambit07/fxmaster) - Visual effects module
29. [farling42/foundryvtt-socketlib](https://github.com/farling42/foundryvtt-socketlib) - Socket communication library
30. [foundry-vtt-community/wiki - API Learning](https://github.com/foundry-vtt-community/wiki/blob/main/API-Learning-API.md)

### Package Pages

31. [Foundry REST API Package](https://foundryvtt.com/packages/foundry-rest-api)
32. [HTTP API Package](https://foundryvtt.com/packages/api)
33. [Tagger Package](https://foundryvtt.com/packages/tagger)
34. [FXMaster Package](https://foundryvtt.com/packages/fxmaster/)
35. [socketlib Package](https://foundryvtt.com/packages/socketlib)

### Community

36. [Foundry VTT GitHub Issues - Feature Request #3568 (HTTP Auth)](https://github.com/foundryvtt/foundryvtt/issues/3568)
37. [Foundry REST API Relay - Public Instance](https://foundryvtt-rest-api-relay.fly.dev/)
38. [Foundry REST API Relay - Docs](https://foundryvtt-rest-api-relay.fly.dev/docs/)

---

## Appendix A: Quick Reference - Which Integration Method to Use

| Use Case | Recommended Solution | Notes |
|----------|---------------------|-------|
| External app needs CRUD on world data | foundryvtt-rest-api (ThreeHats) | Production-ready, REST, self-hostable |
| Simple scripting/automation | Palantiri | JSONRPC, easy to set up |
| Need to run within same browser | fvtt-module-api (kakaroto) | Legacy, limited |
| Complex automation with auth | PlaneShift | NestJS, Discord/OIDC auth |
| Tagging and querying objects | Tagger | Powerful query API |
| Visual effects control | FXMaster | Flag-based, macro-friendly |
| Module-to-module communication | socketlib | Within Foundry only |

## Appendix B: Document Type Reference

| Collection Name | Document Class | Embedded In |
|----------------|---------------|-------------|
| `game.actors` | Actor | World |
| `game.items` | Item | World, Actor |
| `game.scenes` | Scene | World |
| `game.journal` | JournalEntry | World |
| `game.playlists` | Playlist | World |
| `game.tables` | RollTable | World |
| `game.macros` | Macro | World |
| `game.messages` | ChatMessage | World |
| `game.combats` | Combat | World |
| `game.folders` | Folder | World |
| `game.users` | User | World |
| `scene.tokens` | TokenDocument | Scene |
| `scene.walls` | WallDocument | Scene |
| `scene.lights` | AmbientLightDocument | Scene |
| `scene.sounds` | AmbientSoundDocument | Scene |
| `scene.drawings` | DrawingDocument | Scene |
| `scene.tiles` | TileDocument | Scene |
| `scene.templates` | MeasuredTemplateDocument | Scene |
| `scene.notes` | NoteDocument | Scene |
| `actor.items` | Item | Actor |
| `actor.effects` | ActiveEffect | Actor |
| `journal.pages` | JournalEntryPage | JournalEntry |
| `playlist.sounds` | PlaylistSound | Playlist |
| `combat.combatants` | Combatant | Combat |
