(function (global) {
  "use strict";

  const COLORS = {
    active: {border: "#e9a51a", background: "#3d4147", text: "#e9a51a"},
    completed: {border: "#55d4b4", background: "#344b48", text: "#55d4b4"},
    unvisited: {border: "#71818e", background: "#373d44", text: "#71818e"},
  };

  function stateAt(timeline, timeMs) {
    return timeline.map((item) => ({
      ...item,
      state: timeMs < item.activeAtMs ? "unvisited" : timeMs < item.completeAtMs ? "active" : "completed",
    }));
  }

  function layoutFor(rootBox, targetBox, pointerBox) {
    return {
      focus: {
        left: targetBox.left - rootBox.left,
        top: targetBox.top - rootBox.top,
        width: targetBox.width,
        height: targetBox.height,
      },
      pointer: {
        left: targetBox.right - rootBox.left - pointerBox.width - 16,
        top: targetBox.bottom - rootBox.top - pointerBox.height - 16,
      },
    };
  }

  function apply(root, timeline, timeMs) {
    const states = stateAt(timeline, timeMs);
    const nodes = [...root.querySelectorAll("[data-state-item]")];
    let activeNode = null;
    states.forEach((item, index) => {
      const node = root.querySelector(`[data-item-id="${item.itemId}"]`) || root.querySelector(`#${item.targetId || item.itemId}`) || nodes[index];
      if (!node) return;
      node.dataset.stateRole = item.state;
      node.style.borderColor = COLORS[item.state].border;
      node.style.backgroundColor = COLORS[item.state].background;
      node.style.color = COLORS[item.state].text;
      if (item.state === "active") activeNode = node;
    });
    const focus = root.querySelector("[data-broll-focus], .hf-focus");
    const pointer = root.querySelector("[data-broll-pointer], .marker");
    for (const node of [focus, pointer]) {
      if (!node) continue;
      node.style.opacity = activeNode ? "1" : "0";
      if (activeNode) node.dataset.focusTarget = activeNode.id || activeNode.dataset.itemId || "";
    }
    if (activeNode) {
      const rootBox = root.getBoundingClientRect();
      const targetBox = activeNode.getBoundingClientRect();
      const pointerBox = pointer ? pointer.getBoundingClientRect() : {width: 0, height: 0};
      const layout = layoutFor(rootBox, targetBox, pointerBox);
      if (focus) Object.assign(focus.style, {
        left: `${layout.focus.left}px`, top: `${layout.focus.top}px`,
        width: `${layout.focus.width}px`, height: `${layout.focus.height}px`, transform: "none",
      });
      if (pointer) Object.assign(pointer.style, {
        left: `${layout.pointer.left}px`, top: `${layout.pointer.top}px`, transform: "none",
      });
    }
    return states;
  }

  function mount(root, timeline) {
    const handle = {update: (timeMs) => apply(root, timeline, timeMs)};
    root.__brollProgress = handle;
    return handle;
  }

  function bindGsap(root, timeline, gsapTimeline, options) {
    if (!root || !gsapTimeline || typeof gsapTimeline.eventCallback !== "function") {
      throw new Error("B-roll progress runtime requires a root and a seekable GSAP timeline");
    }
    const originMs = Number(options && options.originMs) || 0;
    const handle = mount(root, timeline);
    const previous = gsapTimeline.eventCallback("onUpdate");
    const update = function () {
      if (typeof previous === "function") previous.call(gsapTimeline);
      handle.update(originMs + Number(gsapTimeline.time()) * 1000);
    };
    gsapTimeline.eventCallback("onUpdate", update);
    update();
    root.dataset.brollProgressRuntime = "bound";
    return handle;
  }

  global.BrollProgressController = {COLORS, stateAt, layoutFor, apply, mount, bindGsap};
})(typeof globalThis !== "undefined" ? globalThis : window);
