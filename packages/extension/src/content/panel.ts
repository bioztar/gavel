// The "Chair this meeting" panel — `/compose`, inline, next to the event.
//
// States, in the order a host meets them:
//   brief      the one box, prefilled from the event being edited
//   drafting   waiting on POST /ext/v1/agenda/draft (the server's model call)
//   refuse     the gate: no topics came back; asks GATE_QUESTION inline
//   confirm    the editable table (title / minutes / owner / must hear / type)
//   sending    POST /ext/v1/agendas, then the write into the real event
//   done       what was written, what still needs the host's Save
//   error
//
// Everything rendered is built with `h()` and `textContent`; every string read
// from the page or from the server goes through `sanitize.ts` first.

import { DEFAULT_ENFORCEMENT, buildAgenda, isRegistrable, newSessionId } from "../lib/agenda.js";
import { briefFrom } from "../lib/description.js";
import { GATE_BODY, GATE_HEADLINE, GATE_HINT, GATE_QUESTION, briefWithAgenda, gate, withSpareRow } from "../lib/gate.js";
import { send, type Response } from "../lib/messages.js";
import { cleanHttpUrl, cleanLine, cleanMinutes, cleanText } from "../lib/sanitize.js";
import type { ConfirmState, Draft, Enforcement, EventContext, Person, TopicRow } from "../lib/types.js";
import { clear, h } from "./dom.js";
import css from "./panel.css";

export { css };

/** What the two content scripts provide: how to read the event, and — where a
 *  live editor exists — how to put text into it so the host's own Save carries
 *  the agenda even for an event that has no id yet. */
export interface Surface {
  read(): EventContext;
  writeDescription?(text: string): boolean;
  addGuest?(email: string): boolean;
}

type State =
  | { name: "brief"; brief: string; typed: string; error?: string }
  | { name: "drafting"; brief: string; typed: string }
  | { name: "refuse"; brief: string; typed: string }
  | { name: "confirm"; brief: string; draft: Draft | null; state: ConfirmState }
  | { name: "sending"; state: ConfirmState }
  | { name: "done"; response: Extract<Response, { ok: true; type: "register" }>; writes: { description: boolean; guest: boolean } }
  | { name: "error"; message: string; back: State };

export class Panel {
  private readonly el: HTMLElement;
  private context: EventContext;
  private host: Person | null = null;
  private state: State;

  constructor(
    private readonly root: ShadowRoot,
    private readonly surface: Surface,
  ) {
    this.context = surface.read();
    this.state = { name: "brief", brief: initialBrief(this.context), typed: "" };
    this.el = h("section", { class: "gv-panel", role: "dialog", "aria-label": "Chair this meeting" });
    root.append(this.el);
    void this.whoami();
    void this.lookup();
    this.render();
  }

  /** Fill in what the page did not show (the Meet pre-join screen shows no
   *  guests or description) from the saved event, when there is one. */
  private async lookup(): Promise<void> {
    const { eventId, meetCode } = this.context;
    if (!eventId && !meetCode) return;
    const r = await send({ type: "lookup", eventId, meetCode });
    if (!r.ok || r.type !== "lookup" || !r.event) return;
    const e = r.event;
    this.syncTyping();
    const untouched = this.state.name === "brief" && this.state.brief === initialBrief(this.context);
    this.context = {
      ...this.context,
      eventId: this.context.eventId ?? e.eventId,
      title: this.context.title || e.title,
      description: this.context.description || e.description,
      attendees: this.context.attendees.length ? this.context.attendees : e.attendees,
      start: this.context.start ?? e.start,
      durationMinutes: this.context.durationMinutes ?? e.durationMinutes,
    };
    // Only refill the box if the host has not started typing in it.
    if (untouched && this.state.name === "brief") this.state = { ...this.state, brief: initialBrief(this.context) };
    this.render();
  }

  close(): void {
    this.el.remove();
  }

  private async whoami(): Promise<void> {
    const r = await send({ type: "whoami" });
    if (r.ok && r.type === "whoami" && r.user) {
      this.host = { name: cleanLine(r.user.name ?? "") || r.user.email.split("@")[0]!, email: r.user.email };
      this.render();
    }
  }

  private set(next: State): void {
    this.state = next;
    this.render();
  }

  // ---- actions -------------------------------------------------------------

  /** Re-read the live editor (the host may have added a guest since), keeping
   *  anything only the lookup knew. */
  private refresh(): EventContext {
    const live = this.surface.read();
    this.context = {
      ...this.context,
      title: live.title || this.context.title,
      description: live.description || this.context.description,
      attendees: live.attendees.length ? live.attendees : this.context.attendees,
      start: live.start ?? this.context.start,
      durationMinutes: live.durationMinutes ?? this.context.durationMinutes,
    };
    return this.context;
  }

