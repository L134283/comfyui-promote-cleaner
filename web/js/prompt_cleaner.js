/**
 * Comfyui-Promote-Cleaner 前端扩展
 *
 * 做两件事：
 *
 * 1. **文本输入口的自由增减**：把「清洁选项」里那些开关从节点上收走之后，
 *    节点只留下文本输入相关的东西 —— 一个常驻口 ``text_in``、
 *    若干可增减的额外口（后端用 ``io.Autogrow`` 声明，名字形如
 *    ``extra_texts.text_in_2``），以及一个可以直接打字的文本框。
 *    连上最后一个额外口时 ComfyUI 会自动再补一个；也可以点「＋ 文本输入口」
 *    按钮手动加一个，或在设置窗口里逐个删掉。
 *
 * 2. **把开关收进一个大按钮 + 弹窗**：``bracket_policy`` / ``keep_weights`` /
 *    ``blacklist`` 等 9 个控件依然存在于 widget 列表里（所以工作流 JSON、
 *    序列化、后端取值全都不变），只是「不画出来」，统一在「清洁设置」弹窗里编辑。
 *
 * 注意：这里**不新增任何后端参数**，只是给已有的 widget 换了个 UI。
 */

import { app } from "../../../scripts/app.js";

/** 本扩展负责的节点。 */
const NODE_TYPES = new Set(["PromoteCleaner_Text", "PromoteCleaner_ClipEncode"]);

/** 额外文本插槽在前端 / 后端的统一前缀（后端 Autogrow 展开成 ``extra_texts.<name>``）。 */
const SLOT_PREFIX = "extra_texts.";

/** 兜底插槽名：正常情况下从节点定义里读，读不到时用这份（需与 nodes.py 保持一致）。 */
const FALLBACK_SLOT_NAMES = [
  "text_in_2", "text_in_3", "text_in_4", "text_in_5", "text_in_6",
  "text_in_7", "text_in_8", "text_in_9", "text_in_10",
];

/** 需要收进弹窗的控件（按节点上的原有顺序）。 */
const OPTION_WIDGETS = [
  "bracket_policy",
  "keep_weights",
  "underscore_to_space",
  "dedupe",
  "strip_blacklist",
  "lowercase",
  "separator",
  "normalize_fullwidth",
  "blacklist",
];

/** 开关型控件。 */
const BOOLEAN_OPTIONS = [
  {
    id: "keep_weights",
    zh: "保留权重语法", en: "Keep weight syntax",
    zhHint: "（tag:1.2）这类显式权重原样保留，只转义真正的字面括号",
    enHint: "Keep explicit weights like (tag:1.2); only literal brackets get escaped",
  },
  {
    id: "underscore_to_space",
    zh: "下划线转空格", en: "Underscore to space",
    zhHint: "drawing_bow → drawing bow",
    enHint: "drawing_bow -> drawing bow",
  },
  {
    id: "dedupe",
    zh: "去重", en: "Dedupe",
    zhHint: "重复标签只保留第一次出现（跨输入来源也算）",
    enHint: "Keep only the first occurrence of each tag, across every input",
  },
  {
    id: "strip_blacklist",
    zh: "黑名单过滤", en: "Blacklist filter",
    zhHint: "按下方黑名单剔除 tagme / watermark / signature 等脏标签",
    enHint: "Drop dirty tags (tagme / watermark / signature ...) using the blacklist below",
  },
  {
    id: "lowercase",
    zh: "转小写", en: "Lowercase",
    zhHint: "输出标签统一转小写",
    enHint: "Lowercase every output tag",
  },
  {
    id: "normalize_fullwidth",
    zh: "全角转半角", en: "Fullwidth to halfwidth",
    zhHint: "（） → ( ) 、 ＿ → _",
    enHint: "（） -> () , ＿ -> _",
  },
];

