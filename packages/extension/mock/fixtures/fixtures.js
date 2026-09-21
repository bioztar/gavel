// Behaviour for the fixture pages: guest chips that accept Enter the way
// Google's do, a description box, dates, and prefilling from the mock event
// when the URL names one. This is fixture code, not extension code.

(function () {
  const $ = (s, r) => (r || document).querySelector(s);

  function fmtDate(d) {
    return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  }
  function fmtTime(d) {
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toLowerCase().replace(" ", "");
  }

  function addChip(email, name, organizer) {
    const chips = $("#chips");
    if (!chips || chips.querySelector(`[data-email="${email}"]`)) return;
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.dataset.email = email;
    if (name) chip.dataset.name = name;
    chip.setAttribute("aria-label", `${name || email}${organizer ? ", organizer" : ""}`);
    const av = document.createElement("span");
    av.className = "av";
    av.textContent = (name || email)[0].toUpperCase();
    const label = document.createElement("span");
    label.textContent = name || email;
    if (organizer) {
      const tag = document.createElement("small");
      tag.textContent = "Organizer";
      label.append(" ", tag);
    }
    chip.append(av, label);
    chips.append(chip);
  }

  function setupCalendar() {
    const input = $(".guest-input");
    input.addEventListener("keydown", (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      const v = input.value.trim();
      if (/^[^\s@]+@[^\s@]+$/.test(v)) addChip(v.toLowerCase(), "", false);
      input.value = "";
    });

    const today = new Date();
    for (const sel of ['[aria-label="Start date"]', '[aria-label="End date"]']) $(sel).value = fmtDate(today);

    // The host is always a guest of their own event.
    addChip("host@example.com", "Vitaly", true);

    const m = location.pathname.match(/\/eventedit\/([^/?#]+)/);
    if (!m) return;
    fetch("/fixtures/event.json")
      .then((r) => r.json())
      .then(({ event }) => {
        $('[aria-label="Add title"]').value = event.summary;
        $('[aria-label="Description"]').textContent = event.description;
        const s = new Date(event.start.dateTime);
        const e = new Date(event.end.dateTime);
        $('[aria-label="Start date"]').value = fmtDate(s);
        $('[aria-label="End date"]').value = fmtDate(e);
        $('[aria-label="Start time"]').value = fmtTime(s);
        $('[aria-label="End time"]').value = fmtTime(e);
        for (const a of event.attendees) addChip(a.email, a.displayName || "", !!a.organizer);
      });
  }

  function setupMeet() {
    const clock = $("#clock");
    const tick = () => (clock.textContent = new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }));
    tick();
    setInterval(tick, 30_000);
    const code = location.pathname.split("/").find((s) => /^[a-z]{3}-[a-z]{4}-[a-z]{3}$/.test(s));
    if (!code) return;
    fetch("/fixtures/event.json")
      .then((r) => r.json())
      .then(({ meetCode, event }) => {
        if (meetCode === code) {
          const h1 = $("#meeting-title");
          h1.textContent = event.summary;
          h1.setAttribute("data-meeting-title", event.summary);
        }
      });
    $(".join-now").addEventListener("click", () => alert("Fixture: this is where Meet would join the call."));
  }

  function setupIndex() {
    fetch("/fixtures/event.json")
      .then((r) => r.json())
      .then(({ editUrl, meetCode }) => {
        $("#existing").href = editUrl;
        $("#meet").href = `/fixtures/meet/${meetCode}`;
      });
  }

  if (document.body.classList.contains("calendar")) setupCalendar();
  else if (document.body.classList.contains("meet")) setupMeet();
  else if (document.body.classList.contains("index")) setupIndex();
})();
