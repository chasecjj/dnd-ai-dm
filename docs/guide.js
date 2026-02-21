/* ================================================================
   Adventurer's Compendium — Home Page Logic
   Role selector with localStorage persistence,
   feature card visibility toggle
   ================================================================ */

(function () {
  'use strict';

  // ── DOM refs ──
  const btnPlayer = document.getElementById('btn-player');
  const btnDM = document.getElementById('btn-dm');
  const playerCards = document.getElementById('player-cards');
  const dmCards = document.getElementById('dm-cards');

  if (!btnPlayer || !btnDM || !playerCards || !dmCards) return;

  // ── State ──
  let currentRole = localStorage.getItem('guide-role') || null;

  // ── Role Selector ──
  function setRole(role) {
    currentRole = role;
    localStorage.setItem('guide-role', role);

    // Button states
    btnPlayer.classList.toggle('active', role === 'player');
    btnDM.classList.toggle('active', role === 'dm');

    // Feature card visibility
    playerCards.classList.toggle('visible', role === 'player');
    dmCards.classList.toggle('visible', role === 'dm');
  }

  btnPlayer.addEventListener('click', () => setRole('player'));
  btnDM.addEventListener('click', () => setRole('dm'));

  // ── Restore saved role ──
  if (currentRole === 'player' || currentRole === 'dm') {
    setRole(currentRole);
  }
})();