/** 下拉型控件。 */
const COMBO_OPTIONS = [
  {
    id: "bracket_policy",
    zh: "括号转义策略", en: "Bracket policy",
    zhHint: "ComfyUI 里只有 \\( \\) 是真正生效的转义，一般保持默认即可",
    enHint: "Only \\( \\) is a real escape in ComfyUI; the default is usually right",
  },
  {
    id: "separator",
    zh: "标签分隔符", en: "Separator",
    zhHint: "默认「逗号 + 空格」，也是 Anima 的推荐格式",
    enHint: "Comma + space is the default and the recommended Anima format",
  },
];

/** 界面文案。 */
const STRINGS = {
  zh: {
    addSlot: "＋ 文本输入口",
    addSlotTip: "再加一个文本连线口，所有连上的内容会自动拼接并一起清洁",
    settings: "⚙ 清洁设置",
    settingsTip: "打开设置窗口：开关、黑名单、文本输入口",
    dialogTitle: "提示词清洁 · 设置",
    sectionPorts: "文本输入口",
    portsHint: "连上的口按「文本输入 → 更多文本输入 → 提示词文本」的顺序拼接，然后一起清洁。",
    portConnected: "已连接",
    portFree: "空闲",
    portRemove: "移除",
    portRemoveTip: "移除这个输入口（已连接的请先断开连线）",
    portAdd: "＋ 添加",
    portMax: "已经是插槽上限，无法再添加",
    portHasLink: "这个输入口上还有连线，请先断开",
    sectionOptions: "清洁选项",
    sectionBlacklist: "黑名单",
    blacklistHint: "每行一条：# 开头为注释；普通文本 = 整标签匹配；re: 开头 = 正则包含匹配。清空即关闭黑名单过滤。",
    reset: "恢复默认",
    cancel: "取消",
    save: "保存",
    close: "关闭",
    slotLabel: "插槽",
    sepComma: "逗号 + 空格",
    sepCommaOnly: "仅逗号",
    policyParens: "圆括号",
    policyAll: "全部",
    policyNone: "不转义",
  },
  en: {
    addSlot: "＋ Text input",
    addSlotTip: "Add one more text socket; everything connected is merged and cleaned together",
    settings: "⚙ Clean settings",
    settingsTip: "Open the settings window: toggles, blacklist, text inputs",
    dialogTitle: "Prompt Cleaner · Settings",
    sectionPorts: "Text inputs",
    portsHint: "Connected sockets are concatenated in order (text in -> extra inputs -> prompt text box) and cleaned as one prompt.",
    portConnected: "connected",
    portFree: "free",
    portRemove: "Remove",
    portRemoveTip: "Remove this input socket (disconnect it first)",
    portAdd: "＋ Add",
    portMax: "No more sockets available",
    portHasLink: "This socket still has a link; disconnect it first",
    sectionOptions: "Clean options",
    sectionBlacklist: "Blacklist",
    blacklistHint: "One rule per line: # starts a comment; plain text = whole-tag match; re: = regex contains-match. Clear the box to disable filtering.",
    reset: "Reset",
    cancel: "Cancel",
    save: "Save",
    close: "Close",
    slotLabel: "slot",
    sepComma: "comma + space",
    sepCommaOnly: "comma only",
    policyParens: "parens",
    policyAll: "all",
    policyNone: "none",
  },
};

// ────────────────────────────── 小工具 ──────────────────────────────

/** 链式挂载回调，保留原有实现（ComfyUI 扩展的常规写法）。 */
function chainCallback(object, property, callback) {
  if (!object) return;
  const original = object[property];
  object[property] = function (...args) {
    const result = original?.apply(this, args);
    callback.apply(this, args);
    return result;
  };
}

/** 当前界面语言是不是中文。 */
function isChinese() {
  let locale = "";
  try {
    locale =
      app?.extensionManager?.setting?.get?.("Comfy.Locale") ||
      app?.ui?.settings?.getSettingValue?.("Comfy.Locale") ||
      "";
  } catch {
    locale = "";
  }
  if (!locale) locale = navigator.language || "";
  return /^zh/i.test(locale);
}

