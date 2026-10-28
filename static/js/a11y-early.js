/* Версия для слабовидящих: применяем сохранённые настройки ДО отрисовки страницы,
   чтобы не было «мигания». Подключается в <head> без defer. */
(function () {
  "use strict";
  var state;
  try { state = JSON.parse(window.localStorage.getItem("a11y") || "null"); } catch (e) { state = null; }
  if (!state || !state.on) return;
  var c = ["a11y"];
  if (/^[123]$/.test(String(state.fs))) c.push("a11y-fs-" + state.fs);
  if (/^(bw|wb|blue)$/.test(String(state.cs))) c.push("a11y-cs-" + state.cs);
  if (state.noimg) c.push("a11y-noimg");
  if (state.ls) c.push("a11y-ls-2");
  document.documentElement.className += " " + c.join(" ");
})();
