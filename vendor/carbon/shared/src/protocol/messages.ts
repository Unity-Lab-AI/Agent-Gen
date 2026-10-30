// ═══════════════════════════════════════════════════════════════
// WEBSOCKET PROTOCOL - Message types between server and client
// ═══════════════════════════════════════════════════════════════

// every message over the wire follows this envelope
// agreed with Oslo: added id (request/response pairing) and version (protocol evolution)
export interface WSMessage<T = unknown> {
  id: string;       // uuid for request/response pairing
  type: string;
  payload: T;
  ts: number;       // server timestamp (game time)
  seq: number;      // sequence number for ordering
  version: 1;       // protocol version, bump when breaking changes
}

// --- AUTH ---
export interface AuthPayload {
  token: string; // supabase JWT
}

export interface AuthResultPayload {
  success: boolean;
  character_id?: string;
  error?: string;
}

// --- SENSES (server → client) ---
// structured data, client renders into text/cards
export interface SensePayload {
  sight: SightData;
  hearing: HearingData;
  smell: SmellData;
  touch: TouchData;
  taste?: TasteData; // only when actively tasting
}

export interface SightData {
  description: string;           // main area description
  entities: string[];            // clickable/interactive entity names (Oslo requested)
  pois: PointOfInterestData[];   // visible points of interest
  players: NearbyPlayerData[];   // visible players
  animals: NearbyAnimalData[];   // visible wildlife
  visibility: number;            // 0-1 (night, fog, etc.)
  time_of_day: 'dawn' | 'morning' | 'midday' | 'afternoon' | 'dusk' | 'night';
  survival_hints?: string[];     // era-specific survival hints from server
}

export interface HearingData {
  sounds: SoundEvent[];
}

export interface SoundEvent {
  description: string;  // "rustling in the bushes nearby"
  direction: string;    // "north" (if compass known) or "to your left"
  distance: 'close' | 'near' | 'far' | 'distant';
  source_type: 'player' | 'animal' | 'nature' | 'structure' | 'unknown';
}

export interface SmellData {
  scents: ScentEvent[];
}

export interface ScentEvent {
  description: string;  // "smoke from a fire"
  intensity: 'faint' | 'moderate' | 'strong' | 'overwhelming';
  direction?: string;
}

export interface TouchData {
  temperature: 'freezing' | 'cold' | 'cool' | 'comfortable' | 'warm' | 'hot' | 'scorching';
  wind: 'calm' | 'breezy' | 'windy' | 'gusty' | 'gale';
  ground: string;       // "soft dirt" | "rough stone" | "wet grass"
  pain_level: number;   // 0-10
  pain?: number;        // simplified pain indicator (0-10) sent by some server versions
}

export interface TasteData {
  description: string;
  safe: boolean;
}

export interface SettlementBuildingPayload {
  type: string;
  name: string;
  condition: number;
  provides: string;      // what this building provides to the settlement
  operational: boolean;
  position: { x: number; y: number; z: number };
  radius: number;
  storage_capacity?: number;
  stored_inputs?: Record<string, number>;
  stored_outputs?: Record<string, number>;
  production_recipes?: string[];
  workers: number;
}

export interface PointOfInterestData {
  id: string;
  name: string;
  description: string;
  type: string;
  distance: 'here' | 'close' | 'near' | 'far' | 'distant';
  distance_m?: number;
  distance_band?: 'at_feet' | 'nearby' | 'visible' | 'distant';
  direction?: string;
  position?: { x: number; y: number; z: number };
  identified?: boolean;
  sensory_hints?: string[];
  actions: ActionData[];
}

export interface NearbyPlayerData {
  id: string;
  name: string;
  description: string;   // visible appearance
  distance: 'here' | 'close' | 'near' | 'far';
  distance_m?: number;
  direction?: string;    // compass direction if known
  actions: ActionData[];
}

export interface NearbyAnimalData {
  id: string;
  type: string;          // 'wolf', 'deer', 'rabbit'
  description: string;
  distance: 'here' | 'close' | 'near' | 'far';
  distance_m?: number;
  threat_level: 'harmless' | 'cautious' | 'dangerous' | 'deadly' | 'aggressive' | 'hostile';
  actions: ActionData[];
}

// --- ACTIONS ---
export interface ActionData {
  id: string;
  label: string;           // "Pick up", "Examine", "Attack"
  description: string;     // tooltip text
  time_cost: number;       // game minutes to perform
  stamina_cost: number;
  skill_required?: string; // skill name if any
  min_skill_level?: number;
  enabled: boolean;        // can the player actually do this right now
  disabled_reason?: string; // "Too tired" | "Missing tool"
}

// --- PLAYER ACTION (client → server) ---
export interface PlayerActionPayload {
  action_id: string;
  target_id?: string;    // what are we acting on
  params?: Record<string, unknown>; // action-specific params
  body_part?: string;    // targeted body part in combat
  amount?: number;       // quantity for sell/trade/deposit actions
  currency_id?: string;  // currency for sell/trade actions
  weapon_id?: string;    // weapon for siege/combat targeting
  copies?: number;       // number of copies for print action
  [key: string]: unknown; // allow additional action-specific fields
}

// --- COMBAT ---
export interface CombatResultPayload {
  attacker: CombatantInfo;
  defender: CombatantInfo;
  action: string;          // "swing club at head"
  result: 'hit' | 'miss' | 'block' | 'dodge' | 'critical';
  damage?: number;
  body_part?: string;      // "left arm", "torso", "head"
  injury?: string;         // "deep cut", "broken bone", "bruise"
  narrative: string;       // human-readable combat text
  attacker_stamina_after: number;
  defender_health_after: number;
}