function strings() {
  return isChinese() ? STRINGS.zh : STRINGS.en;
}

function findWidget(node, name) {
  return node?.widgets?.find((widget) => widget?.name === name);
}

function toast(severity, summary, detail) {
  try {
    app?.extensionManager?.toast?.add({ severity, summary, detail, life: 3000 });
  } catch {
    console.warn(`[PromptCleaner] ${summary}: ${detail ?? ""}`);
  }
}

/** 从节点定义里读出 Autogrow 声明的插槽名。 */
function readSlotNames(nodeData) {
  const entry =
    nodeData?.input?.optional?.extra_texts ?? nodeData?.input?.required?.extra_texts;
  // object_info 里是 ["COMFY_AUTOGROW_V3", {...}]，前端内部也可能把它规范成对象
  const spec = Array.isArray(entry) ? entry[1] : entry;
  const names = spec?.template?.names;
  return Array.isArray(names) && names.length ? [...names] : [...FALLBACK_SLOT_NAMES];
}

/** 隐藏控件但保留序列化（工作流 JSON 里照旧保存，后端也照旧取到值）。 */
function hideWidgetForGood(widget) {
  if (!widget) return;
  widget.hidden = true;
  widget.origComputeSize = widget.computeSize;
  widget.computeSize = () => [0, -4];
}

/** 写回控件值并触发它自己的回调，让 ComfyUI 知道图被改过。 */
function writeWidgetValue(node, widget, value) {
  if (!widget) return;
  const changed = widget.value !== value;
  widget.value = value;
  if (typeof widget.callback === "function") {
    try {
      widget.callback(value, app.canvas, node, [0, 0], null);
    } catch (err) {
      console.warn("[PromptCleaner] widget callback failed", err);
    }
  }
  if (changed) app.graph?.setDirtyCanvas(true, true);
}

/** 让节点尺寸跟上内容（加了口 / 加了控件之后）。 */
function refitNode(node) {
  const computeSize = node?.computeSize;
  if (typeof computeSize !== "function") return;
  const [, height] = computeSize.call(node);
  if (Number.isFinite(height) && height > (node.size?.[1] ?? 0)) {
    node.setSize?.([node.size[0], height]);
  }
  app.graph?.setDirtyCanvas(true, true);
}

// ───────────────────────── 文本输入口的增减 ─────────────────────────

/** 列出节点上现有的额外文本口。 */
function extraTextSlots(node) {
  const slots = [];
  (node?.inputs ?? []).forEach((input, index) => {
    if (!input?.name?.startsWith(SLOT_PREFIX)) return;
    slots.push({
      index,
      name: input.name,
      shortName: input.name.slice(SLOT_PREFIX.length),
      connected: input.link != null,
    });
  });
  return slots;
}

/** 在节点末尾追加一个额外文本口（名字必须与后端 Autogrow 声明一致）。 */
function appendTextSlot(node, shortName) {
  const name = SLOT_PREFIX + shortName;
  if ((node.inputs ?? []).some((input) => input?.name === name)) return false;
  node.addInput?.(name, "STRING", { localized_name: shortName });
  const slot = node.inputs?.[node.inputs.length - 1];
  if (slot && slot.name === name) slot.label = shortName;
  refitNode(node);
  return true;
}

/** 「＋ 文本输入口」：补下一个还没出现的插槽。 */
function addNextTextSlot(node, slotNames) {
  const t = strings();
  const existing = new Set((node.inputs ?? []).map((input) => input?.name));
  const next = slotNames.find((name) => !existing.has(SLOT_PREFIX + name));
  if (!next) {
    toast("warn", t.settings, t.portMax);
    return false;
  }
  return appendTextSlot(node, next);
}

/** 移除一个额外文本口（有连线时拒绝，避免静默剪断用户的图）。 */
function removeTextSlot(node, slot) {
  const t = strings();
  const input = node.inputs?.[slot.index];
  if (!input || input.name !== slot.name) return false;
  if (input.link != null) {
    toast("warn", t.settings, t.portHasLink);
    return false;
  }
  node.removeInput?.(slot.index);
  refitNode(node);
  return true;
}

