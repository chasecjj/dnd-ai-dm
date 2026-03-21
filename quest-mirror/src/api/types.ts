/**
 * WebSocket protocol types for Quest Mirror.
 *
 * Mirrors web/protocol.py exactly. All message types and data shapes
 * used for communication between the React SPA and the FastAPI/WebSocket backend.
 */

// ── Data Shapes ──────────────────────────────────────────────────

export interface CharacterData {
  name: string;
  race?: string;
  class?: string;
  level?: number;
  hp_current?: number;
  hp_max?: number;
  ac?: number;
  conditions?: string[];
  inventory_notes?: string;
  spell_slots_used?: number;
  spell_slots_max?: number;
}

export interface SceneEntity {
  name: string;
  physical_description?: string;
  holding_items?: string[];
  role_or_relationship?: string;
  current_demeanor?: string;
}

export interface SceneObject {
  name: string;
  holder?: string;
  description?: string;
}

export interface SceneData {
  entities_present?: SceneEntity[];
  objects_in_play?: SceneObject[];
  spatial_notes?: string;
}

export interface ThreadData {
  title?: string;
  importance?: number;
  urgency?: number;
  category?: string;
}

export interface ConsequenceData {
  text?: string;
}

export interface ChaosData {
  chaos_factor: number;
  threads: ThreadData[];
  consequences: string[];
}

export interface EnvironmentData {
  location: string;
  time_of_day?: string;
  chaos?: number;
  preset_hint?: string;
}

export interface TurnData {
  turn: number;
  player_input: string;
  narrative: string;
}

export interface SessionInfo {
  id: string;
  character_name: string;
  current_location: string;
  turn_count: number;
  started_at: string;
  chaos_factor: number;
  status: string;
  is_web?: boolean;
}

// ── Client → Server Messages ────────────────────────────────────

export interface PlayerInputMsg {
  type: "player_input";
  text: string;
  input_type?: string;
}

export interface DiceResultMsg {
  type: "dice_result";
  request_id: string;
  result: number;
  natural: number;
}

export interface SessionEndMsg {
  type: "session_end";
}

export interface UndoMsg {
  type: "undo";
}

export interface HeartbeatMsg {
  type: "heartbeat";
}

export type ClientMsg =
  | PlayerInputMsg
  | DiceResultMsg
  | SessionEndMsg
  | UndoMsg
  | HeartbeatMsg;

// ── Server → Client Messages ────────────────────────────────────

export interface NarrativeStreamMsg {
  type: "narrative_stream";
  text: string;
  mood: string;
  breath_group: number;
  is_final: boolean;
}

export interface RollRequestMsg {
  type: "roll_request";
  request_id: string;
  roll_type: string;
  formula: string;
  prompt: string;
  auto_timeout_s: number;
}

export interface StateUpdateMsg {
  type: "state_update";
  character?: CharacterData | null;
  scene?: SceneData | null;
  world_clock?: Record<string, unknown> | null;
}

export interface EnvironmentChangeMsg {
  type: "environment_change";
  location: string;
  atmosphere: string;
  time_of_day: string;
  chaos: number;
  preset_hint: string;
}

export interface ChaosUpdateMsg {
  type: "chaos_update";
  chaos_factor: number;
  threads: ThreadData[];
  consequences: ConsequenceData[];
}

export interface SessionEventMsg {
  type: "session_event";
  event_type: "start" | "end" | "undo_complete";
  opening_narrative?: string;
  character?: CharacterData | null;
  summary?: Record<string, unknown> | null;
}

export interface StateSyncMsg {
  type: "state_sync";
  character?: CharacterData | null;
  scene?: SceneData | null;
  chaos?: ChaosData | null;
  recent_turns: TurnData[];
  environment?: EnvironmentData | null;
}

export interface ErrorMsg {
  type: "error";
  code: string;
  message: string;
  recoverable: boolean;
}

export interface HeartbeatAckMsg {
  type: "heartbeat_ack";
}

export type ServerMsg =
  | NarrativeStreamMsg
  | RollRequestMsg
  | StateUpdateMsg
  | EnvironmentChangeMsg
  | ChaosUpdateMsg
  | SessionEventMsg
  | StateSyncMsg
  | ErrorMsg
  | HeartbeatAckMsg;
