const FONT_MODE_KEY = "kabot-docs-font-mode";
const FONT_MODES = {
  clean: "Font: Clean",
  cyber: "Font: Cyber",
};

function getStickyOffset() {
  const header = document.querySelector(".md-header");
  const headerHeight = header ? header.getBoundingClientRect().height : 0;
  return headerHeight + 16;
}

function syncStickySidebarState() {
  const stickyOffset = getStickyOffset();
  document
    .querySelectorAll(".md-sidebar--primary, .md-sidebar--secondary")
    .forEach((sidebar) => {
      const top = sidebar.getBoundingClientRect().top;
      sidebar.classList.toggle("kabot-is-stuck", top <= stickyOffset + 1);
    });
}

function getStoredFontMode() {
  const stored = window.localStorage.getItem(FONT_MODE_KEY);
  return stored === "cyber" ? "cyber" : "clean";
}

function applyFontMode(mode) {
  const root = document.documentElement;
  root.classList.add("kabot-cyberpunk");
  root.classList.remove("kabot-font-clean", "kabot-font-cyber");
  root.classList.add(mode === "cyber" ? "kabot-font-cyber" : "kabot-font-clean");
  root.dataset.kabotFontMode = mode;
  window.localStorage.setItem(FONT_MODE_KEY, mode);
}

function updateFontToggleLabel(button, mode) {
  button.textContent = FONT_MODES[mode];
  button.setAttribute("aria-label", FONT_MODES[mode]);
  button.setAttribute("title", FONT_MODES[mode]);
}

function ensureFontToggle() {
  const header = document.querySelector(".md-header__inner");
  if (!header) {
    return;
  }

  let button = document.querySelector(".kabot-font-toggle");
  if (!button) {
    button = document.createElement("button");
    button.type = "button";
    button.className = "kabot-font-toggle";
    button.addEventListener("click", () => {
      const nextMode = document.documentElement.dataset.kabotFontMode === "cyber" ? "clean" : "cyber";
      applyFontMode(nextMode);
      updateFontToggleLabel(button, nextMode);
    });
    header.appendChild(button);
  } else if (button.parentElement !== header) {
    header.appendChild(button);
  }

  updateFontToggleLabel(button, getStoredFontMode());
}

function initKabotDocsTheme() {
  const mode = getStoredFontMode();
  applyFontMode(mode);
  ensureFontToggle();
  syncStickySidebarState();
}

if (window.document$ && typeof window.document$.subscribe === "function") {
  window.document$.subscribe(initKabotDocsTheme);
} else {
  document.addEventListener("DOMContentLoaded", initKabotDocsTheme);
}

window.addEventListener("scroll", syncStickySidebarState, { passive: true });
window.addEventListener("resize", syncStickySidebarState, { passive: true });