// ───────────────────────── 节点上的按钮与摘要 ─────────────────────────

/** 摘要里用的短名。 */
function shortLabel(t, id, value) {
  if (id === "separator") {
    if (value === "仅逗号" || value === ",") return t.sepCommaOnly;
    return t.sepComma;
  }
  if (id === "bracket_policy") {
    if (typeof value === "string" && value.includes("全部")) return t.policyAll;
    if (typeof value === "string" && (value.includes("原样") || value.includes("不转义"))) {
      return t.policyNone;
    }
    return t.policyParens;
  }
  return String(value);
}

/** 把当前设置压成一行摘要（开关都收进弹窗了，节点上总得能看出个大概）。 */
function refreshSummary(node) {
  const element = node?._pcSummaryEl;
  if (!element) return;
  const zh = isChinese();
  const parts = [];
  for (const option of BOOLEAN_OPTIONS) {
    if (findWidget(node, option.id)?.value) parts.push(zh ? option.zh : option.en);
  }
  for (const option of COMBO_OPTIONS) {
    const widget = findWidget(node, option.id);
    if (widget) {
      const label = zh ? option.zh : option.en;
      parts.push(`${label}: ${shortLabel(strings(), option.id, widget.value)}`);
    }
  }
  element.textContent = parts.join(" · ");
  element.title = parts.join("\n");
  refitNode(node);
}

/** 给节点挂上「＋ 文本输入口」「⚙ 清洁设置」两个按钮与一行摘要。 */
function setupNode(node, slotNames) {
  const t = strings();

  // 记下默认值，供弹窗里的「恢复默认」使用
  node._pcDefaults = {};
  for (const name of OPTION_WIDGETS) {
    const widget = findWidget(node, name);
    if (widget) node._pcDefaults[name] = widget.value;
  }

  // 把原来的开关收走（widget 本身还留着，只是不画）
  for (const name of OPTION_WIDGETS) hideWidgetForGood(findWidget(node, name));

  const addSlotWidget = node.addWidget(
    "button",
    t.addSlot,
    null,
    () => addNextTextSlot(node, slotNames),
    { serialize: false },
  );
  if (addSlotWidget) addSlotWidget.tooltip = t.addSlotTip;

  const settingsWidget = node.addWidget(
    "button",
    t.settings,
    null,
    () => openSettingsDialog(node, slotNames),
    { serialize: false },
  );
  if (settingsWidget) settingsWidget.tooltip = t.settingsTip;

  try {
    const summary = document.createElement("div");
    summary.className = "pc-summary";
    node.addDOMWidget("pc_settings_summary", "promote_cleaner_summary", summary, {
      serialize: false,
      hideOnZoom: false,
    });
    node._pcSummaryEl = summary;
  } catch (err) {
    console.warn("[PromptCleaner] 摘要行创建失败，已跳过", err);
  }

  refreshSummary(node);
}

// ─────────────────────────────── 样式 ───────────────────────────────

