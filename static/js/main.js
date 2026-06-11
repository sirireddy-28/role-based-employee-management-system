// ── Auto-dismiss alerts ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  const alerts = document.querySelectorAll('.alert-custom');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 500);
    }, 4000);
  });

  // ── Sidebar toggle (mobile) ───────────────────────────────────────────
  const toggleBtn = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      if (overlay) overlay.classList.toggle('active');
    });
  }

  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      overlay.classList.remove('active');
    });
  }

  // ── Active nav link highlight ─────────────────────────────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-link-custom').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });

  // ── Table search ──────────────────────────────────────────────────────
  const searchInput = document.getElementById('table-search');
  if (searchInput) {
    searchInput.addEventListener('keyup', function () {
      const query = this.value.toLowerCase();
      document.querySelectorAll('.searchable-row').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(query) ? '' : 'none';
      });
    });
  }

  // ── Confirm delete dialogs ────────────────────────────────────────────
  document.querySelectorAll('.confirm-delete').forEach(btn => {
    btn.addEventListener('click', function (e) {
      if (!confirm('Are you sure you want to delete this record? This action cannot be undone.')) {
        e.preventDefault();
      }
    });
  });

  // ── Salary net auto-calculate ─────────────────────────────────────────
  ['basic_salary', 'allowances', 'deductions'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', calcNet);
  });

  function calcNet() {
    const basic = parseFloat(document.getElementById('basic_salary')?.value || 0);
    const allow = parseFloat(document.getElementById('allowances')?.value || 0);
    const deduct = parseFloat(document.getElementById('deductions')?.value || 0);
    const netEl = document.getElementById('net_salary_display');
    if (netEl) {
      const net = basic + allow - deduct;
      netEl.textContent = '₹' + net.toLocaleString('en-IN');
    }
  }

  // ── Animate counter numbers ───────────────────────────────────────────
  document.querySelectorAll('.stat-value[data-count]').forEach(el => {
    const target = parseInt(el.getAttribute('data-count'), 10);
    let current = 0;
    const step = Math.ceil(target / 30);
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = current.toLocaleString();
      if (current >= target) clearInterval(timer);
    }, 40);
  });
});