  private async draft(brief: string, typed: string): Promise<void> {
    this.refresh();
    this.set({ name: "drafting", brief, typed });
    const combined = briefWithAgenda(brief, typed);
    const r = await send({ type: "draft", brief: combined, attendees: this.context.attendees, timezone: this.context.timezone });
    if (!r.ok) {
      this.set({ name: "error", message: describe(r), back: { name: "brief", brief, typed } });
      return;
    }
    if (r.type !== "draft") return;

    // The draft call may have been the moment the host signed in.
    if (!this.host) await this.whoami();
    const people = this.people();
    const outcome = gate(r.parsed, typed, people);
    if (outcome.kind === "refuse") {
      this.set({ name: "refuse", brief, typed: outcome.typed });
      return;
    }
    const draft = outcome.draft;
    this.set({
      name: "confirm",
      brief,
      draft,
      state: {
        title: cleanLine(this.context.title || draft?.title || "", 300),
        purpose: cleanLine(draft?.purpose ?? "", 1000),
        start: this.context.start ?? draft?.start ?? null,
        durationMinutes: this.context.durationMinutes ?? draft?.durationMinutes ?? 30,
        attendees: people,
        rows: outcome.rows,
        enforcement: DEFAULT_ENFORCEMENT,
      },
    });
  }

  private async register(state: ConfirmState): Promise<void> {
    const host = this.host ?? state.attendees[0];
    if (!host) {
      this.set({ name: "error", message: "Sign in first so the agenda has a host.", back: this.state });
      return;
    }
    const agenda = buildAgenda({ state, host, sessionId: newSessionId() });
    if (!isRegistrable(agenda)) {
      // Every row was blanked out in the table — that is the gate again.
      this.set({ name: "refuse", brief: this.currentBrief(), typed: "" });
      return;
    }
    this.set({ name: "sending", state });
    const r = await send({ type: "register", context: this.refresh(), state, agenda });
    if (!r.ok) {
      this.set({ name: "error", message: describe(r), back: { name: "confirm", brief: this.currentBrief(), draft: null, state } });
      return;
    }
    if (r.type !== "register") return;
    const writes = { description: false, guest: false };
    if (!r.wrote.description && this.surface.writeDescription) writes.description = this.surface.writeDescription(r.description);
    if (this.surface.addGuest) writes.guest = this.surface.addGuest(r.botEmail);
    this.set({ name: "done", response: r, writes });
  }

  private people(): Person[] {
    const list = [...this.context.attendees];
    if (this.host && !list.some((p) => p.email === this.host!.email)) list.unshift(this.host);
    return list;
  }

  private currentBrief(): string {
    const s = this.state;
    return "brief" in s ? s.brief : initialBrief(this.context);
  }

  // ---- rendering -----------------------------------------------------------

  /** `whoami` / `lookup` resolve while the host may already be typing; keep
   *  what is in the box across the re-render. */
  private syncTyping(): void {
    const typing = this.el.querySelector("textarea");
    if (!(typing instanceof HTMLTextAreaElement)) return;
    if (this.state.name === "brief") this.state = { ...this.state, brief: typing.value };
    if (this.state.name === "refuse") this.state = { ...this.state, typed: typing.value };
  }

  private render(): void {
    this.syncTyping();
    clear(this.el);
    const closeBtn = h("button", { class: "gv-close", "aria-label": "Close", type: "button" }, "\u00d7");
    closeBtn.addEventListener("click", () => this.close());
    this.el.append(h("header", { class: "gv-head" }, h("span", {}, "\u2696 Chair this meeting"), closeBtn));
    const body = h("div", { class: "gv-body" });
    this.el.append(body);

    const s = this.state;
    switch (s.name) {
      case "brief":
        this.renderBrief(body, s.brief, s.typed, s.error);
        break;
      case "drafting":
        body.append(h("p", {}, h("span", { class: "gv-spin" }), "Reading the brief\u2026"));
        break;
      case "refuse":
        this.renderRefuse(body, s.brief, s.typed);
        break;
      case "confirm":
        this.renderConfirm(body, s.state);
        break;
      case "sending":
        body.append(h("p", {}, h("span", { class: "gv-spin" }), "Registering the agenda and writing the invite\u2026"));
        break;
      case "done":
        this.renderDone(body, s);
        break;
      case "error": {
        body.append(h("div", { class: "gv-error" }, s.message));
        const back = h("button", { class: "gv-btn", type: "button" }, "Back");
        back.addEventListener("click", () => this.set(s.back));
        body.append(h("div", { class: "gv-actions" }, back));
        break;
      }
    }
  }