function injectStyle() {
  if (document.getElementById("pc-style")) return;
  const style = document.createElement("style");
  style.id = "pc-style";
  style.textContent = `
.pc-summary { padding: 2px 6px 0; font-size: 11px; line-height: 1.45; opacity: .68;
  word-break: break-word; pointer-events: none; }
.pc-overlay { position: fixed; inset: 0; z-index: 10000; display: flex;
  align-items: center; justify-content: center; background: rgba(0,0,0,.55); }
.pc-panel { width: min(560px, 92vw); max-height: 88vh; display: flex; flex-direction: column;
  background: #2a2a2a; color: #e8e8e8; border: 1px solid #474747; border-radius: 10px;
  box-shadow: 0 16px 48px rgba(0,0,0,.55); overflow: hidden;
  font: 13px/1.5 system-ui, "Segoe UI", "Microsoft YaHei", sans-serif; }
.pc-head { display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  background: #333; border-bottom: 1px solid #474747; font-weight: 600; }
.pc-head .pc-close { margin-left: auto; border: none; background: transparent; color: #bbb;
  font-size: 18px; line-height: 1; cursor: pointer; padding: 0 4px; }
.pc-head .pc-close:hover { color: #fff; }
.pc-body { padding: 12px 14px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
.pc-sec { border: 1px solid #3d3d3d; border-radius: 8px; padding: 10px 12px; background: #262626; }
.pc-sec > h4 { margin: 0 0 8px; font-size: 12px; letter-spacing: .05em; color: #8fb7d8;
  text-transform: uppercase; }
.pc-hint { margin: 0 0 8px; color: #9a9a9a; font-size: 11px; }
.pc-row { display: flex; align-items: center; gap: 10px; padding: 5px 0; }
.pc-row + .pc-row { border-top: 1px solid #333; }
.pc-row > label { flex: 1 1 auto; cursor: pointer; }
.pc-row .pc-sub { display: block; color: #9a9a9a; font-size: 11px; }
.pc-row input[type=checkbox] { width: 16px; height: 16px; accent-color: #4a9eff; cursor: pointer; }
.pc-row select { flex: 0 0 auto; min-width: 170px; padding: 4px 6px; border-radius: 6px;
  background: #1e1e1e; color: #e8e8e8; border: 1px solid #4a4a4a; font: inherit; }
.pc-textarea { width: 100%; box-sizing: border-box; min-height: 170px; resize: vertical;
  background: #1e1e1e; color: #e8e8e8; border: 1px solid #4a4a4a; border-radius: 6px;
  padding: 8px; font: 12px/1.5 ui-monospace, Consolas, "Courier New", monospace; }
.pc-ports { display: flex; flex-direction: column; gap: 6px; }
.pc-port { display: flex; align-items: center; gap: 8px; background: #2f2f2f;
  border-radius: 6px; padding: 4px 8px; font-size: 12px; }
.pc-port .pc-dot { width: 8px; height: 8px; border-radius: 50%; background: #6a9fd8; }
.pc-port .pc-dot.on { background: #5fd07a; }
.pc-port .pc-state { color: #9a9a9a; }
.pc-port .pc-btn { margin-left: auto; }
.pc-foot { display: flex; gap: 8px; justify-content: flex-end; padding: 10px 14px;
  background: #333; border-top: 1px solid #474747; }
.pc-btn { padding: 5px 14px; border-radius: 6px; border: 1px solid #555; background: #3d3d3d;
  color: #e8e8e8; cursor: pointer; font: inherit; }
.pc-btn:hover { background: #484848; }
.pc-btn.primary { background: #3a6ea5; border-color: #4a86c8; }
.pc-btn.primary:hover { background: #467fb8; }
.pc-btn.ghost { background: transparent; }
`;
  document.head.appendChild(style);
}

// ────────────────────────────── 设置弹窗 ──────────────────────────────

/**
 * 打开「清洁设置」窗口。
 *
 * 弹窗只改**已有 widget 的值**：控制项实时写进 `state`，点「保存」才写回 widget，
 * 所以「取消」天然是安全的。文本输入口的增减属于图结构改动，点一下立刻生效。
 */
