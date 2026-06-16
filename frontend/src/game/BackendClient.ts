export type Role = 'Mafia' | 'Detective' | 'Doctor' | 'Villager';
export type Phase =
  | 'night'
  | 'dawn'
  | 'discussion'
  | 'hot_seat'
  | 'vote'
  | 'resolution'
  | 'game_over';

export interface PlayerView {
  id: string;
  name: string;
  seat: number;
  alive: boolean;
  isHuman: boolean;
  persona: string;
  modelSpec: string;
  architecture: string;
  team: 'town' | 'mafia' | null;
  role: Role | null;
  claimedRole: Role | null;
  claimConfidence: string;
  keyQuote: string;
  lastVote: string | null;
  publicStatus: string;
  avatar?: string | null;
}

export interface EventView {
  seq: number;
  type: string;
  phase: Phase;
  day: number;
  actor: string | null;
  payload: Record<string, unknown>;
}

export interface Suggestion {
  id: string;
  intent: string;
  tone: string;
  message: string;
}

export interface MafiaGameView {
  gameId: string;
  seed: number;
  mode: string;
  phase: Phase;
  phaseLabel: string;
  day: number;
  winner: 'town' | 'mafia' | null;
  aliveCount: number;
  human: {
    id: string;
    name: string;
    role: Role;
    team: 'town' | 'mafia';
    alive: boolean;
    legalActions: string[];
    privateInfo: Record<string, unknown>;
  };
  players: PlayerView[];
  events: EventView[];
  scene: {
    id: string;
    sceneKey: string;
    title: string;
    subtitle: string;
    objective: string;
    soundCue: string;
  };
  suggestions: Suggestion[];
  lastReceipt: EventView | null;
  public: Record<string, unknown>;
  votes: Record<string, string>;
  lockedVotes: string[];
  hotSeatTarget: string | null;
  dawnMessage: string;
  pendingHumanFloor: boolean;
  targetChoices: { id: string; label: string }[];
  roleChoices: Role[];
  metrics: Record<string, unknown>;
  humanAvatar: string;
}

export interface ReadyView {
  ready: boolean;
  agentMode: string;
  moderator: string;
  playerArchitecture: string;
  checks: { name: string; target?: string; ready: boolean; error?: string }[];
}

export interface NewGameOptions {
  seed: number;
  humanName: string;
  humanRole?: string;
  agentMode: string;
  humanAvatar?: string;
}

export const seatTexturePrefix: Record<string, string> = {
  p1: 'player',
  p2: 'nora',
  p3: 'kai',
  p4: 'mira',
  p5: 'jules',
  p6: 'lena',
  p7: 'owen',
};

export const roleCardKey: Record<Role, string> = {
  Mafia: 'role_card_mafia',
  Detective: 'role_card_detective',
  Doctor: 'role_card_doctor',
  Villager: 'role_card_villager',
};

declare global {
  interface Window {
    __MAFIA_VIEW__?: MafiaGameView;
    __MAFIA_READY__?: ReadyView;
    __MAFIA_PLAYER_NAME__?: string;
    __MAFIA_AGENT_MODE__?: string;
    __MAFIA_AVATAR_ID__?: string;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export class BackendClient {
  async ready(agentMode: string): Promise<ReadyView> {
    return requestJson<ReadyView>('/api/ready', {
      method: 'POST',
      body: JSON.stringify({ agent_mode: agentMode }),
    });
  }

  async newGame(options: NewGameOptions): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>('/api/game', {
      method: 'POST',
      body: JSON.stringify({
        seed: options.seed,
        human_name: options.humanName,
        human_role: options.humanRole ?? 'Random',
        agent_mode: options.agentMode,
        human_avatar: options.humanAvatar ?? 'player',
      }),
    });
  }

  async advance(gameId: string, maxSteps = 1): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>(`/api/game/${gameId}/advance`, {
      method: 'POST',
      body: JSON.stringify({ max_steps: maxSteps }),
    });
  }

  async message(gameId: string, message: string): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>(`/api/game/${gameId}/message`, {
      method: 'POST',
      body: JSON.stringify({ message, source: 'human_typed' }),
    });
  }

  async approveSuggestion(gameId: string, suggestion: Suggestion): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>(`/api/game/${gameId}/approve-suggestion`, {
      method: 'POST',
      body: JSON.stringify({
        suggestion_id: suggestion.id,
        message: suggestion.message,
      }),
    });
  }

  async claim(gameId: string, role: Role): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>(`/api/game/${gameId}/claim`, {
      method: 'POST',
      body: JSON.stringify({ role }),
    });
  }

  async accuse(gameId: string, target: string): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>(`/api/game/${gameId}/accuse`, {
      method: 'POST',
      body: JSON.stringify({ target }),
    });
  }

  async startVote(gameId: string): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>(`/api/game/${gameId}/start-vote`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
  }

  async vote(gameId: string, target: string): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>(`/api/game/${gameId}/vote`, {
      method: 'POST',
      body: JSON.stringify({ target }),
    });
  }

  async nightAction(gameId: string, target: string): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>(`/api/game/${gameId}/night-action`, {
      method: 'POST',
      body: JSON.stringify({ target }),
    });
  }

  async passFloor(gameId: string): Promise<MafiaGameView> {
    return requestJson<MafiaGameView>(`/api/game/${gameId}/pass-floor`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
  }

  async suggestions(gameId: string, target?: string | null): Promise<Suggestion[]> {
    const data = await requestJson<{ suggestions: Suggestion[] }>(`/api/game/${gameId}/suggestions`, {
      method: 'POST',
      body: JSON.stringify({ target }),
    });
    return data.suggestions ?? [];
  }
}

export function actorName(view: MafiaGameView, id: string | null | undefined): string {
  if (!id) return 'Moderator';
  return view.players.find((player) => player.id === id)?.name ?? id;
}

export function targetLabel(view: MafiaGameView, id: string | null | undefined): string {
  if (!id) return 'Unknown';
  const player = view.players.find((item) => item.id === id);
  return player ? `${player.seat}. ${player.name}` : id;
}
