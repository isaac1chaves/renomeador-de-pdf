(() => {
  "use strict";
  const config = window.APP_CONFIG || {};
  const setText = (selector, value) => document.querySelectorAll(selector).forEach(el => el.textContent = value);
  const setLink = (selector, value) => document.querySelectorAll(selector).forEach(el => {
    el.href = value || "#";
    if (!value || value === "#") {
      el.setAttribute("aria-disabled", "true");
      el.title = "Link ainda não configurado em config.js";
      el.addEventListener("click", event => event.preventDefault());
    }
  });
  setText("[data-version]", config.version || "1.3.2");
  setLink("[data-download]", config.downloadUrl);
  setLink("[data-repository]", config.repositoryUrl);
  setLink("[data-release]", config.releaseUrl);
  const year = document.querySelector("#year");
  if (year) year.textContent = new Date().getFullYear();
  const button = document.querySelector(".menu-button");
  const menu = document.querySelector("#menu");
  if (button && menu) {
    button.addEventListener("click", () => {
      const open = menu.classList.toggle("open");
      button.setAttribute("aria-expanded", String(open));
    });
    menu.querySelectorAll("a").forEach(link => link.addEventListener("click", () => {
      menu.classList.remove("open");
      button.setAttribute("aria-expanded", "false");
    }));
  }
})();