  private renderBrief(body: HTMLElement, brief: string, typed: string, error?: string): void {
    const who = this.people();
    body.append(
      h("p", { class: "gv-muted" }, "Say what the call is for, who is on it and what it needs to decide. The agenda, owners and time budgets come back for you to check."),
    );
    const ta = h("textarea", { "aria-label": "Brief", placeholder: "Thursday 2pm, 30 minutes: decide the launch date with Ana and Artem\u2026" });
    ta.value = brief;
    body.append(ta);
    if (who.length) body.append(h("p", { class: "gv-people" }, `On the invite: ${who.map((p) => p.name).join(", ")}`));
    if (error) body.append(h("div", { class: "gv-error" }, error));
    const go = h("button", { class: "gv-btn gv-primary", type: "button" }, "Draft the agenda");
    go.addEventListener("click", () => {
      const text = cleanText(ta.value).trim();
      if (!text) {
        this.set({ name: "brief", brief: "", typed, error: "Write a sentence about the meeting first." });
        return;
      }
      void this.draft(text, typed);
    });
    body.append(h("div", { class: "gv-actions" }, go));
  }

  /** The gate. Same three lines as `render_gate_html`, same one question. */
  private renderRefuse(body: HTMLElement, brief: string, typed: string): void {
    const ta = h("textarea", { "aria-label": GATE_QUESTION, placeholder: GATE_HINT });
    ta.value = typed;
    body.append(
      h("div", { class: "gv-gate", role: "alert" }, h("h3", {}, GATE_HEADLINE), h("p", {}, GATE_BODY), h("p", { class: "gv-question" }, GATE_QUESTION)),
      h("p", { class: "gv-muted" }, "One line per topic is enough. It goes back through the same reading, together with the brief."),
      ta,
    );
    const back = h("button", { class: "gv-btn", type: "button" }, "Edit the brief");
    back.addEventListener("click", () => this.set({ name: "brief", brief, typed: ta.value }));
    const go = h("button", { class: "gv-btn gv-primary", type: "button" }, "Try again");
    go.addEventListener("click", () => void this.draft(brief, cleanText(ta.value)));
    body.append(h("div", { class: "gv-actions" }, back, go));
  }

  private renderConfirm(body: HTMLElement, state: ConfirmState): void {
    const title = h("input", { type: "text", "aria-label": "Title" });
    title.value = state.title;
    const purpose = h("input", { type: "text", "aria-label": "Purpose", placeholder: "What this call has to decide" });
    purpose.value = state.purpose;
    const minutes = h("input", { type: "number", min: "1", step: "1", "aria-label": "Duration (minutes)" });
    minutes.value = String(state.durationMinutes);
    const enforcement = h("select", { "aria-label": "Enforcement" });
    for (const level of ["low", "medium", "high"] as Enforcement[]) {
      const opt = h("option", { value: level }, level[0]!.toUpperCase() + level.slice(1));
      if (level === state.enforcement) opt.selected = true;
      enforcement.append(opt);
    }

    const table = h("table", { class: "gv-rows" });
    table.append(
      h("thead", {}, h("tr", {}, h("th", {}, "Topic"), h("th", { class: "gv-col-min" }, "Min"), h("th", {}, "Owner"), h("th", {}, "Must hear"), h("th", { class: "gv-col-type" }, "Type"))),
    );
    const tbody = h("tbody");
    const rowInputs: { title: HTMLInputElement; minutes: HTMLInputElement; owner: HTMLInputElement; mustHear: HTMLInputElement; type: HTMLSelectElement }[] = [];
    for (const row of state.rows) {
      const t = h("input", { type: "text", "aria-label": "Topic" });
      t.value = row.title;
      const m = h("input", { type: "text", inputmode: "numeric", "aria-label": "Minutes" });
      m.value = row.minutes;
      const o = h("input", { type: "text", "aria-label": "Owner" });
      o.value = row.owner;
      const mh = h("input", { type: "text", "aria-label": "Must hear" });
      mh.value = row.mustHear;
      const ty = h("select", { "aria-label": "Type" });
      for (const kind of ["discussion", "presentation"] as const) {
        const opt = h("option", { value: kind }, kind);
        if (kind === row.type) opt.selected = true;
        ty.append(opt);
      }
      rowInputs.push({ title: t, minutes: m, owner: o, mustHear: mh, type: ty });
      tbody.append(h("tr", {}, h("td", {}, t), h("td", {}, m), h("td", {}, o), h("td", {}, mh), h("td", {}, ty)));
    }
    table.append(tbody);

    const readState = (): ConfirmState => ({
      title: cleanLine(title.value, 300),
      purpose: cleanLine(purpose.value, 1000),
      start: state.start,
      durationMinutes: cleanMinutes(minutes.value) ?? state.durationMinutes,
      attendees: state.attendees,
      enforcement: (enforcement.value as Enforcement) ?? DEFAULT_ENFORCEMENT,
      rows: rowInputs.map<TopicRow>((r) => ({
        title: cleanLine(r.title.value, 300),
        minutes: cleanLine(r.minutes.value, 8),
        owner: cleanLine(r.owner.value, 120),
        mustHear: cleanLine(r.mustHear.value, 400),
        type: r.type.value === "presentation" ? "presentation" : "discussion",
      })),
    });

    body.append(
      h("div", { class: "gv-field" }, h("label", {}, "Title"), title),
      h("div", { class: "gv-field" }, h("label", {}, "Purpose"), purpose),
      h("div", { class: "gv-field" }, h("label", {}, "Duration (minutes)"), minutes),
      h("p", { class: "gv-people" }, `Attendees: ${state.attendees.map((p) => `${p.name} <${p.email}>`).join(", ")}`),
      table,
    );
    const addRow = h("button", { class: "gv-btn", type: "button" }, "+ topic");
    addRow.addEventListener("click", () => {
      const next = readState();
      this.set({ name: "confirm", brief: this.currentBrief(), draft: null, state: { ...next, rows: withSpareRow(next.rows) } });
    });
    body.append(h("div", { class: "gv-field" }, h("label", {}, "How firmly the chair enforces this"), enforcement));
    const back = h("button", { class: "gv-btn", type: "button" }, "Back");
    back.addEventListener("click", () => this.set({ name: "brief", brief: this.currentBrief(), typed: "" }));
    const go = h("button", { class: "gv-btn gv-primary", type: "button" }, "Chair this meeting");
    go.addEventListener("click", () => void this.register(readState()));
    body.append(h("div", { class: "gv-actions" }, addRow, back, go));
  }

