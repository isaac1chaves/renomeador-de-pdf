
(() => {
  const cfg = window.APP_CONFIG || {};
  document.querySelectorAll('[data-version]').forEach(el => el.textContent = cfg.version || '');
  document.querySelectorAll('[data-download]').forEach(el => {
    el.href = cfg.downloadUrl || '#';
    el.addEventListener('click', () => {
      if (!cfg.downloadUrl) alert('O link de download ainda não foi configurado.');
    });
  });
  document.querySelectorAll('[data-repository]').forEach(el => el.href = cfg.repositoryUrl || '#');
  document.querySelectorAll('[data-release]').forEach(el => el.href = cfg.releaseUrl || cfg.repositoryUrl || '#');
  document.getElementById('year').textContent = new Date().getFullYear();
})();
