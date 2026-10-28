/* Сайт работает и без этого скрипта. Здесь — только улучшения:
   1) версия для слабовидящих (панель настроек, хранение в localStorage);
   2) демо-формы (data-demo) и защита от двойной отправки;
   3) мобильное меню: закрытие по Esc и по клику вне. */
(function () {
  "use strict";

  var root = document.documentElement;
  var KEY = "a11y";
  var DEFAULT = { on: true, fs: 2, cs: "bw", noimg: false, ls: false };

  function load() {
    try { return JSON.parse(window.localStorage.getItem(KEY) || "null"); } catch (e) { return null; }
  }
  function save(state) {
    try {
      if (state) window.localStorage.setItem(KEY, JSON.stringify(state));
      else window.localStorage.removeItem(KEY);
    } catch (e) { /* приватный режим — настройки действуют до перезагрузки */ }
  }

  function apply(state) {
    var keep = root.className.split(/\s+/).filter(function (c) { return c && c.indexOf("a11y") !== 0; });
    if (state && state.on) {
      keep.push("a11y");
      if (state.fs) keep.push("a11y-fs-" + state.fs);
      if (state.cs) keep.push("a11y-cs-" + state.cs);
      if (state.noimg) keep.push("a11y-noimg");
      if (state.ls) keep.push("a11y-ls-2");
    }
    root.className = keep.join(" ");
    syncButtons(state);
  }

  function syncButtons(state) {
    var on = !!(state && state.on);
    var label = on ? "Обычная версия" : "Версия для слабовидящих";
    var toggles = document.querySelectorAll("#a11y-toggle, [data-a11y-toggle]");
    Array.prototype.forEach.call(toggles, function (t) {
      t.setAttribute("aria-expanded", on ? "true" : "false");
      var txt = t.querySelector(".a11y-link__text");
      var sr = t.querySelector(".a11y-link__sr");
      if (txt) txt.textContent = label;
      if (sr) sr.textContent = label;
      if (!txt && !sr) t.textContent = label;
    });
    var btns = document.querySelectorAll(".a11y-panel [data-a11y]");
    Array.prototype.forEach.call(btns, function (b) {
      var kind = b.getAttribute("data-a11y");
      var val = b.getAttribute("data-value");
      var pressed = null;
      if (!state) pressed = false;
      else if (kind === "fs") pressed = String(state.fs) === val;
      else if (kind === "cs") pressed = state.cs === val;
      else if (kind === "noimg") pressed = !!state.noimg;
      else if (kind === "ls") pressed = !!state.ls;
      if (pressed !== null && kind !== "off") b.setAttribute("aria-pressed", pressed ? "true" : "false");
    });
  }

  var state = load();
  syncButtons(state);

  document.addEventListener("click", function (ev) {
    var t = ev.target.closest ? ev.target.closest("#a11y-toggle, [data-a11y-toggle], .a11y-panel [data-a11y]") : null;
    if (!t) return;
    ev.preventDefault();
    if (t.id === "a11y-toggle" || t.hasAttribute("data-a11y-toggle")) {
      state = state && state.on ? null : Object.assign({}, DEFAULT);
      if (state) window.scrollTo(0, 0);
    } else {
      var kind = t.getAttribute("data-a11y");
      var val = t.getAttribute("data-value");
      if (kind === "off") state = null;
      else {
        state = Object.assign({}, DEFAULT, state || {});
        if (kind === "fs") state.fs = Number(val);
        if (kind === "cs") state.cs = val;
        if (kind === "noimg") state.noimg = !state.noimg;
        if (kind === "ls") state.ls = !state.ls;
      }
    }
    save(state);
    apply(state);
    if (!state) { var tg = document.getElementById("a11y-toggle"); if (tg) tg.focus(); }
  });

  /* ---------- Формы ---------- */
  var DEMO_TEXT = "В демо-версии форма не отправляется. На рабочем сайте заявка придёт вам на почту и в Telegram.";
  Array.prototype.forEach.call(document.querySelectorAll("form.lead-form"), function (form) {
    form.addEventListener("submit", function (ev) {
      var btn = form.querySelector("[type=submit]");
      if (form.hasAttribute("data-demo")) {
        ev.preventDefault();
        var msg = form.querySelector(".form-demo-msg");
        if (msg) {
          msg.hidden = false;
          var p = msg.querySelector("p");
          if (p) p.textContent = DEMO_TEXT;
          msg.focus();
        } else {
          window.alert(DEMO_TEXT);
        }
        return;
      }
      if (btn) {
        if (btn.getAttribute("aria-disabled") === "true") { ev.preventDefault(); return; }
        btn.setAttribute("aria-disabled", "true");
        btn.setAttribute("data-label", btn.textContent);
        btn.textContent = "Отправляем…";
        /* если пользователь вернулся «Назад» — разблокируем */
        window.addEventListener("pageshow", function () {
          btn.removeAttribute("aria-disabled");
          if (btn.getAttribute("data-label")) btn.textContent = btn.getAttribute("data-label");
        }, { once: true });
      }
    });
  });

  /* Фокус на сводке ошибок, если форма вернулась с ошибками */
  var summary = document.querySelector(".form-alert--error[tabindex]");
  if (summary) summary.focus();

  /* ---------- Мобильное меню ---------- */
  var menu = document.querySelector(".nav-mobile");
  if (menu) {
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && menu.open) { menu.open = false; menu.querySelector("summary").focus(); }
    });
    document.addEventListener("click", function (ev) {
      if (menu.open && !menu.contains(ev.target)) menu.open = false;
    });
    var summ = menu.querySelector("summary");
    menu.addEventListener("toggle", function () { summ.setAttribute("aria-expanded", menu.open ? "true" : "false"); });
    summ.setAttribute("aria-expanded", "false");
  }
})();