  private renderDone(body: HTMLElement, s: Extract<State, { name: "done" }>): void {
    const { response, writes } = s;
    const wroteDescription = response.wrote.description || writes.description;
    const invitedBot = response.wrote.botInvited || writes.guest;
    const items: HTMLElement[] = [h("li", {}, `Agenda registered (session ${response.result.sessionId}).`)];
    items.push(
      h("li", {}, wroteDescription ? (response.wrote.description ? "Agenda written into the invite." : "Agenda placed in the description \u2014 press Save.") : "Could not reach the description field."),
    );
    items.push(h("li", {}, invitedBot ? `${response.botEmail} added as a guest${response.wrote.botInvited ? "." : " \u2014 press Save."}` : `Add ${response.botEmail} as a guest.`));
    body.append(h("div", { class: wroteDescription && invitedBot ? "gv-ok" : "gv-error" }, h("strong", {}, "Done."), h("ul", {}, ...items)));

    if (!wroteDescription) {
      const copy = h("textarea", { class: "gv-copy", readonly: true, "aria-label": "Agenda text" });
      copy.value = response.description;
      body.append(h("p", { class: "gv-muted" }, "Paste this into the event description:"), copy);
    }
    const join = cleanHttpUrl(response.result.joinUrl, __DEV_BUILD__);
    if (join) {
      const a = h("a", { href: join, target: "_blank", rel: "noopener noreferrer" }, "Open the chair's join link");
      body.append(h("p", {}, a));
    }
    const closeBtn = h("button", { class: "gv-btn gv-primary", type: "button" }, "Close");
    closeBtn.addEventListener("click", () => this.close());
    body.append(h("div", { class: "gv-actions" }, closeBtn));
  }
}

/** The one box, pre-filled from the event: its title as the first line, then
 *  whatever the host already wrote in the description (minus any agenda block a
 *  previous run of ours put there). */
export function initialBrief(ctx: EventContext): string {
  const parts: string[] = [];
  if (ctx.title) parts.push(ctx.title);
  const own = briefFrom(ctx.description);
  if (own) parts.push(own);
  return parts.join("\n\n");
}

function describe(r: Extract<Response, { ok: false }>): string {
  switch (r.error) {
    case "not-signed-in":
      return `Sign in to gavel first. ${r.detail}`;
    case "auth-cancelled":
      return "Sign-in was cancelled.";
    case "server-unreachable":
      return `Could not reach the gavel server. ${r.detail}`;
    case "server-refused":
      return `The server refused: ${r.detail}`;
    case "calendar-write-failed":
      return `The agenda was registered, but writing it into the event failed: ${r.detail}`;
    case "bad-request":
      return r.detail;
  }
}
