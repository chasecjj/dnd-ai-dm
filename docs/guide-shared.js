/* ================================================================
   Adventurer's Compendium — Shared JS
   Loaded by every page: home + all 5 subpages
   Handles: SVG sprite (path-aware), hamburger, expandable cards,
   filter inputs, active nav highlighting, page-enter trigger
   ================================================================ */

(function () {
  'use strict';

  // ── SVG Sprite Loader (path-aware via <meta name="guide-base">) ──
  const baseMeta = document.querySelector('meta[name="guide-base"]');
  const base = baseMeta ? baseMeta.getAttribute('content') : '';

  async function loadSpriteSheet() {
    const container = document.getElementById('svg-sprite-container');
    if (!container) return;
    try {
      const resp = await fetch(base + 'guide-icons.svg');
      if (!resp.ok) throw new Error(`SVG sprite: ${resp.status}`);
      container.innerHTML = await resp.text();
    } catch (e) {
      console.warn('Could not load SVG sprite sheet:', e.message);
    }
  }

  // ── Hamburger Menu ──
  function initHamburger() {
    const hamburger = document.getElementById('nav-hamburger');
    const navLinks = document.getElementById('nav-links');
    if (!hamburger || !navLinks) return;

    hamburger.addEventListener('click', () => {
      hamburger.classList.toggle('open');
      navLinks.classList.toggle('open');
    });

    // Close nav on link click (mobile)
    navLinks.addEventListener('click', (e) => {
      if (e.target.tagName === 'A') {
        hamburger.classList.remove('open');
        navLinks.classList.remove('open');
      }
    });
  }

  // ── Active Nav Highlighting (via data-page matching body[data-page]) ──
  function highlightActiveNav() {
    const currentPage = document.body.getAttribute('data-page');
    if (!currentPage) return;
    document.querySelectorAll('.nav-links a[data-page]').forEach((link) => {
      if (link.getAttribute('data-page') === currentPage) {
        link.classList.add('active');
      }
    });
  }

  // ── Expandable Cards ──
  function bindExpandableCards(container) {
    container.querySelectorAll('.card.expandable').forEach((card) => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('a, button, input')) return;
        card.classList.toggle('expanded');
      });
    });
  }

  // ── Command Filter ──
  function bindFilterInputs(container) {
    container.querySelectorAll('.filter-input').forEach((input) => {
      const tableId = input.getAttribute('data-filter-target');
      const table = container.querySelector('#' + tableId) ||
                    input.closest('section, main')?.querySelector('.guide-table');
      if (!table) return;

      input.addEventListener('input', () => {
        const query = input.value.toLowerCase().trim();
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach((row) => {
          row.style.display = row.textContent.toLowerCase().includes(query) ? '' : 'none';
        });
      });
    });
  }

  // ── Init ──
  async function init() {
    await loadSpriteSheet();
    initHamburger();
    highlightActiveNav();
    bindExpandableCards(document);
    bindFilterInputs(document);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
