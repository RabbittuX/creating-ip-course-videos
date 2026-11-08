(function () {
  "use strict";

  const rect = (node) => node.getBoundingClientRect();
  const visible = (node) => {
    const style = getComputedStyle(node);
    const box = rect(node);
    return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0 && box.width > 0 && box.height > 0;
  };
  const rgb = (value) => {
    const parts = String(value).match(/[\d.]+/g) || [];
    return parts.slice(0, 3).map(Number);
  };
  const hex = (value) => {
    const c = rgb(value);
    return c.length === 3 ? `#${c.map((n) => Math.round(n).toString(16).padStart(2, "0")).join("")}` : String(value).toLowerCase();
  };
  const isWhite = (value) => {
    const c = rgb(value);
    return c.length === 3 && c.every((n) => n >= 248);
  };

  window.__inspectBrollFrame = function inspectBrollFrame(options = {}) {
    const root = options.root || document.querySelector("[data-composition-id]") || document.body;
    const canvas = rect(root);
    const safe = Number(options.safeMarginPx ?? 64);
    const tolerance = Number(options.focusAlignmentTolerancePx ?? 8);
    const textNodes = [...root.querySelectorAll("*")].filter((node) => visible(node) && [...node.childNodes].some((x) => x.nodeType === 3 && x.textContent.trim()));
    const textOverflow = textNodes.filter((node) => node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1);
    const inspected = [...root.querySelectorAll("[data-inspect-bounds], [data-focus-target]")].filter(visible);
    const outOfBounds = inspected.filter((node) => {
      const box = rect(node);
      return box.left < canvas.left + safe || box.top < canvas.top + safe || box.right > canvas.right - safe || box.bottom > canvas.bottom - safe;
    });
    const focusMisaligned = [...root.querySelectorAll("[data-focus-target]")].filter((focus) => {
      const target = root.querySelector(`#${CSS.escape(focus.dataset.focusTarget)}`);
      if (!target || !visible(focus) || !visible(target)) return true;
      const a = rect(focus), b = rect(target);
      const localTolerance = Math.max(tolerance, Number(focus.dataset.focusTolerance || 0));
      const centerDelta = Math.max(
        Math.abs((a.left + a.right) / 2 - (b.left + b.right) / 2),
        Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2),
      );
      const containsTarget = a.left <= b.left + localTolerance && a.top <= b.top + localTolerance && a.right >= b.right - localTolerance && a.bottom >= b.bottom - localTolerance;
      return centerDelta > localTolerance || !containsTarget;
    });
    const activeContent = [...root.querySelectorAll("*")].filter((node) => visible(node)).length;
    const background = getComputedStyle(root).backgroundColor || getComputedStyle(document.body).backgroundColor;
    const stateColors = {};
    for (const role of ["active", "completed", "unvisited"]) {
      const node = root.querySelector(`[data-state-role="${role}"]`);
      if (node && visible(node)) stateColors[role] = hex(getComputedStyle(node).borderColor || getComputedStyle(node).color);
    }
    const palette = {active: "#e9a51a", completed: "#55d4b4", unvisited: "#71818e", ...(options.stateColors || {})};
    for (const node of root.querySelectorAll("[data-state-item]")) {
      if (!visible(node)) continue;
      const style = getComputedStyle(node);
      const colors = [hex(style.borderColor), hex(style.color), hex(style.backgroundColor)];
      for (const [role, expected] of Object.entries(palette)) {
        if (colors.includes(String(expected).toLowerCase())) stateColors[role] = String(expected).toLowerCase();
      }
    }
    return {
      time: Number(options.time || 0),
      textOverflowCount: textOverflow.length,
      outOfBoundsCount: outOfBounds.length,
      focusMisalignedCount: focusMisaligned.length,
      whiteFrame: isWhite(background) && activeContent < 4,
      focusVisible: [...root.querySelectorAll("[data-focus-target]")].some(visible),
      stateColors,
      diagnostics: {
        textOverflow: textOverflow.map((x) => x.id || x.className || x.tagName),
        outOfBounds: outOfBounds.map((x) => x.id || x.className || x.tagName),
        focusMisaligned: focusMisaligned.map((x) => x.id || x.className || x.tagName),
      },
    };
  };
})();
