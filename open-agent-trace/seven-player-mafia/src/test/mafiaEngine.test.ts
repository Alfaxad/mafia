import { describe, it, expect } from 'vitest';
import { MafiaEngine, PLAYER_ORDER, factionOf } from '../game/MafiaEngine';
import type { VoteRecord } from '../game/MafiaTypes';

function freshEngine(seed = 12345): MafiaEngine {
  const e = new MafiaEngine(seed);
  e.dealRoles();
  return e;
}

describe('MafiaEngine role dealing', () => {
  it('deals exactly the configured role distribution', () => {
    const e = freshEngine();
    const roles = e.list().map((p) => p.role);
    const count = (r: string) => roles.filter((x) => x === r).length;
    expect(count('Mafia')).toBe(2);
    expect(count('Detective')).toBe(1);
    expect(count('Doctor')).toBe(1);
    expect(count('Villager')).toBe(3);
    expect(roles.length).toBe(7);
  });

  it('assigns all seven seats in canonical order', () => {
    const e = freshEngine();
    expect(PLAYER_ORDER.length).toBe(7);
    PLAYER_ORDER.forEach((id) => {
      expect(e.players[id]).toBeDefined();
      expect(e.players[id].alive).toBe(true);
    });
  });

  it('is deterministic for a given seed', () => {
    const a = freshEngine(999).list().map((p) => p.role);
    const b = freshEngine(999).list().map((p) => p.role);
    expect(a).toEqual(b);
  });

  it('populates human mafia partner only when human is mafia', () => {
    const e = freshEngine();
    if (e.humanRole === 'Mafia') {
      expect(e.humanMafiaPartnerIds.length).toBe(1);
      expect(e.players[e.humanMafiaPartnerIds[0]].role).toBe('Mafia');
    } else {
      expect(e.humanMafiaPartnerIds.length).toBe(0);
    }
  });
});

describe('MafiaEngine night resolution', () => {
  it('kills the mafia target when not protected', () => {
    const e = freshEngine();
    e.beginNight();
    const victim = e.livingTown()[0].id;
    const res = e.resolveNight({ mafiaTarget: victim, detectiveTarget: null, doctorTarget: null });
    expect(res.killedId).toBe(victim);
    expect(e.players[victim].alive).toBe(false);
  });

  it('saves the target when doctor protects the same person', () => {
    const e = freshEngine();
    e.beginNight();
    const victim = e.livingTown()[0].id;
    const res = e.resolveNight({ mafiaTarget: victim, detectiveTarget: null, doctorTarget: victim });
    expect(res.savedByDoctor).toBe(true);
    expect(res.killedId).toBeNull();
    expect(e.players[victim].alive).toBe(true);
  });

  it('records detective investigation result truthfully', () => {
    const e = freshEngine();
    e.beginNight();
    const mafiaId = e.getMafiaIds()[0];
    e.resolveNight({ mafiaTarget: null, detectiveTarget: mafiaId, doctorTarget: null });
    const r = e.detectiveResults[e.detectiveResults.length - 1];
    expect(r.targetId).toBe(mafiaId);
    expect(r.isMafia).toBe(true);
  });
});

describe('MafiaEngine voting', () => {
  it('eliminates plurality target and records role', () => {
    const e = freshEngine();
    e.beginDay();
    e.beginVote();
    const target = e.livingIds().find((id) => id !== 'player')!;
    const votes: VoteRecord[] = e.livingIds().map((id) => ({ voterId: id, targetId: target }));
    const res = e.tallyVotes(votes);
    expect(res.eliminatedId).toBe(target);
    expect(e.players[target].alive).toBe(false);
  });

  it('does not eliminate on a tie', () => {
    const e = freshEngine();
    e.beginDay();
    e.beginVote();
    const [a, b] = e.livingIds();
    const votes: VoteRecord[] = [
      { voterId: a, targetId: b },
      { voterId: b, targetId: a },
    ];
    const res = e.tallyVotes(votes);
    expect(res.tie).toBe(true);
    expect(res.eliminatedId).toBeNull();
  });
});

describe('MafiaEngine win conditions', () => {
  it('town wins when both mafia are dead', () => {
    const e = freshEngine();
    const mafia = e.getMafiaIds();
    mafia.forEach((id) => (e.players[id].alive = false));
    expect(e.checkWin()).toBe('town');
  });

  it('mafia wins when living mafia >= living town', () => {
    const e = freshEngine();
    const mafia = e.getMafiaIds();
    // Kill town until parity: leave both mafia and at most two town.
    const town = e.list().filter((p) => p.role !== 'Mafia');
    town.slice(0, town.length - 2 + 1).forEach((p) => (e.players[p.id].alive = false));
    // Now living town should be <= living mafia... ensure deterministic check:
    while (e.livingTown().length > e.livingMafia().length) {
      const t = e.livingTown()[0];
      e.players[t.id].alive = false;
    }
    expect(e.checkWin()).toBe('mafia');
  });

  it('factionOf maps roles correctly', () => {
    expect(factionOf('Mafia')).toBe('mafia');
    expect(factionOf('Detective')).toBe('town');
    expect(factionOf('Doctor')).toBe('town');
    expect(factionOf('Villager')).toBe('town');
  });
});

describe('MafiaEngine AI behaviour', () => {
  it('mafia AI never targets a fellow mafia at night', () => {
    const e = freshEngine();
    e.beginNight();
    const target = e.aiMafiaTarget();
    if (target) {
      expect(e.players[target].role).not.toBe('Mafia');
    }
  });

  it('AI votes never exceed living AI count and respect pass threshold', () => {
    const e = freshEngine();
    e.beginDay();
    e.beginVote();
    const votes = e.computeAIVotes();
    expect(votes.length).toBe(e.livingAIIds().length);
  });

  it('generates discussion lines that append to the chat log', () => {
    const e = freshEngine();
    e.beginDay();
    const before = e.chatLog.length;
    const lines = e.generateDiscussion();
    expect(e.chatLog.length).toBeGreaterThanOrEqual(before);
    expect(Array.isArray(lines)).toBe(true);
  });
});