function openSettingsDialog(node, slotNames) {
  const t = strings();
  injectStyle();

  const state = {};
  for (const name of OPTION_WIDGETS) state[name] = findWidget(node, name)?.value;

  const overlay = document.createElement("div");
  overlay.className = "pc-overlay";
  overlay.tabIndex = -1;

  const panel = document.createElement("div");
  panel.className = "pc-panel";
  overlay.appendChild(panel);

  const head = document.createElement("div");
  head.className = "pc-head";
  const title = document.createElement("span");
  title.textContent = t.dialogTitle;
  const closeButton = document.createElement("button");
  closeButton.className = "pc-close";
  closeButton.textContent = "×";
  closeButton.title = t.close;
  head.append(title, closeButton);

  const body = document.createElement("div");
  body.className = "pc-body";

  const foot = document.createElement("div");
  foot.className = "pc-foot";
  const resetButton = document.createElement("button");
  resetButton.className = "pc-btn ghost";
  resetButton.textContent = t.reset;
  const cancelButton = document.createElement("button");
  cancelButton.className = "pc-btn";
  cancelButton.textContent = t.cancel;
  const saveButton = document.createElement("button");
  saveButton.className = "pc-btn primary";
  saveButton.textContent = t.save;
  foot.append(resetButton, cancelButton, saveButton);

  panel.append(head, body, foot);

  // ── 文本输入口 ──
  const portsSection = document.createElement("section");
  portsSection.className = "pc-sec";
  const portsTitle = document.createElement("h4");
  portsTitle.textContent = t.sectionPorts;
  const portsHint = document.createElement("p");
  portsHint.className = "pc-hint";
  portsHint.textContent = t.portsHint;
  const portsList = document.createElement("div");
  portsList.className = "pc-ports";
  const portsAdd = document.createElement("button");
  portsAdd.className = "pc-btn";
  portsAdd.textContent = t.portAdd;
  portsAdd.style.marginTop = "8px";
  portsSection.append(portsTitle, portsHint, portsList, portsAdd);

  const renderPorts = () => {
    portsList.replaceChildren();
    const slots = extraTextSlots(node);
    if (!slots.length) {
      const empty = document.createElement("div");
      empty.className = "pc-hint";
      empty.textContent = "—";
      portsList.appendChild(empty);
      return;
    }
    for (const slot of slots) {
      const row = document.createElement("div");
      row.className = "pc-port";
      const dot = document.createElement("span");
      dot.className = slot.connected ? "pc-dot on" : "pc-dot";
      const name = document.createElement("span");
      name.textContent = `${t.slotLabel} ${slot.shortName}`;
      const stateText = document.createElement("span");
      stateText.className = "pc-state";
      stateText.textContent = slot.connected ? t.portConnected : t.portFree;
      const remove = document.createElement("button");
      remove.className = "pc-btn";
      remove.textContent = t.portRemove;
      remove.title = t.portRemoveTip;
      remove.disabled = slot.connected;
      remove.addEventListener("click", () => {
        if (removeTextSlot(node, slot)) renderPorts();
      });
      row.append(dot, name, stateText, remove);
      portsList.appendChild(row);
    }
  };

  portsAdd.addEventListener("click", () => {
    addNextTextSlot(node, slotNames);
    renderPorts();
  });

  // ── 清洁选项 ──
  const optionsSection = document.createElement("section");
  optionsSection.className = "pc-sec";
  const optionsTitle = document.createElement("h4");
  optionsTitle.textContent = t.sectionOptions;
  optionsSection.appendChild(optionsTitle);

  const checkboxes = {};
  for (const option of BOOLEAN_OPTIONS) {
    const widget = findWidget(node, option.id);
    if (!widget) continue;
    const row = document.createElement("div");
    row.className = "pc-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = Boolean(state[option.id]);
    checkbox.addEventListener("change", () => {
      state[option.id] = checkbox.checked;
    });
    const label = document.createElement("label");
    label.textContent = isChinese() ? option.zh : option.en;
    const sub = document.createElement("span");
    sub.className = "pc-sub";
    sub.textContent = isChinese() ? option.zhHint : option.enHint;
    label.appendChild(sub);
    label.prepend(checkbox);
    row.appendChild(label);
    optionsSection.appendChild(row);
    checkboxes[option.id] = checkbox;
  }

  const selects = {};
  for (const option of COMBO_OPTIONS) {
    const widget = findWidget(node, option.id);
    if (!widget) continue;
    const row = document.createElement("div");
    row.className = "pc-row";
    const label = document.createElement("label");
    label.textContent = isChinese() ? option.zh : option.en;
    const sub = document.createElement("span");
    sub.className = "pc-sub";
    sub.textContent = isChinese() ? option.zhHint : option.enHint;
    label.appendChild(sub);
    const select = document.createElement("select");
    const values = widget.options?.values ?? [];
    for (const value of values) {
      const item = document.createElement("option");
      item.value = value;
      item.textContent = value;
      select.appendChild(item);
    }
    select.value = state[option.id];
    select.addEventListener("change", () => {
      state[option.id] = select.value;
    });
    row.append(label, select);
    optionsSection.appendChild(row);
    selects[option.id] = select;
  }

  // ── 黑名单 ──
  const blacklistSection = document.createElement("section");
  blacklistSection.className = "pc-sec";
  const blacklistTitle = document.createElement("h4");
  blacklistTitle.textContent = t.sectionBlacklist;
  const blacklistHint = document.createElement("p");
  blacklistHint.className = "pc-hint";
  blacklistHint.textContent = t.blacklistHint;
  const textarea = document.createElement("textarea");
  textarea.className = "pc-textarea";
  textarea.spellcheck = false;
  textarea.value = state.blacklist ?? "";
  textarea.addEventListener("input", () => {
    state.blacklist = textarea.value;
  });
  blacklistSection.append(blacklistTitle, blacklistHint, textarea);

  body.append(portsSection, optionsSection, blacklistSection);

  // ── 交互 ──
  const close = () => {
    overlay.remove();
    document.removeEventListener("keydown", onKeyDown, true);
  };

  const onKeyDown = (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      close();
    }
  };

  const save = () => {
    for (const name of OPTION_WIDGETS) {
      if (name in state) writeWidgetValue(node, findWidget(node, name), state[name]);
    }
    refreshSummary(node);
    close();
  };

  const reset = () => {
    for (const name of OPTION_WIDGETS) {
      if (name in (node._pcDefaults ?? {})) state[name] = node._pcDefaults[name];
    }
    for (const option of BOOLEAN_OPTIONS) {
      if (checkboxes[option.id]) checkboxes[option.id].checked = Boolean(state[option.id]);
    }
    for (const option of COMBO_OPTIONS) {
      if (selects[option.id]) selects[option.id].value = state[option.id];
    }
    textarea.value = state.blacklist ?? "";
  };

  saveButton.addEventListener("click", save);
  cancelButton.addEventListener("click", close);
  resetButton.addEventListener("click", reset);
  closeButton.addEventListener("click", close);
  overlay.addEventListener("mousedown", (event) => {
    if (event.target === overlay) close();
  });
  // 冒泡到 overlay 就掐掉：ComfyUI 的全局快捷键挂在 document / window 上，不会被抢走；
  // 事件已经先到达真正的目标（textarea 等），所以照常能输入。
  for (const type of ["keydown", "keyup", "keypress", "wheel"]) {
    overlay.addEventListener(type, (event) => {
      if (event.key !== "Escape") event.stopPropagation();
    });
  }
  // 焦点不在弹窗里时也要能按 Esc 关掉
  document.addEventListener("keydown", onKeyDown, true);

  renderPorts();
  document.body.appendChild(overlay);
  overlay.focus();
}

// ────────────────────────────── 注册 ──────────────────────────────

app.registerExtension({
  name: "Comfyui-Promote-Cleaner.clean_settings",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!NODE_TYPES.has(nodeData?.name)) return;
    const slotNames = readSlotNames(nodeData);
    chainCallback(nodeType.prototype, "onNodeCreated", function () {
      setupNode(this, slotNames);
    });
  },

  getNodeMenuItems(node) {
    if (!NODE_TYPES.has(node?.comfyClass)) return [];
    const slotNames = readSlotNames(node.constructor?.nodeData);
    const t = strings();
    return [
      {
        content: t.settings,
        callback: () => openSettingsDialog(node, slotNames),
      },
      {
        content: t.addSlot,
        callback: () => addNextTextSlot(node, slotNames),
      },
    ];
  },
});
