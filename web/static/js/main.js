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
    mountAvailableVideo(data);
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

/* Demonstration video ------------------------------------------ */

const videoStage = document.querySelector("[data-video-stage]");

function playIcon() {
  return '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13l10-6.5z"/></svg>';
}

function pauseIcon() {
  return '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>';
}

function mountVideo(stage, src, captionsSrc, hasCaptions) {
  const poster = stage.querySelector(".demo-poster");
  const overlay = stage.querySelector("[data-video-overlay]");
  const status = document.querySelector("[data-video-status]");

  const video = document.createElement("video");
  video.controls = true;
  video.preload = "metadata";
  video.playsInline = true;
  video.src = src;
  if (poster) video.poster = poster.currentSrc || poster.src;

  if (hasCaptions && captionsSrc) {
    const track = document.createElement("track");
    track.kind = "captions";
    track.label = "English";
    track.srclang = "en";
    track.src = captionsSrc;
    video.appendChild(track);
  }

  stage.classList.add("has-video");
  if (poster) poster.hidden = true;
  stage.prepend(video);

  const badge = overlay ? overlay.querySelector(".demo-badge") : null;
  const badgePending = badge ? badge.innerHTML : "";
  if (badge) {
    badge.innerHTML = '<span class="status-dot" aria-hidden="true"></span> Demonstration';
  }

  const play = document.createElement("button");
  play.type = "button";
  play.className = "demo-play";
  play.setAttribute("aria-label", "Play demonstration video");
  play.innerHTML = playIcon();
  stage.appendChild(play);

  const sync = () => {
    stage.classList.toggle("is-playing", !video.paused && !video.ended);
    play.innerHTML = video.paused || video.ended ? playIcon() : pauseIcon();
    play.setAttribute(
      "aria-label",
      video.paused || video.ended ? "Play demonstration video" : "Pause demonstration video"
    );
  };

  play.addEventListener("click", () => {
    if (video.paused || video.ended) {
      const attempt = video.play();
      if (attempt && typeof attempt.catch === "function") attempt.catch(() => {});
    } else {
      video.pause();
    }
  });

  video.addEventListener("play", sync);
  video.addEventListener("pause", sync);
  video.addEventListener("ended", sync);
  video.addEventListener("error", () => {
    stage.classList.remove("has-video", "is-playing");
    video.remove();
    play.remove();
    if (poster) poster.hidden = false;
    if (badge && badgePending) badge.innerHTML = badgePending;
    if (status) status.textContent = "No recording in this build";
  });

  if (status) status.textContent = "Recording available";

  if (reduceMotion.matches) video.autoplay = false;
}

let videoMounted = false;

function mountAvailableVideo(health) {
  if (!videoStage || videoMounted || !health || !health.demo_video) return;
  const src = videoStage.dataset.videoSrc;
  if (!src) return;
  videoMounted = true;
  mountVideo(
    videoStage,
    src,
    videoStage.dataset.captionsSrc,
    Boolean(health.demo_captions)
  );
}