export interface CombatantInfo {
  id: string;
  name: string;
  type: 'player' | 'animal';
}

// --- CHAT ---
export interface ChatPayload {
  channel: 'system' | 'whisper' | 'talk' | 'shout' | 'party' | 'clan' | 'local';
  message: string;
  sender_id: string;
  sender_name: string;
  target_id?: string;     // for whisper, who it's directed at
}

// --- INVENTORY ---
export interface InventoryUpdatePayload {
  items: InventoryItem[];
  capacity: number;        // max weight
  current_weight: number;
}

export interface InventoryItem {
  id: string;
  name: string;
  description: string;
  item_type?: string;
  weight: number;
  quantity: number;
  actions: ActionData[];
  properties: Record<string, string | number | boolean>;
}

// --- CRAFTING ---
export interface CraftAttemptPayload {
  item_ids: string[];  // items being combined
}

export interface CraftResultPayload {
  success: boolean;
  result_item?: InventoryItem;
  narrative: string;       // "You strike the flint against the steel..."
  first_discovery: boolean;
  discoverer_name?: string;
  recipe_name?: string;    // player-chosen name if first discovery
}

// --- STATS UPDATE (server → client, periodic) ---
export interface StatsUpdatePayload {
  meters: {
    health: number;
    hunger: number;
    thirst: number;
    stamina: number;
    warmth: number;
    fatigue: number;
    morale: number;
  };
  stats_changed?: Partial<Record<string, number>>;
  skills_changed?: Array<{ id: string; name: string; level: number; xp: number; xp_to_next: number; xp_gained: number; category: string }>;
  character_level?: number;
}

// --- TURNING (rotate body, no movement) ---
export interface TurnPayload {
  direction: 'left' | 'right';
  degrees?: number;          // default 45 (8-point compass), can be any 1-359
}

export interface TurnResultPayload {
  facing: number;            // new facing in degrees (0=N, 90=E, 180=S, 270=W)
  facing_label: string;      // "North", "Southwest", etc.
  narrative: string;         // "You turn to face northeast."
}

// --- MOVEMENT ---
export interface MovePayload {
  direction?: string;        // "forward" | "backward" | "north" (if compass) | "wander"
  toward?: string;           // POI id
  landmark?: string;         // remembered landmark id
  speed?: string;            // legacy compat — maps to travel_mode
  distance?: number;         // custom distance in meters
  travel_mode?: string;      // "creep"|"walk"|"jog"|"run"|"sprint"|"reverse"|"trot"|"gallop"|"pedal"|"car"|"full_throttle"|"train"|"airplane"|"rocket"
}

export interface MoveResultPayload {
  success: boolean;
  new_location: { x: number; y: number; z: number };
  facing: number;            // current facing after move
  facing_label: string;      // "North", "Southwest", etc.
  travel_time: number;       // game minutes elapsed
  stamina_cost: number;
  narrative: string;         // "You walk toward the river..."
  senses: SensePayload;      // full senses update at new location
  travel_warning?: {         // sent when trip would kill the player
    distance: number;
    mode: string;
    stamina_cost: number;
    hunger_cost: number;
    thirst_cost: number;
    travel_minutes: number;
    will_die: boolean;
  };
}

// --- SERVER INFO ---
export interface ServerInfoPayload {
  name: string;
  game_year: number;
  game_day: number;
  eon: string;
  player_count: number;
  time_ratio: number;
  uptime_hours: number;
}

