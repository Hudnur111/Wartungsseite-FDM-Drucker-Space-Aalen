document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    if (target.hasAttribute("tabindex")) target.focus({ preventScroll: true });
  });
});

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const revealItems = document.querySelectorAll(".reveal");
if (prefersReducedMotion || !("IntersectionObserver" in window)) {
  revealItems.forEach((item) => item.classList.add("visible"));
} else {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("visible");
        revealObserver.unobserve(entry.target);
      });
    },
    { threshold: 0.16 },
  );
  revealItems.forEach((item) => revealObserver.observe(item));
}

function animateCount(node) {
  const target = Number(node.dataset.count || node.textContent || 0);
  if (!Number.isFinite(target) || prefersReducedMotion) {
    node.textContent = target;
    return;
  }
  const start = performance.now();
  const duration = 720;
  const tick = (now) => {
    const progress = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    node.textContent = Math.round(target * eased);
    if (progress < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

document.querySelectorAll("[data-count]").forEach(animateCount);

const sections = [...document.querySelectorAll("main section[id]")];
const navLinks = [...document.querySelectorAll(".site-header nav a")];
if ("IntersectionObserver" in window) {
  const navObserver = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
      if (!visible) return;
      navLinks.forEach((link) => {
        const active = link.getAttribute("href") === `#${visible.target.id}`;
        link.classList.toggle("active", active);
        if (active) {
          link.setAttribute("aria-current", "page");
        } else {
          link.removeAttribute("aria-current");
        }
      });
    },
    { rootMargin: "-30% 0px -55% 0px", threshold: [0.1, 0.4, 0.7] },
  );
  sections.forEach((section) => navObserver.observe(section));
}

const previewStates = [
  {
    device: "PRUSA XL 5-Tool",
    role: "Administrator",
    metrics: [7, 2, 18],
    tasks: [
      ["XL Linear-Rails", "200-300 h", "offen", ""],
      ["Tool 1 Nozzle", "b.B.", "bei Bedarf", "neutral"],
      ["Firmware prüfen", "monatlich", "bald", ""],
    ],
  },
  {
    device: "PRUSA MINI+ Alpha",
    role: "Mentor",
    metrics: [1, 3, 22],
    tasks: [
      ["Druckplatte reinigen", "15 Tage", "bald", ""],
      ["First-Layer prüfen", "b.B.", "bei Bedarf", "neutral"],
      ["Extruder reinigen", "250 h", "ok", "positive"],
    ],
  },
  {
    device: "PRUSA MK3.5",
    role: "Benutzer",
    metrics: [0, 1, 24],
    tasks: [
      ["Druckbett prüfen", "vor Druck", "ok", "positive"],
      ["Nozzle reinigen", "15 Tage", "bald", ""],
      ["Riemenspannung prüfen", "250 h", "ok", "positive"],
    ],
  },
];

function setPreviewState(state) {
  const device = document.querySelector("#previewDevice");
  const role = document.querySelector("#previewRole");
  const due = document.querySelector("#previewDue");
  const soon = document.querySelector("#previewSoon");
  const ok = document.querySelector("#previewOk");
  const rows = document.querySelectorAll("[data-preview-row]");
  if (!device || !role || !due || !soon || !ok || rows.length < 3) return;

  device.textContent = state.device;
  role.textContent = state.role;
  [due, soon, ok].forEach((node, index) => {
    node.textContent = state.metrics[index];
  });
  rows.forEach((row, index) => {
    const [title, interval, status, tone] = state.tasks[index];
    row.classList.add("is-updating");
    row.querySelector("strong").textContent = title;
    row.querySelector("span").textContent = interval;
    const badge = row.querySelector("b");
    badge.textContent = status;
    badge.className = tone;
    window.setTimeout(() => row.classList.remove("is-updating"), 360);
  });
}

if (!prefersReducedMotion) {
  let previewIndex = 0;
  window.setInterval(() => {
    previewIndex = (previewIndex + 1) % previewStates.length;
    setPreviewState(previewStates[previewIndex]);
  }, 3600);
}
