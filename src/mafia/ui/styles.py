APP_CSS = """
:root {
  --bg: #080706;
  --panel: rgba(15, 14, 12, 0.92);
  --panel-2: rgba(31, 23, 18, 0.92);
  --line: rgba(203, 153, 89, 0.42);
  --gold: #d5ad71;
  --gold-2: #f1d5a0;
  --red: #9b2f28;
  --red-2: #e04a3f;
  --green: #5ca66c;
  --text: #f0e2cc;
  --muted: #b7a48a;
}

.gradio-container {
  background:
    radial-gradient(circle at 50% 42%, rgba(151, 72, 48, 0.22), transparent 34%),
    radial-gradient(circle at 20% 18%, rgba(213, 173, 113, 0.10), transparent 24%),
    linear-gradient(135deg, #080706 0%, #15100e 48%, #060504 100%) !important;
  color: var(--text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

#mafia-root h1, #mafia-root h2, #mafia-root h3 {
  font-family: Georgia, "Times New Roman", serif;
  color: var(--gold-2);
  letter-spacing: 0;
}

#mafia-root .main-grid {
  display: grid;
  grid-template-columns: minmax(250px, 0.8fr) minmax(560px, 2.4fr) minmax(290px, 0.9fr);
  gap: 16px;
  align-items: stretch;
}

.mafia-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--line);
  background: rgba(6, 5, 4, 0.74);
  padding: 12px 18px;
  margin-bottom: 12px;
}

.mafia-title strong {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 34px;
  color: var(--gold-2);
}

.status-line {
  color: var(--muted);
  font-size: 13px;
}

.status-line, .status-line * {
  color: var(--gold-2) !important;
}

.gradio-container .block,
.gradio-container .form,
.gradio-container .form > *,
.gradio-container label,
.gradio-container .wrap {
  background: rgba(12, 10, 9, 0.88) !important;
  border-color: rgba(213, 173, 113, 0.28) !important;
  color: var(--text) !important;
}

.gradio-container input,
.gradio-container textarea,
.gradio-container select,
.gradio-container [role="textbox"],
.gradio-container [data-testid="textbox"],
.gradio-container [data-testid="dropdown"] {
  background: rgba(20, 17, 15, 0.92) !important;
  color: var(--text) !important;
  border-color: rgba(213, 173, 113, 0.22) !important;
}

.gradio-container textarea::placeholder,
.gradio-container input::placeholder {
  color: rgba(240, 226, 204, 0.52) !important;
}

.gradio-container button {
  border: 1px solid rgba(213, 173, 113, 0.34) !important;
  background: linear-gradient(180deg, rgba(40, 35, 30, .95), rgba(17, 15, 13, .95)) !important;
  color: var(--text) !important;
  font-weight: 700 !important;
}

.gradio-container button.primary {
  background: linear-gradient(180deg, rgba(166, 48, 39, .96), rgba(92, 24, 21, .96)) !important;
  color: #fff2dd !important;
}

.gradio-container button:hover {
  border-color: rgba(241, 213, 160, .8) !important;
}

.mafia-board {
  min-height: 615px;
  position: relative;
  border: 1px solid var(--line);
  background:
    linear-gradient(rgba(8, 7, 6, 0.22), rgba(8, 7, 6, 0.42)),
    var(--board-bg),
    radial-gradient(circle at 50% 54%, rgba(213, 173, 113, 0.18), transparent 34%),
    linear-gradient(145deg, rgba(25, 17, 13, 0.95), rgba(4, 4, 4, 0.96));
  background-size: cover, cover, auto, auto;
  background-position: center, center, center, center;
  overflow: hidden;
}

.hud {
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr;
  gap: 10px;
  padding: 14px 18px 0;
  position: relative;
  z-index: 3;
}

.phase-chip, .alive-chip, .timer {
  border: 1px solid var(--line);
  background: rgba(9, 8, 7, 0.84);
  text-align: center;
  padding: 10px;
  color: var(--gold-2);
}

.phase-chip { color: #ffdbac; background: linear-gradient(180deg, rgba(92, 25, 22, .7), rgba(18, 13, 12, .92)); }
.timer { font-size: 36px; line-height: 1; font-family: Georgia, serif; }
.alive-chip { font-size: 11px; }
.alive-chip strong { font-size: 25px; }

.table-ring {
  position: absolute;
  inset: 64px 18px 138px;
  border-radius: 50%;
  border: 1px solid rgba(213, 173, 113, .22);
  box-shadow: inset 0 0 80px rgba(213, 173, 113, .08), 0 0 80px rgba(120, 28, 22, .18);
}

.table-center {
  position: absolute;
  left: 50%;
  top: 51%;
  transform: translate(-50%, -50%);
  width: 260px;
  height: 260px;
  border-radius: 50%;
  border: 1px solid rgba(213, 173, 113, .35);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: rgba(241, 213, 160, .76);
  font-family: Georgia, serif;
  font-size: 20px;
  background: radial-gradient(circle, rgba(213, 173, 113, .08), rgba(0, 0, 0, .10));
  opacity: .86;
}

.pressure-ring {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 170px;
  height: 170px;
  border-radius: 50%;
  border: 2px solid rgba(224, 74, 63, .72);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #ffb7a3;
  background: rgba(69, 14, 12, .36);
  z-index: 2;
}

.pressure-ring strong { font-size: 52px; color: #ffb7a3; }

.seat {
  position: absolute;
  width: 176px;
  transform: translate(-50%, -50%);
  text-align: center;
  z-index: 4;
}

.portrait {
  width: 136px;
  height: 136px;
  margin: 0 auto -12px;
  border-radius: 50%;
  border: 2px solid var(--gold);
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 35% 30%, rgba(255,255,255,.18), transparent 18%),
    linear-gradient(145deg, #322820, #100d0b 65%, #4c211d);
  color: var(--gold-2);
  font-family: Georgia, serif;
  font-size: 34px;
  box-shadow: 0 10px 24px rgba(0,0,0,.45);
  overflow: hidden;
}

.portrait img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.portrait.small { width: 54px; height: 54px; font-size: 18px; margin: 0 auto 8px; }
.seat.human .portrait { border-color: #f4d49b; box-shadow: 0 0 28px rgba(244, 212, 155, .34); }
.seat.accused .portrait { border-color: var(--red-2); box-shadow: 0 0 34px rgba(224,74,63,.46); }
.seat.dead { filter: grayscale(1); opacity: .58; }

.reaction-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid rgba(213,173,113,.35);
  background: rgba(5,5,5,.74);
  color: var(--gold-2);
  font-size: 12px;
  position: relative;
  z-index: 2;
  margin-bottom: -12px;
}

.nameplate {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: 158px;
  padding: 5px 9px;
  border: 1px solid var(--line);
  background: rgba(6,5,4,.92);
  color: var(--text);
}

.seatnum {
  font-family: Georgia, serif;
  color: var(--gold-2);
  font-size: 20px;
}

.pname {
  font-family: Georgia, serif;
  font-weight: 700;
}

.badge {
  font-size: 10px;
  color: #15100e;
  background: var(--gold);
  padding: 1px 5px;
  border-radius: 999px;
}

.subline {
  margin-top: 5px;
  color: var(--muted);
  font-size: 12px;
}

.side-panel {
  border: 1px solid var(--line);
  background: var(--panel);
  padding: 14px;
  min-height: 615px;
}

.side-panel h2 {
  font-size: 17px;
  margin: 2px 0 12px;
  border-bottom: 1px solid rgba(213,173,113,.2);
  padding-bottom: 8px;
}

.ledger-row {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 10px;
  padding: 10px 8px;
  margin-bottom: 8px;
  background: rgba(255,255,255,.035);
  border: 1px solid rgba(213,173,113,.14);
}

.ledger-row.dead { opacity: .55; }
.mini-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--gold);
  color: var(--gold-2);
  font-family: Georgia, serif;
  overflow: hidden;
}
.mini-avatar img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ledger-row strong, .ledger-row span, .ledger-row small { display: block; }
.ledger-row span { color: var(--gold-2); font-size: 13px; }
.ledger-row small { color: var(--muted); font-size: 11px; }

.history, .vote-list { color: var(--muted); padding-left: 18px; font-size: 13px; }

.chat-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 410px;
  overflow: auto;
}

.rail-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 12px;
}

.rail-tabs span {
  border: 1px solid rgba(213,173,113,.28);
  text-align: center;
  padding: 9px;
  color: var(--gold-2);
  font-family: Georgia, serif;
  background: rgba(12,11,10,.78);
}

.rail-tabs .active {
  background: linear-gradient(180deg, rgba(101, 29, 25, .88), rgba(29, 15, 14, .9));
  border-color: rgba(224,74,63,.54);
}

.chat-row {
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(213,173,113,.12);
  padding: 9px;
}
.chat-row.mod { border-color: rgba(224,74,63,.28); background: rgba(82, 24, 19, .22); }
.chat-meta { display: flex; justify-content: space-between; color: var(--gold-2); font-size: 12px; }
.chat-row p { margin: 5px 0 0; color: var(--text); font-size: 13px; line-height: 1.35; }
.empty { color: var(--muted); padding: 20px; text-align: center; }

.reaction-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 14px 0;
}

.reaction-bar span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 32px;
  border: 1px solid rgba(213,173,113,.24);
  background: rgba(255,255,255,.04);
}

.assistant-panel {
  margin-top: 12px;
  border: 1px solid rgba(213,173,113,.28);
  background: rgba(14, 12, 10, .82);
  padding: 12px;
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 7px 9px;
}

.assistant-panel h3, .assistant-panel p {
  grid-column: 1 / -1;
  margin: 0;
}

.assistant-panel p { color: var(--muted); font-size: 12px; }
.assistant-panel button {
  width: 30px;
  height: 28px;
  padding: 0 !important;
}
.assistant-panel span { color: var(--text); font-size: 12px; align-self: center; }

.action-dock {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  display: grid;
  grid-template-columns: repeat(5, 108px);
  gap: 26px;
  z-index: 8;
}

.action-token {
  text-align: center;
  color: var(--muted);
  text-shadow: 0 1px 2px rgba(0,0,0,.65);
}

.action-icon {
  width: 76px;
  height: 76px;
  margin: 0 auto 7px;
  border-radius: 50%;
  border: 1px solid rgba(213,173,113,.58);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34px;
  background: radial-gradient(circle at 35% 25%, rgba(255,255,255,.13), transparent 28%),
    linear-gradient(155deg, rgba(55,43,33,.95), rgba(10,9,8,.96));
  box-shadow: 0 10px 26px rgba(0,0,0,.42);
}

.action-token.active .action-icon {
  border-color: rgba(224,74,63,.9);
  background: radial-gradient(circle at 35% 25%, rgba(255,255,255,.16), transparent 28%),
    linear-gradient(155deg, rgba(130,35,28,.96), rgba(38,14,12,.96));
}

.action-token strong {
  display: block;
  font-family: Georgia, serif;
  color: var(--gold-2);
  font-size: 14px;
}

.action-token span {
  display: block;
  font-size: 10px;
  line-height: 1.2;
}

.coach-panel {
  position: absolute;
  left: 18px;
  bottom: 18px;
  width: 240px;
  border: 1px solid rgba(213,173,113,.36);
  background: rgba(7,6,5,.86);
  padding: 12px;
  z-index: 9;
  box-shadow: 0 0 24px rgba(213,173,113,.12);
}

.coach-panel h3 { margin: 0 0 7px; font-size: 15px; }
.coach-panel p { margin: 0 0 8px; color: var(--text); font-size: 12px; line-height: 1.35; }
.coach-panel small { color: var(--gold-2); }

.replay-strip {
  display: grid;
  grid-template-columns: 54px 1fr;
  gap: 12px;
  margin-top: 12px;
  border: 1px solid var(--line);
  background: rgba(8, 7, 6, .84);
  padding: 12px;
}
.play-dot {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.04);
  color: var(--gold-2);
}
.timeline {
  display: flex;
  gap: 8px;
  overflow: auto;
}
.timeline-item {
  min-width: 116px;
  border-left: 2px solid var(--red);
  background: rgba(255,255,255,.035);
  padding: 8px 10px;
}
.timeline-item span, .timeline-item small { display: block; }
.timeline-item span { color: var(--text); font-size: 12px; }
.timeline-item small { color: var(--muted); font-size: 11px; }

.control-grid {
  display: grid;
  grid-template-columns: 1.2fr .8fr .8fr;
  gap: 10px;
  align-items: end;
}

.endgame-panel {
  margin-top: 14px;
  border: 1px solid var(--line);
  background:
    linear-gradient(rgba(6,5,4,.54), rgba(6,5,4,.74)),
    var(--endgame-bg),
    radial-gradient(circle at 50% 0%, rgba(213, 173, 113, .16), transparent 42%),
    rgba(9,8,7,.94);
  background-size: cover, cover, auto, auto;
  background-position: center;
  padding: 22px;
  text-align: center;
}
.endgame-panel h1 { font-size: 38px; margin: 0 0 4px; }
.reveal-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(86px, 1fr));
  gap: 10px;
  margin: 18px 0;
}
.reveal-card {
  border: 1px solid var(--line);
  background: rgba(255,255,255,.04);
  padding: 10px;
}
.reveal-card span, .reveal-card small { display: block; }
.reveal-card span { color: var(--gold-2); }
.reveal-card small { color: var(--green); }
.reveal-card.dead small { color: var(--red-2); }
.confession {
  max-width: 680px;
  margin: 0 auto;
  border: 1px solid rgba(213,173,113,.22);
  background: rgba(255,255,255,.035);
  padding: 14px 18px;
}
.metrics-table {
  width: 100%;
  border-collapse: collapse;
  color: var(--text);
}
.metrics-table th, .metrics-table td {
  border-bottom: 1px solid rgba(213,173,113,.16);
  padding: 7px 8px;
  text-align: left;
  font-size: 12px;
}
.metrics-table th { color: var(--gold-2); }

@media (max-width: 1050px) {
  #mafia-root .main-grid {
    grid-template-columns: 1fr;
  }
  .mafia-board, .side-panel {
    min-height: auto;
  }
  .mafia-board { height: 680px; }
  .reveal-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
  .control-grid { grid-template-columns: 1fr; }
  .action-dock {
    position: relative;
    left: auto;
    bottom: auto;
    transform: none;
    grid-template-columns: repeat(5, minmax(54px, 1fr));
    gap: 8px;
    padding: 10px;
    margin-top: 520px;
  }
  .action-icon { width: 48px; height: 48px; font-size: 22px; }
  .action-token strong { font-size: 10px; }
  .action-token span { display: none; }
  .coach-panel {
    position: relative;
    left: auto;
    bottom: auto;
    width: auto;
    margin: 10px;
  }
  .seat { width: 120px; }
  .portrait { width: 88px; height: 88px; }
}
"""