// --- MESSAGE TYPE REGISTRY ---
export type MessageTypeMap = {
  // === CORE (client → server) ===
  'auth': AuthPayload;
  'action': PlayerActionPayload;
  'turn': TurnPayload;
  'move': MovePayload;
  'chat': ChatPayload;
  'craft': CraftAttemptPayload;
  'name_discovery': { recipe_id: string; name: string };
  'heir_select': { heir_id: string };
  'select_character': { character_id: string };
  'kill_character': { character_id: string };
  'create_character': { name: string; sex: string; description?: string };
  'list_characters': {};
  'request_give_up': {};
  'confirm_give_up': { token: string };
  'give_up_confirm': { token: string };
  'taste': { item_id: string };

  // === AGRICULTURE (client → server) ===
  'farm_till': {};
  'farm_plant': { plot_id: string; crop_type: string };
  'farm_water': { plot_id: string };
  'farm_harvest': { plot_id: string };
  'domesticate': { animal_type: string };
  'feed_animal': { animal_id: string };
  'collect_products': { animal_id: string };

  // === CAVES (client → server) ===
  'enter_cave': { cave_entrance_id: string };
  'cave_move': { room_id: string };

  // === MEDICAL (client → server) ===
  'treat_wound': { injury_id: string; medicine_type: string };

  // === SETTLEMENT (client → server) ===
  'settlement_build': { group_id: string; building_type: string };
  // U440: claim an abandoned settlement
  'claim_settlement': { group_id: string };

  // === MAP (client → server) ===
  'request_map': {};

  // === TRADE (client → server) ===
  'trade_propose': { to_character_id: string; offering: Array<{ item_id: string; item_name: string; quantity: number }>; requesting: Array<{ item_id: string; item_name: string; quantity: number }>; currency_id?: string; price?: number };
  'trade_accept': { trade_id: string };
  'trade_reject': { trade_id: string };

  // === GROUPS (client → server) ===
  'group_create': { type: string; name: string };
  'group_join': { group_id: string };
  'group_leave': { group_id: string };

  // === DIPLOMACY (client → server) ===
  'declare_war': { target_group_id: string; casus_belli: string };
  'propose_treaty': { type: string; target_group_id: string; terms: string };
  'break_treaty': { treaty_id: string };
  'impose_sanction': { target_group_id: string; sanction_type: string; reason: string };

  // === CRIME (client → server) ===
  'attempt_theft': { target_id: string };
  'place_bounty': { target_id: string; amount: number; crime_id: string };
  'start_trial': { accused_id: string; crime_id: string };
  'jury_vote': { trial_id: string; guilty: boolean };

  // === APPRENTICESHIP (client → server) ===
  'begin_apprenticeship': { master_id: string; skill_name: string };
  'abandon_apprenticeship': {};

  // === EDUCATION (client → server) ===
  'enroll': { institution_id: string };
  'unenroll': {};

  // === ENTERTAINMENT (client → server) ===
  'create_event': { type: string; name: string; description: string };
  'attend_event': { event_id: string };

  // === SUBSTANCE (client → server) ===
  'use_substance': { item_id: string; substance_type: string };

  // === PROPAGANDA (client → server) ===
  'launch_campaign': { method: string; message: string; narrative_spin: string; target_settlement?: string };

  // === TRADE ROUTES (client → server) ===
  'establish_route': { name: string; to_settlement: string; goods_exported: unknown[]; goods_imported: unknown[] };
  'dispatch_caravan': { route_id: string; guards: number };

  // === NAVAL (client → server) ===
  'board_vessel': { vessel_id: string };
  'disembark_vessel': {};
  'sail': { vessel_id: string; target_x: number; target_y: number };
  'naval_combat': { attacker_vessel_id: string; defender_vessel_id: string };

  // === VEHICLE (client → server) ===
  'board_vehicle': { vehicle_id: string };
  'disembark_vehicle': {};
  'travel_vehicle': { vehicle_id: string; target_x: number; target_y: number; target_z: number };

  // === PROPERTY (client → server) ===
  'property_claim': { name?: string };
  'property_build': { type: string; name?: string };
  'property_lock': { building_id: string };
  'property_abandon': { claim_id: string };

  // === STORAGE (client → server) ===
  'store_item': { building_id: string; item_id: string; quantity?: number };
  'retrieve_item': { building_id: string; item_id: string; quantity?: number };
  'view_storage': { building_id: string };

  // === LOCK/KEY (client → server) ===
  'use_key': { key_item_id: string; target_id: string; lock_name?: string };
  'copy_key': { key_item_id: string };

  // === WATER (client → server) ===
  'fill_container': {};
  'transfer_water': { from_id: string; to_id: string };

  // === MEGAPROJECTS (client → server) ===
  'megaproject_start': { type: string; settlement_id: string };
  'megaproject_contribute': { project_id: string; material_type: string; quantity: number };
  'megaproject_status': { project_id: string };
  'megaproject_list': { settlement_id: string };

  // === ACTIVITIES (client → server) ===
  'request_activities': {};
  'do_activity': { activity_id: string };

  // === ERA PANELS (client → server) ===
  'request_agriculture': {};
  'request_education': {};
  'request_entertainment': {};
  'request_substance': {};
  'observe_sky': {};
  'launch_mission': { destination: string; from?: string };
  'alien_communicate': { species_id: string };
  'name_alien_species': { species_id: string; name: string };
  'collect_gas': {};
  'first_contact': { species_id: string; body_type: string; tech_era: string; disposition: string; description: string };
  'request_propaganda': {};
  'request_apprenticeship': {};
  'request_trade_routes': {};

  // === PREFERENCES (both directions) ===
  'save_prefs': { prefs: Record<string, string> };
  'load_prefs': {};
  'display_prefs': { prefs: Record<string, string> };

  // === COMMUNICATIONS (client → server) ===
  'create_comm_channel': { type: string; name: string; frequency?: number; band?: string };
  'send_comm_message': { channel_id: string; content: string; to_settlement?: string };
  'place_comm_infrastructure': { type: string; position_x: number; position_y: number };
  'request_comm_channels': {};
  'request_comm_messages': { channel_id: string };
  'scan_frequencies': {};
  'maintain_infrastructure': { infra_id: string };

  // === SETTLEMENT (client → server) ===
  'request_settlement': { group_id?: string };

  // === FOLLOWERS (client → server) ===
  'request_followers': {};
  'recruit_follower': {};
  'assign_follower_tasks': { guard?: number; gather?: number; build?: number; research?: number; explore?: number; farm?: number; craft?: number; trade?: number };
  'supply_followers': { food?: number; water?: number; shelter_quality?: number };
  'banish_followers': { count: number };

  // === TECH TREE (client → server) ===
  'request_tech_tree': {};

  // === BOT SYSTEM ===
  'create_bot': { behavior: string; name?: string; custom_script?: string };
  'delete_bot': { bot_character_id: string };
  'disconnect_bot': { bot_character_id: string };
  'reconnect_bot': { bot_character_id: string };
  'change_bot_behavior': { bot_character_id: string; behavior: string };
  'get_bot_status': {};
  'bot_created': { bot_id: string; bot_token: string; ws_url: string; name: string; behavior: string; message: string };
  'bot_deleted': { bot_character_id: string; message: string };
  'bot_disconnected': { bot_character_id: string };
  'bot_reconnected': { bot_character_id: string };
  'bot_status': { bots: Array<{ character_id: string; name: string; behavior: string; active: boolean; current_action: string | null; items_gathered: number; items_crafted: number; kills: number }> };
  'bot_templates': { templates: Array<{ id: string; name: string; description: string; icon: string }> };

  // === GAME STATE ===
  'game_ready': { character_name: string; biome: string; game_year: number; eon: string };

  // === MISC REQUESTS ===
  'request_inventory': {};
  'request_family': {};
  'batch_craft': { recipe_id: string; quantity: number };
  'marry_follower': { companion_id: string };
  'have_child': { companion_id: string };

  // === ECONOMY (client → server) ===
  'deposit': { currency_id: string; amount: number };
  'withdraw': { currency_id: string; amount: number };
  'create_currency': { name: string; symbol: string; material: string };
  'mint_coins': { currency_id: string; amount: number };
  'create_loan': { borrower_id: string; currency_id: string; amount: number; interest_rate: number; due_game_year: number };
  'repay_loan': { loan_id: string; amount: number };
  'transfer_currency': { to_character_id: string; currency_id: string; amount: number };
  'request_economy': {};

  // === MINING (client → server) ===
  'prospect': {};                                                    // prospect current chunk
  'extract': { deposit_id: string };                                 // extract from a deposit by hand/tool
  'build_mine': { deposit_id: string; type: string; name: string };  // build a mine structure
  'mine_assign_workers': { mine_id: string; count: number };
  'mine_maintain': { mine_id: string };
  'pan_gold': {};                                                     // pan for gold in river
  'request_mines': {};                                                // get list of owned mines

  // === NAVIGATION (client → server) ===
  'request_landmarks': {};
  'set_landmark': { name: string };  // mark current location as a personal landmark

  // === LEADERBOARD (client → server) ===
  'request_leaderboard': {};
  'request_discoveries': {};
  'request_timeline': {};

  // === CORE (server → client) ===
  'auth_result': AuthResultPayload;
  'character_list': { characters: Array<{ id: string; name: string; sex: string; age: number; alive: boolean }> };
  'character_created': { character_id: string };
  'senses': SensePayload;
  'stats': StatsUpdatePayload;
  'combat': CombatResultPayload;
  'chat_msg': ChatPayload;
  'inventory': InventoryUpdatePayload;
  'craft_result': CraftResultPayload;
  'turn_result': TurnResultPayload;
  'move_result': MoveResultPayload;
  'server_info': ServerInfoPayload;
  'error': { code: string; message: string };
  'death': { cause: string; narrative: string; heirs: Array<{ id: string; name: string; age: number }> };
  'examine_result': { id: string; name: string; description: string; properties: Record<string, unknown>; weight: number };

  // === WEATHER (server → client) ===
  'weather': { type: string; intensity: number; wind_speed: number; duration_remaining: number; effects: Record<string, number> };

  // === INJURIES (server → client) ===
  'injuries': { injuries: Array<{ id: string; location: string; type: string; severity: string; bleeding: boolean; infected: boolean; treated: boolean; permanent: boolean; description: string }>; stat_modifiers: Record<string, number> };

  // === CAVE (server → client) ===
  'cave_enter': { room: { id: string; name: string; type: string }; description: string; light_level: number; can_see: boolean; connections: string[]; resources: Array<{ id: string; type: string; quantity: number }> };

  // === MAP (server → client) ===
  'map_data': { tech_level: string; visited_chunks: unknown[]; landmarks: unknown[]; settlements: unknown[]; player_position: { cx: number; cy: number }; compass_directions: boolean };

  // === TRADE (server → client) ===
  'trade_offer': { trade_id: string; from_id: string; from_name: string; offering: Array<{ item_id: string; item_name: string; quantity: number }>; requesting: Array<{ item_id: string; item_name: string; quantity: number }> };

  // === DIPLOMACY (server → client) ===
  'war_declared': { aggressor: string; defender: string; casus_belli: string };
  'treaty_proposed': { treaty: { id: string; type: string; proposer: string; proposer_name: string; target: string; terms: string; game_year: number } };
  'sanction_imposed': { sanction: { id: string; imposer: string; target: string; type: string; reason: string; game_year: number } };

  // === CRIME (server → client) ===
  'bounty_posted': { bounty: { id: string; target_id: string; target_name: string; amount: number; posted_by: string; crime_id: string; game_year: number } };
  'trial_started': { trial: { id: string; accused_id: string; accused_name: string; crime_id: string; location: string; judge_id: string } };
  'trial_verdict': { verdict: string; sentence?: string };

  // === LEADERBOARD (server → client) ===
  'landmarks_list': { landmarks: Array<{ id: string; name: string; type: string; position: { x: number; y: number; z: number }; distance: number; description: string }> };
  'storage_contents': { building_id: string; building_name: string; items: Array<{ id: string; item_type: string; name: string; quantity: number; weight: number }>; capacity: number; used: number };
  'leaderboard': { categories: Record<string, Array<{ rank: number; name: string; value: string | number; playerId: string }>> };
  'discoveries_list': { discoveries: Array<{ id: string; name: string; discoveredBy: string; discoveredYear: number; category: string; description: string }> };
  'timeline': { events: Array<{ id: string; event_type: string; description: string; game_year: number; data: Record<string, unknown> }> };

  // === MINING/PROSPECTING (server → client) ===
  'prospect_result': {
    precision: 'feeling' | 'hint' | 'survey' | 'exact';  // based on tools used
    deposits: Array<{
      id: string;
      type: string;              // 'copper_ore', 'gold_ore', etc — only if precision >= hint
      type_hint?: string;        // 'metal', 'mineral', 'fuel' — for feeling precision
      direction?: string;        // 'north', 'beneath you' — for feeling precision
      depth: string;             // 'surface'|'shallow'|'deep'|'very_deep' — only if precision >= survey
      remaining?: number;        // only if precision === 'exact'
      quality?: number;          // only if precision === 'exact'
    }>;
    narrative: string;
    map_overlay?: Array<{        // only if precision >= survey
      cx: number; cy: number;
      deposits: Array<{ type: string; depth: string; size: 'small' | 'medium' | 'large' }>;
    }>;
  };
  'extract_result': {
    success: boolean;
    item_type: string;
    quantity: number;
    narrative: string;
  };
  'mine_status': {
    mines: Array<{
      id: string; name: string; type: string; deposit_type: string;
      workers: number; max_workers: number; daily_output: number;
      condition: number; remaining: number;
    }>;
  };

  // === ACTIVITIES (server → client) ===
  'activities_list': {
    activities: Array<{
      id: string; name: string; description: string;
      duration_minutes: number; stamina_cost: number;
      possible_returns: Array<{ name: string; chance_label: 'likely' | 'possible' | 'rare' }>;
    }>;
  };

  // === ERA PANELS (server → client) ===
  'agriculture_data': {
    plots: Array<{ id: string; crop_type: string; state: string; growth_progress: number; watered: boolean; irrigated: boolean; yield_multiplier: number }>;
    animals: Array<{ id: string; type: string; name: string; age_days: number; health: number; produces: string; tamed: boolean }>;
  };
  'education_data': {
    enrolled: boolean;
    institution: { id: string; name: string; type: string; subjects: string[]; skill_xp_bonus: number } | null;
    available: Array<{ id: string; name: string; type: string; subjects: string[] }>;
  };
  'entertainment_data': {
    events: Array<{ id: string; name: string; type: string; description: string; morale_boost: number; attendees: number; organizer_id: string }>;
  };
  'substance_data': {
    available?: Array<{ type: string; name: string; category: string; era: string; effects: Record<string, number>; addiction_risk: number; overdose_threshold: number; description: string }>;
    active_effects: Array<{ substance_type: string; effects: Record<string, number>; started_at: number; expires_at: number }>;
    addictions: Array<{ substance_type: string; severity: number; last_use_game_minute: number; withdrawal_active: boolean }>;
  };
  'substance_effect': {
    overdose: boolean;
    substance: string;
  };
  'propaganda_data': {
    campaigns: Array<{ id: string; method: string; message: string; narrative_spin: string; launcher_name: string; reach: number; influence_count: number }>;
  };
  'apprenticeship_data': {
    active: boolean;
    apprenticeship: { master_name: string; skill_name: string; progress: number; recipes_learned: string[]; started_day: number } | null;
  };
  'trade_route_data': {
    routes: Array<{ id: string; name: string; from: string; to: string; goods_exported: unknown[]; goods_imported: unknown[]; active_caravans: number; total_revenue: number }>;
  };

  // === COMMUNICATIONS (server → client) ===
  'comm_channels': { channels: Array<{ id: string; type: string; name: string; frequency?: number; range: number; encrypted: boolean }> };
  'comm_messages': { channel_id: string; messages: Array<{ id: string; from_name: string; content: string; sent_at: number; delivered: boolean }> };
  'comm_infrastructure': { infrastructure: Array<{ id: string; type: string; position: { x: number; y: number }; range: number; condition: number; operational: boolean }> };
  'comm_scan_result': { intercepted: Array<{ frequency: number; from_name: string; content: string; encrypted: boolean }> };

  // === SETTLEMENT (server → client) ===
  'settlement_data': {
    id: string;
    name: string;
    type: string;              // camp/village/town/city/metropolis/nation/empire
    founded_year: number;
    population: { players: number; followers: number; effective: number };
    buildings: SettlementBuildingPayload[];
    resources: Record<string, number>;  // communal stockpile
    defenses: { walls: boolean; towers: number; guards: number; rating: number };
    economy: { treasury: number; currency_name: string; tax_rate: number };
    morale: number;
    auto_build: { current_target: string | null; resources_needed: Record<string, number>; progress: number } | null;
  };

  // === FOLLOWERS (server → client) ===
  'follower_info': {
    count: number;
    max: number;
    morale: number;
    loyalty: number;
    names: { singular: string; plural: string; group: string };
    bonuses: {
      health_bonus: number;
      stamina_bonus: number;
      craft_speed: number;
      gather_speed: number;
      combat_bonus: number;
      build_speed: number;
      research_bonus: number;
    };
  };

  // === TECH TREE (server → client) ===
  'tech_tree_data': {
    nodes: Array<{
      id: string;
      name: string;
      requires: string[];
      visibility: 'known' | 'learnable' | 'adjacent' | 'hidden';
    }>;
    eon: string;
  };

  // === ECONOMY STATUS (server → client) ===
  'economy_status': {
    currencies: Array<{ id: string; name: string; symbol: string; material: string; total_minted: number; inflation_rate: number; backing: string; backing_reserve: number }>;
    accounts: Array<{ currency_id: string; balance: number }>;
    loans: Array<{ id: string; amount: number; interest_rate: number; due_game_year: number; paid: boolean }>;
    market_prices: Record<string, number>;
  };

  // === UI UNLOCKS (server → client) — what the player can see based on tech ===
  'ui_unlocks': {
    eon: string;                     // current server eon
    stat_precision: 'vague' | 'rough' | 'numbered' | 'exact';  // how precise meters display
    show_coordinates: boolean;       // compass discovered?
    show_map: boolean;               // mapping discovered?
    show_health_numbers: boolean;    // medicine discovered?
    panels: string[];                // which UI panels to show (era-gated)
    known_recipes: string[];         // what this character knows how to craft
    available_travel_modes: string[]; // travel modes player can use (based on tech + vehicles owned)
  };

  // === ACTION PROGRESS (server → client) ===
  'action_started': { action_id: string; action_label: string; duration_seconds: number; stamina_cost: number };
  'action_complete': { action_id: string; success: boolean; narrative: string };

  // === STORM EVENTS (server → client) ===
  'storm_event': { type: string; description: string; cx: number; cy: number };

  // === ADMIN (client → server) ===
  'admin_status': {};
  'admin_kick': { character_id: string; reason: string };
  'admin_broadcast': { message: string };
  'queue_action': { action_id: string; target_id?: string; body_part?: string };
  'cancel_queue': {};
  'admin_config_get': {};
  'admin_config_set': { config: Record<string, any> };

  // === CHARACTER INFO (server → client) ===
  'character_info': {
    name: string;
    sex: string;
    age: number;
    stats: Record<string, number>;
    meters: Record<string, number>;
    skills: Array<{ id: string; name: string; level: number }>;
    facing: number;
  };

  // === ADMIN (server → client) ===
  'admin_config': { config: Record<string, any>; schema: any };
  'admin_status_result': {
    online_players: Array<{ id: string; name: string; location: { x: number; y: number; z: number } }>;
    game_year: number;
    eon: string;
    uptime_ms: number;
    tick_count: number;
    chunk_cache_size: number;
  };

  // === DIPLOMACY (both directions) ===
  'request_diplomacy': {};
  'diplomacy_data': {
    treaties: Array<{ id: string; party_a: string; party_b: string; type: string; terms: string; active: boolean }>;
    wars: string[];
    reputations: Array<{ group: string; status: string }>;
    my_groups: string[];
  };

  // === CRIME & JUSTICE (both directions) ===
  'request_crime': {};
  'crime_data': {
    crimes: Array<{ id: string; type: string; perpetrator_id: string; victim_id: string; severity: number; timestamp: number }>;
    bounties: Array<{ id: string; target_id: string; reward: number; reason: string; active: boolean }>;
    active_trials: Array<{ id: string; accused_id: string; crime_id: string; verdict: string }>;
    my_record: { crimes_committed: number; times_convicted: number; wanted: boolean };
  };

  // === FACTORY/KNOWLEDGE/NUCLEAR (both directions) ===
  'build_factory': { type: string; name?: string; recipe?: string; materials?: Record<string, number> };
  'assign_workers': { factory_id: string; count: number };
  'request_factory': {};
  'factory_data': {
    factories: Array<{ id: string; type: string; name: string; condition: number; operational: boolean; storage_capacity: number; stored_inputs: Record<string, number>; stored_outputs: Record<string, number>; production_recipes: Array<{ id: string; name: string; inputs: Record<string, number>; output: string; output_qty: number; time_minutes: number }>; workers: number }>;
  };
  'request_knowledge': {};
  'knowledge_data': {
    documents: Array<{ id: string; title: string; type: string; author: string; year_written: number; readable: boolean }>;
    library: Array<{ id: string; title: string; type: string; author: string }>;
    known_recipes_count: number;
    can_print: boolean;
  };
  'request_nuclear': {};
  'nuclear_data': {
    reactors: Array<{ id: string; name: string; condition: number; operational: boolean; fuel_level: number; power_output_kw: number; contamination_risk: number }>;
    warheads: number;
    missile_silos: number;
    total_power_kw: number;
  };

  // === EVENT LOG / MILITARY / ALIEN / BIOTECH ===
  'event_log': { type: string; timestamp: number; text: string; data: unknown };
  'request_military': {};
  'military_data': {
    units: Array<{ id: string; name: string; type: string; count: number; equipment: string[]; morale: number }>;
    weapons: Array<{ id: string; name: string; type: string; damage: number; range: number }>;
    defense_rating: number;
    threats: Array<{ id: string; source: string; severity: number; direction: string }>;
    tech_level: string;
  };
  'request_alien': {};
  'alien_data': {
    contact_made: boolean;
    has_comm_device?: boolean;
    communication_attempts?: number;
    known_species: Array<{
      id: string;
      name: string | null;
      body_type: string;
      tech_era: string;
      disposition: string;
      population: number;
      description: string;
      trade_goods: string[];
      translation_progress: number;
      first_contact_by?: string;
      first_contact_year?: number;
    }>;
    factions: Array<{ name: string; stance: string; translation_progress: number }>;
    translation_progress: number;
  };
  'request_biotech': {};
  'biotech_data': {
    experiments: Array<{ id: string; name: string; type: string; progress: number; status: string }>;
    organisms: Array<{ id: string; name: string; type: string; genome_mapped: boolean }>;
    gene_sequences: Array<{ id: string; name: string; function: string }>;
    research_queue: Array<{ id: string; name: string; eta_minutes: number }>;
  };

  // === COMMUNICATIONS (both directions) ===
  'telegraph_send': { to_settlement: string; message: string };
  'telegraph_message': { from_settlement: string; from_player: string; message: string; sent_at: number; delivered_at: number };
  'radio_broadcast': { frequency: number; message: string; power: number };
  'radio_message': { frequency: number; from_player: string; message: string; signal_strength: number };
  'radio_scan': { band: 'AM' | 'FM' | 'shortwave' | 'UHF' };
  'radio_scan_result': { frequencies: Array<{ freq: number; active: boolean; signal: number }> };
  'radio_jam': { frequency: number; power: number };
  'cctv_feed': { camera_id: string };
  'cctv_alert': { camera_id: string; zone: string; player_id: string; player_name: string; timestamp: number };
  'comms_status': {};
  'comms_status_data': {
    telegraph_connections: Array<{ settlement: string; connected: boolean }>;
    radio_towers: Array<{ id: string; frequency: number; power: number; range: number }>;
    cameras: Array<{ id: string; zone: string; active: boolean }>;
    satellites: Array<{ id: string; type: string; coverage: string }>;
  };
  'satellite_uplink': { message: string; target: string };
  'satellite_message': { from_player: string; message: string; global: boolean };

  // === MARRIAGE / FAMILY (both directions) ===
  'propose_marriage': { target_id: string };
  'marriage_proposal': { from_id: string; from_name: string };
  'accept_marriage': { proposal_from: string };
  'reject_marriage': { proposal_from: string };
  'marriage_result': { success: boolean; spouse_name: string; narrative: string };
  'family_info': {
    spouse?: { id: string; name: string; relation: string };
    children: Array<{ id: string; name: string; age: number }>;
    heirs: Array<{ id: string; name: string; age: number }>;
  };

  // === BANKING (server → client) ===
  // deposit, withdraw, create_loan, repay_loan defined in ECONOMY section above
  'bank_result': { success: boolean; balance?: number; error?: string };

  // === PROXIMITY AWARENESS (server → client) ===
  'player_detected': { player_id: string; player_name: string; distance?: number; direction?: string; era_display: string };
  'player_left_range': { player_id: string };

  // === RESEARCH POOL (both directions) ===
  'contribute_research': { recipe_id: string; xp: number };
  'research_progress': { recipe_id: string; total: number; threshold: number; unlocked: boolean };

  // === ERA PANEL DATA (both directions) ===
  'request_industrial_war': {};
  'industrial_war_data': {
    active_sieges: Array<{ id: string; target: string; attacker: string; progress: number }>;
    wall_integrity: Array<{ type: string; condition: number }>;
    supply_days: number;
    garrison: number;
    attacker_force: number;
  };
  'request_megastructure': {};
  'megastructure_data': {
    projects: Array<{ type: string; name: string; progress: number; resources_invested: Record<string, number>; resources_remaining: Record<string, number> }>;
    available: string[];
  };
  'request_modern_tech': {};
  'modern_tech_data': {
    factories: number;
    automation_level: string;
    power_sources: Array<{ type: string; condition: number; operational: boolean }>;
    production_lines: Array<{ id: string; type: string; recipes: string[]; condition: number }>;
  };
  'request_science': {};
  'science_data': {
    discovered_elements: string[];
    equipment: Array<{ name: string; type: string }>;
  };
  'request_cave': {};
  'cave_data': {
    current_room: { id: string; name: string; type: string; description: string; light_level: number };
    explored_rooms: Array<{ id: string; name: string; type: string; connected_to: string[] }>;
    resources: Array<{ id: string; type: string; quantity: number }>;
    creatures: Array<{ id: string; type: string; threat_level: string; health: number }>;
    exits: string[];
  };
  'request_corporation': {};
  'corporation_data': {
    corps: Array<{ id: string; name: string; type: string; employees: number; revenue: number; stock_price: number; market_cap: number; dividends: number }>;
    stock_prices: Record<string, number>;
  };
  'request_digital': {};
  'digital_data': {
    compute_capacity: number;
    network_status: 'online' | 'degraded' | 'offline';
    software: Array<{ id: string; name: string; type: string; running: boolean; cpu_usage: number }>;
    hacking_attempts: Array<{ id: string; source: string; target: string; success: boolean; timestamp: number }>;
    encryption_level: number;
  };
  'request_galactic': {};
  'galactic_data': {
    stars: Array<{ id: string; name: string; type: string; x: number; y: number; faction_id?: string; colonized: boolean }>;
    factions: Array<{ id: string; name: string; color: string; territory_count: number; relation: string }>;
    trade_routes: Array<{ from_star: string; to_star: string; goods: string[]; revenue: number }>;
    fleets: Array<{ id: string; name: string; faction_id: string; star_id: string; ships: number; power: number }>;
  };

  // === SIEGE / SPACE / COLONY / STARMAP ===
  'request_siege': {};
  'siege_data': {
    wall_sections: Array<{ id: string; type: string; hp: number; max_hp: number; position: string }>;
    supplies: { food: number; water: number; ammo: number; days_remaining: number };
    garrison: { total: number; archers: number; infantry: number; morale: number };
    attacker_force: { total: number; siege_engines: number; morale: number } | null;
    duration_days: number;
  };
  'request_space': {};
  'space_data': {
    has_launch_capability: boolean;
    has_ftl: boolean;
    optics_level: number;            // 0=naked eye, 1=telescope, 2=radio, 3=deep space, 4=quantum
    fuel_reserves: number;
    discovered_bodies: Array<{
      id: string; name: string; type: string; habitable: boolean; atmosphere: boolean;
      gravity: number; resources: Array<{ type: string; abundance: number; extractable: boolean }>;
      discovered_by?: string;
    }>;
    discovered_systems: string[];
    active_mission: { id: string; from_body: string; to_body: string; departure_time: number; arrival_time: number; fuel_used: number; status: string } | null;
    active_missions: Array<{ id: string; character_id: string; from_body: string; to_body: string; status: string }>;
    orbital_stations: any[];
    available_destinations: string[];
    crew: any[];
  };
  'request_colony': {};
  'colony_data': {
    colonies: Array<{ id: string; name: string; location: string; population: number; life_support: number; resources: Record<string, number>; morale: number; habitability: number }>;
  };
  'request_starmap': {};
  'starmap_data': {
    stars: Array<{ id: string; name: string; x: number; y: number; type: string; planets: number; faction: string }>;
    current_position: { x: number; y: number; system: string };
    ftl_routes: Array<{ from: string; to: string; distance: number; charted: boolean }>;
    travel_times: Record<string, number>;
  };

  // === MISSING TYPES (completing U26) ===
  'action_queue': { queue: string[]; max: number };
  'daily_report': {
    day: number;
    tasks: Array<{ task: string; items: Array<{ type: string; name: string; quantity: number }>; narrative: string }>;
    population: number;
    max_population: number;
    morale: number;
    events: string[];
  };
  'intro': { first_spawn: boolean; character_name: string };
  'survival': { meters: Record<string, number> };

  // === MAINTENANCE (server → client) ===
  'maintenance_warning': { minutes_remaining: number; countdown: boolean; restart: boolean };

  // === U261: Missing types added ===
  'equipment_state': { available_slots: string[]; equipped: Record<string, string>; equipped_items: Array<{ slot: string; id: string; name: string; item_type: string; properties: Record<string, unknown> }>; era: string };
  'combat_result': { hit: boolean; miss_type?: string; hit_chance?: number; attacker: string; defender: string; damage: number; narrative: string };
  'unequip': { slot: string };
  'equip': { item_id: string };
  'bot_activated': { bot_id: string; name: string; behavior: string };
  'bot_action_log': { bot_id: string; bot_name: string; action: string; target: string | null; timestamp: number };
  'get_bot_templates': {};
  'ping': { ts: number };
  'pong': { ts: number };

  // === DIVINE / GOD SYSTEM ===
  // client → server
  'check_ascension': {};
  'begin_ritual': {};
  'cancel_ritual': {};
  'ascend': { divine_name: string };
  'god_cast_power': { power_id: string; target_position: { x: number; y: number; z: number }; target_character_id?: string };
  'god_incarnate': { position: { x: number; y: number; z: number }; form: 'divine_form' | 'mortal_disguise' };
  'god_return_omnipresent': {};
  'god_move_view': { position: { x: number; y: number; z: number } };
  'pray': {};
  'offer_to_god': { item_id: string };
  'declare_holy_war': { target_god_id: string };
  'contest_respond': { contest_id: string; power_id: string; energy: number };
  'form_pantheon': { ally_god_id: string; name: string };
  'divine_message_send': { message: string };
  'request_terrain_grid': { radius?: number };

  // server → client
  'ascension_status': {
    requirements: Array<{ name: string; met: boolean; current: string; required: string }>;
    all_met: boolean;
    ritual_active: boolean;
    ritual_remaining_ms: number;
  };
  'ascension_complete': { god_id: string; divine_name: string };
  'god_state': {
    god_id: string;
    name: string;
    alignment: string;
    divine_energy: number;
    max_divine_energy: number;
    grace: number;
    max_grace: number;
    wrath: number;
    max_wrath: number;
    souls: number;
    follower_count: number;
    incarnation: string;
    incarnation_position: { x: number; y: number; z: number } | null;
    powers_unlocked: string[];
    powers: Array<{ id: string; name: string; category: string; description: string; energy_cost: number; soul_cost: number; cooldown_minutes: number; ready: boolean }>;
    pantheon: { id: string; name: string; allies: string[] } | null;
    total_miracles: number;
    total_curses: number;
  };
  'power_cast_result': {
    success: boolean;
    power_id: string;
    narrative: string;
    visual_type: string;
    target_position: { x: number; y: number; z: number };
    area: number;
  };
  'divine_event': {
    type: string;
    god_name: string;
    narrative: string;
    position: { x: number; y: number; z: number };
    area: number;
    visual_type: string;
  };
  'divine_contest': {
    contest_id: string;
    attacker_god: string;
    defender_god: string;
    location: { x: number; y: number; z: number };
    resolved: boolean;
    winner: string | null;
    narrative: string;
  };
  'holy_war_update': {
    war_id: string;
    aggressor_god: string;
    defender_god: string;
    status: string;
    kills: { aggressor: number; defender: number };
  };
  'prayer_received': { character_name: string; energy_gained: number };
  'soul_collected': { character_name: string; total_souls: number };
  'divine_message_received': { god_name: string; message: string };
  // G23 fix: god panel response types (were untyped 'as any' casts)
  'god_followers': {
    followers: Array<{ id: string; name: string; x: number; y: number; z: number; health: number; settlement?: string }>;
    total: number;
  };
  'religion_status': {
    my_religion: { id: string; name: string; follower_count: number; tenets: string[] } | null;
    all_religions: Array<{ id: string; name: string; follower_count: number; god_name?: string }>;
    my_follower_count: number;
    my_temples: number;
  };
  'world_overview': {
    settlements: Array<{ name: string; x: number; y: number; population: number; religion_id?: string; religion_name?: string }>;
    my_religion_id: string;
    total_settlements: number;
  };
  'divine_history': {
    events: Array<{ god_name: string; type: string; narrative: string; position?: { x: number; y: number; z: number }; game_minute: number }>;
    total_miracles: number;
    total_curses: number;
  };
  // U435/U437: divine contest + god combat event types
  'divine_contest_start': {
    type: string; god_name: string; narrative: string;
    position: { x: number; y: number; z: number }; area: number; visual_type: string;
    attacker: string; defender: string;
  };
  'divine_contest': {
    type: string; god_name: string; narrative: string;
    position: { x: number; y: number; z: number }; area: number; visual_type: string;
    attacker: string; defender: string; winner: string | null;
  };
  'god_combat': {
    type: string; narrative: string;
    position: { x: number; y: number; z: number }; area: number; visual_type: string;
    attacker: string; defender: string;
    attacker_energy: number; defender_energy: number;
  };
  'terrain_grid': {
    center: { cx: number; cy: number; cz: number };
    radius: number;
    chunks: Array<{ cx: number; cy: number; cz: number; biome: string; elevation: number; temperature: number; moisture: number; terrain: string; resources: any[] }>;
    player_position: { x: number; y: number; z: number };
  };
};
