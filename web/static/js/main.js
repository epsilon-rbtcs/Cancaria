/* ------------------------------------------------------------------
   Cancaria — shared interface behaviour
   ------------------------------------------------------------------ */

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

/* Navigation ----------------------------------------------------- */

const nav = document.querySelector("[data-nav]");
const navToggle = document.querySelector("[data-nav-toggle]");
const mobileMenu = document.querySelector("[data-mobile-menu]");

function navIsScrolled() {
  if (!nav) return;
  nav.classList.toggle("is-scrolled", window.scrollY > 12);
}

if (nav) {
  let ticking = false;
  navIsScrolled();
  window.addEventListener(
    "scroll",
    () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(() => {
        navIsScrolled();
        ticking = false;
      });
    },
    { passive: true }
  );
}

if (navToggle && mobileMenu) {
  const toggleLabel = navToggle.querySelector(".visually-hidden");
  let lastFocused = null;

  const focusable = () =>
    Array.from(
      mobileMenu.querySelectorAll(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ).filter((node) => node.offsetParent !== null);

  const openMenu = () => {
    lastFocused = document.activeElement;
    mobileMenu.hidden = false;
    document.body.classList.add("menu-open");
    navToggle.setAttribute("aria-expanded", "true");
    if (toggleLabel) toggleLabel.textContent = "Close menu";
    const first = focusable()[0];
    if (first) first.focus();
  };

  const closeMenu = ({ restoreFocus = true } = {}) => {
    if (mobileMenu.hidden) return;
    mobileMenu.hidden = true;
    document.body.classList.remove("menu-open");
    navToggle.setAttribute("aria-expanded", "false");
    if (toggleLabel) toggleLabel.textContent = "Open menu";
    if (restoreFocus && lastFocused) lastFocused.focus();
  };

  navToggle.addEventListener("click", () => {
    if (mobileMenu.hidden) openMenu();
    else closeMenu();
  });

  mobileMenu.addEventListener("click", (event) => {
    if (event.target.closest("a")) closeMenu({ restoreFocus: false });
  });

  document.addEventListener("keydown", (event) => {
    if (mobileMenu.hidden) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeMenu();
      return;
    }
    if (event.key !== "Tab") return;
    const items = focusable();
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 980) closeMenu({ restoreFocus: false });
  });
}

/* Service status ------------------------------------------------ */

const healthTargets = document.querySelectorAll("[data-health]");

function setHealth({ online, label }) {
  healthTargets.forEach((chip) => {
    chip.classList.toggle("is-offline", !online);
    const text = chip.querySelector("[data-health-text]");
    if (text) text.textContent = label;
  });
}

async function checkHealth() {
  if (!healthTargets.length) return;
  try {
    const response = await fetch("/api/health", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) throw new Error("unavailable");
    const data = await response.json();
    const device = String(data.device || "cpu").toUpperCase();
    setHealth({ online: true, label: `Inference online, ${device}` });
  } catch {
    setHealth({ online: false, label: "Inference offline" });
  }
}

checkHealth();

/* Footer wordmark lens ----------------------------------------- */

const footerMark = document.querySelector("[data-footer-mark]");

if (footerMark && !reduceMotion.matches) {
  let frame = 0;
  let pendingX = null;
  let pendingY = null;

  const paint = () => {
    frame = 0;
    if (pendingX === null || pendingY === null) return;
    footerMark.style.setProperty("--mx", `${pendingX}px`);
    footerMark.style.setProperty("--my", `${pendingY}px`);
  };

  footerMark.addEventListener("pointermove", (event) => {
    if (event.pointerType === "touch") return;
    const box = footerMark.getBoundingClientRect();
    pendingX = event.clientX - box.left;
    pendingY = event.clientY - box.top;
    if (!frame) frame = window.requestAnimationFrame(paint);
  });

  footerMark.addEventListener("pointerleave", () => {
    footerMark.style.removeProperty("--mx");
    footerMark.style.removeProperty("--my");
  });
}

/* Hero acquisition sweep --------------------------------------- */

const hero = document.querySelector(".hero");
const sweep = document.querySelector("[data-scan-sweep]");

if (hero && sweep) {
  window.requestAnimationFrame(() => hero.classList.add("is-ready"));
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        hero.classList.toggle("is-offscreen", !entries[0].isIntersecting);
      },
      { threshold: 0.05 }
    );
    observer.observe(hero);
  }
}

/* Workflow tabs ------------------------------------------------- */

document.querySelectorAll("[data-tabs]").forEach((root) => {
  const tabs = Array.from(root.querySelectorAll('[role="tab"]'));
  const panels = tabs.map((tab) =>
    document.getElementById(tab.getAttribute("aria-controls"))
  );

  if (!tabs.length || panels.some((panel) => !panel)) return;

  const select = (index, { focus = false } = {}) => {
    tabs.forEach((tab, i) => {
      const active = i === index;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      panels[i].hidden = !active;
    });
    if (focus) tabs[index].focus();
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => select(index));
    tab.addEventListener("keydown", (event) => {
      const keys = ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft", "Home", "End"];
      if (!keys.includes(event.key)) return;
      event.preventDefault();
      let next = index;
      if (event.key === "ArrowDown" || event.key === "ArrowRight") {
        next = (index + 1) % tabs.length;
      } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
        next = (index - 1 + tabs.length) % tabs.length;
      } else if (event.key === "Home") {
        next = 0;
      } else if (event.key === "End") {
        next = tabs.length - 1;
      }
      select(next, { focus: true });
    });
  });
});

