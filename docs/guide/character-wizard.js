/* ================================================================
   Character Creation Wizard — Core Logic
   7-step interactive wizard: Name → Race → Class → Background →
   Ability Scores → Equipment → Character Sheet Summary.
   Depends on: guide-shared.js (SVG sprite), wizard-data.js (D&D data)
   ================================================================ */

(function () {
  'use strict';

  var D = window.WIZARD_DATA;
  if (!D) { console.error('wizard-data.js must load before character-wizard.js'); return; }

  // ── Shorthand helpers ────────────────────────────────────────────
  var $ = function (id) { return document.getElementById(id); };
  var STEPS = 7;
  var STEP_LABELS = ['Name', 'Race', 'Class', 'Background', 'Abilities', 'Equipment', 'Sheet'];
  var PROFICIENCY_BONUS = 2;

  // ── Character State ──────────────────────────────────────────────
  var state = {
    step: 1,
    name: '',
    concept: '',
    gender: 'male',
    race: null,
    subrace: null,
    draconicAncestry: null,
    halfElfBonuses: [],
    halfElfSkills: [],
    cls: null,
    classSkills: [],
    background: null,
    personalityTrait: 0,
    ideal: 0,
    bond: 0,
    flaw: 0,
    abilityMethod: 'standard-array',
    standardArray: {},
    pointBuy: { STR: 8, DEX: 8, CON: 8, INT: 8, WIS: 8, CHA: 8 },
    rollResults: [],
    rollAssign: {},
    equipChoices: []
  };

  // ── Math helpers ─────────────────────────────────────────────────
  function abilityMod(score) { return Math.floor((score - 10) / 2); }
  function modStr(m) { return m >= 0 ? '+' + m : String(m); }
  function rand(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

  // ── Racial Bonus Calculator ──────────────────────────────────────
  function getRacialBonuses() {
    if (!state.race) return {};
    var race = D.RACES[state.race];
    var bonuses = {};
    // Base race bonuses
    var base = race.abilityBonuses || {};
    D.ABILITY_NAMES.forEach(function (a) { bonuses[a] = base[a] || 0; });
    // Subrace bonuses
    if (race.subraces && state.subrace !== null) {
      var sub = race.subraces[state.subrace];
      if (sub && sub.abilityBonuses) {
        D.ABILITY_NAMES.forEach(function (a) {
          bonuses[a] += sub.abilityBonuses[a] || 0;
        });
      }
    }
    // Half-elf flexible bonuses
    if (state.halfElfBonuses.length) {
      state.halfElfBonuses.forEach(function (a) { bonuses[a] += 1; });
    }
    return bonuses;
  }

  // ── Final Ability Scores ─────────────────────────────────────────
  function getBaseScores() {
    var scores = {};
    if (state.abilityMethod === 'standard-array') {
      D.ABILITY_NAMES.forEach(function (a) {
        scores[a] = state.standardArray[a] !== undefined ? Number(state.standardArray[a]) : 8;
      });
    } else if (state.abilityMethod === 'point-buy') {
      D.ABILITY_NAMES.forEach(function (a) { scores[a] = state.pointBuy[a]; });
    } else {
      D.ABILITY_NAMES.forEach(function (a) {
        var idx = state.rollAssign[a];
        scores[a] = (idx !== undefined && state.rollResults[idx] !== undefined)
          ? state.rollResults[idx] : 10;
      });
    }
    return scores;
  }

  function getFinalScores() {
    var base = getBaseScores();
    var racial = getRacialBonuses();
    var final = {};
    D.ABILITY_NAMES.forEach(function (a) { final[a] = base[a] + (racial[a] || 0); });
    return final;
  }

  // ── All Skill Proficiencies ──────────────────────────────────────
  function getAllSkillProficiencies() {
    var skills = [];
    // Race
    if (state.race) {
      var race = D.RACES[state.race];
      (race.skillProficiencies || []).forEach(function (s) {
        if (skills.indexOf(s) === -1) skills.push(s);
      });
    }
    // Half-elf bonus skills
    state.halfElfSkills.forEach(function (s) {
      if (skills.indexOf(s) === -1) skills.push(s);
    });
    // Background
    if (state.background) {
      var bg = D.BACKGROUNDS[state.background];
      (bg.skillProficiencies || []).forEach(function (s) {
        if (skills.indexOf(s) === -1) skills.push(s);
      });
    }
    // Class choices
    state.classSkills.forEach(function (s) {
      if (skills.indexOf(s) === -1) skills.push(s);
    });
    return skills.sort();
  }

  // ── HP Calculation ───────────────────────────────────────────────
  function getHP() {
    if (!state.cls) return 0;
    var c = D.CLASSES[state.cls];
    var scores = getFinalScores();
    var hp = c.hitDie + abilityMod(scores.CON);
    // Hill Dwarf Dwarven Toughness: +1 HP per level
    if (state.race === 'dwarf' && state.subrace === 0) hp += 1;
    return Math.max(hp, 1);
  }

  // ── AC Calculation ───────────────────────────────────────────────
  function getEquipmentList() {
    if (!state.cls) return [];
    var c = D.CLASSES[state.cls];
    var items = [];
    // Class equipment choices
    c.startingEquipment.choices.forEach(function (options, i) {
      var chosen = state.equipChoices[i] !== undefined ? state.equipChoices[i] : 0;
      items.push(options[chosen]);
    });
    // Class fixed equipment
    c.startingEquipment.fixed.forEach(function (item) { items.push(item); });
    // Background equipment
    if (state.background) {
      D.BACKGROUNDS[state.background].equipment.forEach(function (item) { items.push(item); });
    }
    return items;
  }

  function getAC() {
    var scores = getFinalScores();
    var dexMod = abilityMod(scores.DEX);
    var items = getEquipmentList();
    var joined = items.join('||').toLowerCase();

    var hasShield = joined.indexOf('shield') !== -1;
    var shieldBonus = hasShield ? 2 : 0;

    // Check for specific armor types in equipment
    if (joined.indexOf('chain mail') !== -1) return 16 + shieldBonus;
    if (joined.indexOf('scale mail') !== -1) return 14 + Math.min(dexMod, 2) + shieldBonus;
    if (joined.indexOf('leather armor') !== -1) {
      // Barbarian unarmored defense may beat leather — check
      if (state.cls === 'barbarian') {
        var unarmoredAC = 10 + dexMod + abilityMod(scores.CON);
        var leatherAC = 11 + dexMod;
        return Math.max(unarmoredAC, leatherAC) + shieldBonus;
      }
      return 11 + dexMod + shieldBonus;
    }

    // No armor
    if (state.cls === 'barbarian') return 10 + dexMod + abilityMod(scores.CON) + shieldBonus;
    if (state.cls === 'monk') return 10 + dexMod + abilityMod(scores.WIS);
    return 10 + dexMod + shieldBonus;
  }

  // ── Speed ────────────────────────────────────────────────────────
  function getSpeed() {
    if (!state.race) return 30;
    var race = D.RACES[state.race];
    var speed = race.speed;
    // Wood Elf Fleet of Foot: 35 ft
    if (state.race === 'elf' && state.subrace === 1) speed = 35;
    return speed;
  }

  // ── Spell Slots ──────────────────────────────────────────────────
  function getSpellSlotMax() {
    if (!state.cls) return 0;
    var c = D.CLASSES[state.cls];
    if (!c.spellcasting || !c.spellcasting.spellSlots) return 0;
    var total = 0;
    Object.keys(c.spellcasting.spellSlots).forEach(function (level) {
      total += c.spellcasting.spellSlots[level];
    });
    return total;
  }

  // ── Lay on Hands Pool ────────────────────────────────────────────
  function getLayOnHands() {
    return state.cls === 'paladin' ? 5 : 0;
  }

  // ================================================================
  //  PROGRESS BAR
  // ================================================================
  function renderProgress() {
    var container = $('wizard-progress');
    var html = '';
    for (var i = 1; i <= STEPS; i++) {
      var cls = '';
      if (i < state.step) cls = 'completed';
      else if (i === state.step) cls = 'active';

      html += '<div class="progress-step-wrapper">' +
        '<div class="progress-circle ' + cls + '" data-step="' + i + '"><span>' + i + '</span></div>' +
        '<span class="progress-label">' + STEP_LABELS[i - 1] + '</span>' +
        '</div>';
      if (i < STEPS) {
        html += '<div class="progress-connector' + (i < state.step ? ' completed' : '') + '"></div>';
      }
    }
    container.innerHTML = html;

    // Click to jump to completed/active steps
    container.querySelectorAll('.progress-circle').forEach(function (circle) {
      circle.addEventListener('click', function () {
        var target = Number(this.getAttribute('data-step'));
        if (target <= state.step) goToStep(target);
      });
    });
  }

  // ================================================================
  //  STEP NAVIGATION
  // ================================================================
  function goToStep(n) {
    if (n < 1 || n > STEPS) return;
    // Hide current step
    var current = $('step-' + state.step);
    if (current) current.classList.remove('active');
    state.step = n;
    // Show target step
    var target = $('step-' + n);
    if (target) target.classList.add('active');

    // Render step content on entry
    if (n === 2) renderRaceGrid();
    if (n === 3) renderClassGrid();
    if (n === 4) renderBackgroundGrid();
    if (n === 5) renderAbilityPanel();
    if (n === 6) renderEquipment();
    if (n === 7) renderCharSheet();

    // Update navigation buttons
    $('prev-btn').disabled = (n === 1);
    var nextBtn = $('next-btn');
    if (n === STEPS) {
      nextBtn.style.display = 'none';
    } else {
      nextBtn.style.display = '';
      nextBtn.textContent = 'Next';
    }

    renderProgress();
    saveState();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function canAdvance() {
    var s = state.step;
    if (s === 1 && !state.name.trim()) return false;
    if (s === 2 && !state.race) return false;
    if (s === 3) {
      if (!state.cls) return false;
      var c = D.CLASSES[state.cls];
      if (state.classSkills.length < c.skillChoices.pick) return false;
    }
    if (s === 4 && !state.background) return false;
    if (s === 5) {
      if (state.abilityMethod === 'standard-array') {
        var assigned = Object.keys(state.standardArray).length;
        if (assigned < 6) return false;
        // Check all values are unique
        var vals = D.ABILITY_NAMES.map(function (a) { return state.standardArray[a]; });
        var unique = vals.filter(function (v, i) { return vals.indexOf(v) === i; });
        if (unique.length < 6) return false;
      }
      if (state.abilityMethod === 'roll' && state.rollResults.length < 6) return false;
      if (state.abilityMethod === 'roll') {
        var assignCount = Object.keys(state.rollAssign).length;
        if (assignCount < 6) return false;
      }
    }
    // Dragonborn requires ancestry selection
    if (s === 2 && state.race === 'dragonborn' && state.draconicAncestry === null) return false;
    // Races with subraces require selection
    if (s === 2 && state.race) {
      var race = D.RACES[state.race];
      if (race.subraces && race.subraces.length > 0 && state.subrace === null) return false;
    }
    // Half-elf requires bonus ability choices
    if (s === 2 && state.race === 'half-elf') {
      var choice = D.RACES['half-elf'].abilityBonusChoice;
      if (state.halfElfBonuses.length < choice.count) return false;
    }
    return true;
  }

  // ================================================================
  //  STEP 1: NAME & CONCEPT
  // ================================================================
  function initNameStep() {
    var nameInput = $('char-name');
    var conceptInput = $('char-concept');
    var generateBtn = document.querySelector('.generate-name-btn');
    var genderBtns = document.querySelectorAll('.gender-btn');

    nameInput.value = state.name;
    conceptInput.value = state.concept;

    nameInput.addEventListener('input', function () { state.name = this.value; saveState(); });
    conceptInput.addEventListener('input', function () { state.concept = this.value; saveState(); });

    // Gender toggle
    genderBtns.forEach(function (btn) {
      if (btn.getAttribute('data-gender') === state.gender) btn.classList.add('active');
      else btn.classList.remove('active');
      btn.addEventListener('click', function () {
        state.gender = this.getAttribute('data-gender');
        genderBtns.forEach(function (b) { b.classList.remove('active'); });
        this.classList.add('active');
      });
    });

    // Name generator button
    generateBtn.addEventListener('click', function () {
      if (!state.race) return;
      var race = D.RACES[state.race];
      var table = race.nameTable;
      var first = rand(table[state.gender] || table.male);
      var surname = table.surname ? rand(table.surname) : '';
      state.name = first + (surname ? ' ' + surname : '');
      nameInput.value = state.name;
      saveState();
    });
  }

  function updateNameGenerator() {
    var btn = document.querySelector('.generate-name-btn');
    if (state.race) {
      btn.disabled = false;
      btn.title = 'Generate a ' + D.RACES[state.race].name + ' name';
    } else {
      btn.disabled = true;
      btn.title = 'Choose a race first to generate names';
    }
  }

  // ================================================================
  //  STEP 2: RACE
  // ================================================================
  function renderRaceGrid() {
    var grid = $('race-grid');
    var html = '';
    Object.keys(D.RACES).forEach(function (key) {
      var race = D.RACES[key];
      var selected = state.race === key ? ' selected' : '';
      var bonusStr = Object.keys(race.abilityBonuses)
        .filter(function (a) { return race.abilityBonuses[a] > 0; })
        .map(function (a) { return '+' + race.abilityBonuses[a] + ' ' + a; })
        .join(', ') || 'Flexible';

      html += '<div class="card selectable accent-' + race.accentColor + selected + '" data-key="' + key + '">' +
        '<div class="card-header">' +
        '<div class="card-icon"><svg class="icon-lg" aria-hidden="true"><use href="#' + race.iconId + '"></use></svg></div>' +
        '<div><div class="card-title">' + race.name + '</div>' +
        '<div class="card-subtitle">' + bonusStr + '</div></div>' +
        '</div>' +
        '<p class="card-summary">' + race.description + '</p>' +
        '</div>';
    });
    grid.innerHTML = html;

    // Click handlers
    grid.querySelectorAll('.card.selectable').forEach(function (card) {
      card.addEventListener('click', function () { selectRace(this.getAttribute('data-key')); });
    });

    // Restore selection details
    if (state.race) renderRaceDetails();
  }

  function selectRace(key) {
    console.log('[DEBUG] selectRace called with key:', key);
    var prev = state.race;
    state.race = key;
    console.log('[DEBUG] state.race is now:', state.race);
    // Reset subrace/ancestry/bonuses when changing race
    if (prev !== key) {
      state.subrace = null;
      state.draconicAncestry = null;
      state.halfElfBonuses = [];
      state.halfElfSkills = [];
    }
    // Update card selection
    $('race-grid').querySelectorAll('.card.selectable').forEach(function (card) {
      card.classList.toggle('selected', card.getAttribute('data-key') === key);
    });
    renderRaceDetails();
    updateNameGenerator();
    saveState();
    console.log('[DEBUG] after saveState, localStorage:', localStorage.getItem(STORAGE_KEY));
  }

  function renderRaceDetails() {
    var container = $('race-details');
    if (!state.race) { container.innerHTML = ''; container.style.display = 'none'; return; }
    var race = D.RACES[state.race];

    var html = '<div class="card accent-' + race.accentColor + '">';
    html += '<h3 style="font-family:Cinzel,serif;color:var(--gold);margin-bottom:12px">' + race.name + '</h3>';

    // Core info
    html += '<div class="cards-grid cols-2" style="margin-bottom:16px">';
    html += '<div><strong>Speed:</strong> ' + race.speed + ' ft.</div>';
    html += '<div><strong>Size:</strong> ' + race.size + '</div>';
    html += '<div><strong>Darkvision:</strong> ' + (race.darkvision || 'None') + (race.darkvision ? ' ft.' : '') + '</div>';
    html += '<div><strong>Languages:</strong> ' + race.languages.join(', ') + '</div>';
    html += '</div>';

    // Traits
    html += '<h4 style="color:var(--text-bright);margin-bottom:8px">Racial Traits</h4>';
    html += '<ul style="padding-left:18px;margin-bottom:16px">';
    race.traits.forEach(function (t) {
      html += '<li style="margin-bottom:6px"><strong>' + t.name + '.</strong> ' + t.description + '</li>';
    });
    html += '</ul>';

    // Subraces
    if (race.subraces && race.subraces.length > 0) {
      html += '<h4 style="color:var(--text-bright);margin-bottom:8px">Choose a Subrace</h4>';
      html += '<div class="cards-grid cols-2">';
      race.subraces.forEach(function (sub, i) {
        var sel = state.subrace === i ? ' selected' : '';
        var subBonuses = Object.keys(sub.abilityBonuses)
          .map(function (a) { return '+' + sub.abilityBonuses[a] + ' ' + a; }).join(', ');
        html += '<div class="card selectable' + sel + '" data-subrace="' + i + '" style="padding:14px">' +
          '<div class="card-title" style="margin-bottom:4px">' + sub.name + '</div>' +
          '<div class="card-subtitle">' + subBonuses + '</div>';
        sub.traits.forEach(function (t) {
          html += '<p style="font-size:0.82rem;color:var(--text-dim);margin-top:6px"><strong>' + t.name + '.</strong> ' + t.description + '</p>';
        });
        html += '</div>';
      });
      html += '</div>';
    }

    // Dragonborn ancestry
    if (race.draconicAncestry) {
      html += '<h4 style="color:var(--text-bright);margin:16px 0 8px">Choose Draconic Ancestry</h4>';
      html += '<div class="cards-grid cols-2">';
      race.draconicAncestry.forEach(function (da, i) {
        var sel = state.draconicAncestry === i ? ' selected' : '';
        html += '<div class="card selectable' + sel + '" data-ancestry="' + i + '" style="padding:10px">' +
          '<div class="card-title" style="font-size:0.85rem;margin-bottom:2px">' + da.dragon + ' Dragon</div>' +
          '<div style="font-size:0.78rem;color:var(--text-dim)">' + da.damageType + ' — ' + da.breath + '</div>' +
          '</div>';
      });
      html += '</div>';
    }

    // Half-elf ability bonus choice
    if (race.abilityBonusChoice) {
      var choice = race.abilityBonusChoice;
      html += '<h4 style="color:var(--text-bright);margin:16px 0 8px">Choose ' + choice.count + ' Ability Bonuses (+' + choice.amount + ' each)</h4>';
      html += '<div class="skill-choices-grid" id="half-elf-ability-grid">';
      D.ABILITY_NAMES.forEach(function (a) {
        if (choice.exclude.indexOf(a) !== -1) return;
        var checked = state.halfElfBonuses.indexOf(a) !== -1;
        html += '<label class="skill-choice">' +
          '<input type="checkbox" value="' + a + '"' + (checked ? ' checked' : '') + '> ' +
          D.ABILITY_FULL_NAMES[D.ABILITY_NAMES.indexOf(a)] + ' (' + a + ')' +
          '</label>';
      });
      html += '</div>';
      html += '<p class="skill-choices-remaining" id="half-elf-bonus-remaining">' +
        (choice.count - state.halfElfBonuses.length) + ' remaining</p>';
    }

    // Half-elf skill versatility
    if (race.skillBonusChoices) {
      html += '<h4 style="color:var(--text-bright);margin:16px 0 8px">Choose ' + race.skillBonusChoices + ' Skill Proficiencies</h4>';
      html += '<div class="skill-choices-grid" id="half-elf-skill-grid">';
      D.ALL_SKILLS.forEach(function (skill) {
        var checked = state.halfElfSkills.indexOf(skill.name) !== -1;
        // Lock if already granted by background
        var lockedByBg = state.background && D.BACKGROUNDS[state.background].skillProficiencies.indexOf(skill.name) !== -1;
        var cls = 'skill-choice' + (lockedByBg ? ' locked' : '');
        html += '<label class="' + cls + '">' +
          '<input type="checkbox" value="' + skill.name + '"' +
          (checked ? ' checked' : '') + (lockedByBg ? ' disabled' : '') + '> ' +
          skill.name + ' <span style="color:var(--text-dim);font-size:0.75rem">(' + skill.ability + ')</span>' +
          '</label>';
      });
      html += '</div>';
      html += '<p class="skill-choices-remaining" id="half-elf-skill-remaining">' +
        (race.skillBonusChoices - state.halfElfSkills.length) + ' remaining</p>';
    }

    html += '</div>';
    container.innerHTML = html;
    container.style.display = 'block';

    // Bind subrace clicks
    container.querySelectorAll('[data-subrace]').forEach(function (card) {
      card.addEventListener('click', function () {
        state.subrace = Number(this.getAttribute('data-subrace'));
        renderRaceDetails();
        saveState();
      });
    });

    // Bind ancestry clicks
    container.querySelectorAll('[data-ancestry]').forEach(function (card) {
      card.addEventListener('click', function () {
        state.draconicAncestry = Number(this.getAttribute('data-ancestry'));
        renderRaceDetails();
        saveState();
      });
    });

    // Bind half-elf ability checkboxes
    var abilityGrid = $('half-elf-ability-grid');
    if (abilityGrid) {
      abilityGrid.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
        cb.addEventListener('change', function () {
          var ability = this.value;
          if (this.checked) {
            if (state.halfElfBonuses.length < D.RACES['half-elf'].abilityBonusChoice.count) {
              state.halfElfBonuses.push(ability);
            } else {
              this.checked = false;
              return;
            }
          } else {
            state.halfElfBonuses = state.halfElfBonuses.filter(function (a) { return a !== ability; });
          }
          var remaining = $('half-elf-bonus-remaining');
          if (remaining) remaining.textContent = (D.RACES['half-elf'].abilityBonusChoice.count - state.halfElfBonuses.length) + ' remaining';
          saveState();
        });
      });
    }

    // Bind half-elf skill checkboxes
    var skillGrid = $('half-elf-skill-grid');
    if (skillGrid) {
      skillGrid.querySelectorAll('input[type="checkbox"]:not(:disabled)').forEach(function (cb) {
        cb.addEventListener('change', function () {
          var skill = this.value;
          if (this.checked) {
            if (state.halfElfSkills.length < D.RACES['half-elf'].skillBonusChoices) {
              state.halfElfSkills.push(skill);
            } else {
              this.checked = false;
              return;
            }
          } else {
            state.halfElfSkills = state.halfElfSkills.filter(function (s) { return s !== skill; });
          }
          var remaining = $('half-elf-skill-remaining');
          if (remaining) remaining.textContent = (D.RACES['half-elf'].skillBonusChoices - state.halfElfSkills.length) + ' remaining';
          saveState();
        });
      });
    }
  }

  // ================================================================
  //  STEP 3: CLASS
  // ================================================================
  function renderClassGrid() {
    var grid = $('class-grid');
    var html = '';
    Object.keys(D.CLASSES).forEach(function (key) {
      var c = D.CLASSES[key];
      var selected = state.cls === key ? ' selected' : '';
      html += '<div class="card selectable accent-' + c.accentColor + selected + '" data-key="' + key + '">' +
        '<div class="card-header">' +
        '<div class="card-icon"><svg class="icon-lg" aria-hidden="true"><use href="#' + c.iconId + '"></use></svg></div>' +
        '<div><div class="card-title">' + c.name + '</div>' +
        '<div class="card-subtitle">d' + c.hitDie + ' · ' + c.primaryAbility + '</div></div>' +
        '</div>' +
        '<p class="card-summary">' + c.description + '</p>' +
        '</div>';
    });
    grid.innerHTML = html;

    grid.querySelectorAll('.card.selectable').forEach(function (card) {
      card.addEventListener('click', function () { selectClass(this.getAttribute('data-key')); });
    });

    if (state.cls) {
      renderClassDetails();
      renderSkillChoices();
    }
  }

  function selectClass(key) {
    var prev = state.cls;
    state.cls = key;
    if (prev !== key) {
      state.classSkills = [];
      state.equipChoices = [];
    }
    $('class-grid').querySelectorAll('.card.selectable').forEach(function (card) {
      card.classList.toggle('selected', card.getAttribute('data-key') === key);
    });
    renderClassDetails();
    renderSkillChoices();
    saveState();
  }

  function renderClassDetails() {
    var container = $('class-details');
    if (!state.cls) { container.innerHTML = ''; container.style.display = 'none'; return; }
    var c = D.CLASSES[state.cls];

    var html = '<div class="card accent-' + c.accentColor + '">';
    html += '<h3 style="font-family:Cinzel,serif;color:var(--gold);margin-bottom:12px">' + c.name + '</h3>';

    html += '<div class="cards-grid cols-2" style="margin-bottom:16px">';
    html += '<div><strong>Hit Die:</strong> d' + c.hitDie + '</div>';
    html += '<div><strong>Primary:</strong> ' + c.primaryAbility + '</div>';
    html += '<div><strong>Saving Throws:</strong> ' + c.savingThrows.join(', ') + '</div>';
    html += '<div><strong>HP at 1st Level:</strong> ' + c.hitDie + ' + CON mod</div>';
    html += '</div>';

    // Proficiencies
    html += '<h4 style="color:var(--text-bright);margin-bottom:8px">Proficiencies</h4>';
    html += '<ul style="padding-left:18px;margin-bottom:16px">';
    if (c.armorProficiencies.length) html += '<li><strong>Armor:</strong> ' + c.armorProficiencies.join(', ') + '</li>';
    if (c.weaponProficiencies.length) html += '<li><strong>Weapons:</strong> ' + c.weaponProficiencies.join(', ') + '</li>';
    if (c.toolProficiencies.length) html += '<li><strong>Tools:</strong> ' + c.toolProficiencies.join(', ') + '</li>';
    html += '</ul>';

    // Features
    html += '<h4 style="color:var(--text-bright);margin-bottom:8px">Level 1 Features</h4>';
    html += '<ul style="padding-left:18px;margin-bottom:16px">';
    c.features.forEach(function (f) {
      html += '<li style="margin-bottom:6px"><strong>' + f.name + '.</strong> ' + f.description + '</li>';
    });
    html += '</ul>';

    // Spellcasting
    if (c.spellcasting) {
      html += '<h4 style="color:var(--text-bright);margin-bottom:8px">Spellcasting</h4>';
      var sc = c.spellcasting;
      html += '<div style="font-size:0.88rem;color:var(--text);margin-bottom:8px">';
      html += '<strong>Ability:</strong> ' + sc.ability;
      if (sc.cantripsKnown) html += ' · <strong>Cantrips:</strong> ' + sc.cantripsKnown;
      var slotTotal = 0;
      Object.keys(sc.spellSlots).forEach(function (l) { slotTotal += sc.spellSlots[l]; });
      if (slotTotal) html += ' · <strong>1st-Level Slots:</strong> ' + slotTotal;
      html += '</div>';
      if (sc.note) html += '<p style="font-size:0.82rem;color:var(--text-dim);font-style:italic;margin-bottom:8px">' + sc.note + '</p>';
      if (sc.spellList && sc.spellList.length) {
        html += '<div style="font-size:0.82rem;color:var(--text-dim)"><strong>Available Spells:</strong> ' + sc.spellList.join(', ') + '</div>';
      }
    }

    html += '</div>';
    container.innerHTML = html;
    container.style.display = 'block';
  }

  function renderSkillChoices() {
    var section = $('class-skills');
    if (!state.cls) { section.style.display = 'none'; return; }
    var c = D.CLASSES[state.cls];
    section.style.display = 'block';

    $('skill-choices-label').textContent = 'Choose ' + c.skillChoices.pick + ' from the list below:';

    // Determine locked skills (from race + background + half-elf)
    var locked = [];
    if (state.race) {
      (D.RACES[state.race].skillProficiencies || []).forEach(function (s) { locked.push(s); });
    }
    state.halfElfSkills.forEach(function (s) { if (locked.indexOf(s) === -1) locked.push(s); });
    if (state.background) {
      (D.BACKGROUNDS[state.background].skillProficiencies || []).forEach(function (s) {
        if (locked.indexOf(s) === -1) locked.push(s);
      });
    }

    var grid = $('skill-choices-grid');
    var html = '';
    c.skillChoices.from.forEach(function (skillName) {
      var isLocked = locked.indexOf(skillName) !== -1;
      var isChecked = state.classSkills.indexOf(skillName) !== -1;
      var ability = '';
      D.ALL_SKILLS.forEach(function (s) { if (s.name === skillName) ability = s.ability; });
      var cls = 'skill-choice';
      if (isLocked) cls += ' locked racial';
      html += '<label class="' + cls + '">' +
        '<input type="checkbox" value="' + skillName + '"' +
        (isChecked || isLocked ? ' checked' : '') +
        (isLocked ? ' disabled' : '') + '> ' +
        skillName + ' <span style="color:var(--text-dim);font-size:0.75rem">(' + ability + ')</span>' +
        (isLocked ? ' <span style="font-size:0.7rem;color:var(--green)">(racial/background)</span>' : '') +
        '</label>';
    });
    grid.innerHTML = html;
    updateSkillRemaining();

    // Bind checkboxes
    grid.querySelectorAll('input[type="checkbox"]:not(:disabled)').forEach(function (cb) {
      cb.addEventListener('change', function () {
        var skill = this.value;
        if (this.checked) {
          if (state.classSkills.length < c.skillChoices.pick) {
            state.classSkills.push(skill);
          } else {
            this.checked = false;
            return;
          }
        } else {
          state.classSkills = state.classSkills.filter(function (s) { return s !== skill; });
        }
        updateSkillRemaining();
        saveState();
      });
    });
  }

  function updateSkillRemaining() {
    if (!state.cls) return;
    var c = D.CLASSES[state.cls];
    var remaining = c.skillChoices.pick - state.classSkills.length;
    $('skill-choices-remaining').textContent = remaining > 0
      ? remaining + ' choice' + (remaining > 1 ? 's' : '') + ' remaining'
      : 'All skills chosen!';
  }

  // ================================================================
  //  STEP 4: BACKGROUND
  // ================================================================
  function renderBackgroundGrid() {
    var grid = $('background-grid');
    var html = '';
    Object.keys(D.BACKGROUNDS).forEach(function (key) {
      var bg = D.BACKGROUNDS[key];
      var selected = state.background === key ? ' selected' : '';
      html += '<div class="card selectable accent-gold' + selected + '" data-key="' + key + '">' +
        '<div class="card-title">' + bg.name + '</div>' +
        '<div class="card-subtitle">' + bg.skillProficiencies.join(', ') + '</div>' +
        '<p class="card-summary">' + bg.description + '</p>' +
        '</div>';
    });
    grid.innerHTML = html;

    grid.querySelectorAll('.card.selectable').forEach(function (card) {
      card.addEventListener('click', function () { selectBackground(this.getAttribute('data-key')); });
    });

    if (state.background) {
      renderBackgroundDetails();
      renderPersonality();
    }
  }

  function selectBackground(key) {
    var prev = state.background;
    state.background = key;
    if (prev !== key) {
      state.personalityTrait = 0;
      state.ideal = 0;
      state.bond = 0;
      state.flaw = 0;
    }
    $('background-grid').querySelectorAll('.card.selectable').forEach(function (card) {
      card.classList.toggle('selected', card.getAttribute('data-key') === key);
    });
    renderBackgroundDetails();
    renderPersonality();
    // Re-render class skills if we already have a class selected (locked skills may change)
    if (state.cls) renderSkillChoices();
    saveState();
  }

  function renderBackgroundDetails() {
    var container = $('background-details');
    if (!state.background) { container.innerHTML = ''; container.style.display = 'none'; return; }
    var bg = D.BACKGROUNDS[state.background];

    var html = '<div class="card accent-gold">';
    html += '<h3 style="font-family:Cinzel,serif;color:var(--gold);margin-bottom:12px">' + bg.name + '</h3>';
    html += '<div class="cards-grid cols-2" style="margin-bottom:16px">';
    html += '<div><strong>Skills:</strong> ' + bg.skillProficiencies.join(', ') + '</div>';
    if (bg.toolProficiencies.length) html += '<div><strong>Tools:</strong> ' + bg.toolProficiencies.join(', ') + '</div>';
    if (bg.languages) html += '<div><strong>Languages:</strong> ' + bg.languages + ' of your choice</div>';
    html += '</div>';
    html += '<h4 style="color:var(--text-bright);margin-bottom:6px">' + bg.feature.name + '</h4>';
    html += '<p style="font-size:0.88rem;color:var(--text)">' + bg.feature.description + '</p>';
    html += '<h4 style="color:var(--text-bright);margin:12px 0 6px">Equipment</h4>';
    html += '<p style="font-size:0.85rem;color:var(--text-dim)">' + bg.equipment.join(', ') + '</p>';
    html += '</div>';
    container.innerHTML = html;
    container.style.display = 'block';
  }

  function renderPersonality() {
    var section = $('personality-section');
    if (!state.background) { section.style.display = 'none'; return; }
    section.style.display = 'block';
    var bg = D.BACKGROUNDS[state.background];

    var selects = [
      { id: 'personality-trait', data: bg.personalityTraits, stateKey: 'personalityTrait' },
      { id: 'personality-ideal', data: bg.ideals, stateKey: 'ideal' },
      { id: 'personality-bond', data: bg.bonds, stateKey: 'bond' },
      { id: 'personality-flaw', data: bg.flaws, stateKey: 'flaw' }
    ];

    selects.forEach(function (sel) {
      var el = $(sel.id);
      var html = '';
      sel.data.forEach(function (text, i) {
        var selected = state[sel.stateKey] === i ? ' selected' : '';
        html += '<option value="' + i + '"' + selected + '>' + text + '</option>';
      });
      el.innerHTML = html;
      el.value = state[sel.stateKey];
      // Remove old listeners by cloning
      var newEl = el.cloneNode(true);
      el.parentNode.replaceChild(newEl, el);
      newEl.addEventListener('change', function () {
        state[sel.stateKey] = Number(this.value);
        saveState();
      });
    });
  }

  // ================================================================
  //  STEP 5: ABILITY SCORES
  // ================================================================
  function renderAbilityPanel() {
    renderStandardArray();
    renderPointBuy();
    renderRollGrid();
  }

  function initAbilityTabs() {
    document.querySelectorAll('.ability-tab').forEach(function (tab) {
      if (tab.getAttribute('data-method') === state.abilityMethod) tab.classList.add('active');
      else tab.classList.remove('active');
      tab.addEventListener('click', function () {
        var method = this.getAttribute('data-method');
        state.abilityMethod = method;
        document.querySelectorAll('.ability-tab').forEach(function (t) { t.classList.remove('active'); });
        this.classList.add('active');
        document.querySelectorAll('.ability-method-panel').forEach(function (p) { p.classList.remove('active'); });
        $('method-' + method).classList.add('active');
        saveState();
      });
    });
    // Activate correct panel on load
    document.querySelectorAll('.ability-method-panel').forEach(function (p) { p.classList.remove('active'); });
    $('method-' + state.abilityMethod).classList.add('active');
    document.querySelectorAll('.ability-tab').forEach(function (t) {
      t.classList.toggle('active', t.getAttribute('data-method') === state.abilityMethod);
    });
  }

  // ── Standard Array ──
  function renderStandardArray() {
    var grid = $('standard-array-grid');
    var racial = getRacialBonuses();
    var html = '';
    D.ABILITY_NAMES.forEach(function (a, idx) {
      var assignedVal = state.standardArray[a];
      var totalScore = assignedVal !== undefined ? Number(assignedVal) + (racial[a] || 0) : 0;
      var mod = assignedVal !== undefined ? abilityMod(totalScore) : '';

      html += '<div class="ability-card">' +
        '<div class="ability-card-name">' + a + '</div>' +
        '<div class="ability-card-fullname">' + D.ABILITY_FULL_NAMES[idx] + '</div>' +
        '<div class="ability-score-display">' + (assignedVal !== undefined ? totalScore : '—') + '</div>' +
        '<div class="ability-modifier">' + (mod !== '' ? modStr(mod) : '') + '</div>';

      if (racial[a]) html += '<div class="ability-racial-bonus">+' + racial[a] + ' racial</div>';

      // Dropdown
      html += '<select data-ability="' + a + '">';
      html += '<option value="">—</option>';
      D.STANDARD_ARRAY.forEach(function (val) {
        // Show option if it's the current assignment OR not assigned to another ability
        var usedBy = null;
        D.ABILITY_NAMES.forEach(function (other) {
          if (other !== a && Number(state.standardArray[other]) === val) usedBy = other;
        });
        var disabled = usedBy ? ' disabled' : '';
        var selected = Number(assignedVal) === val ? ' selected' : '';
        html += '<option value="' + val + '"' + disabled + selected + '>' + val + (usedBy ? ' (' + usedBy + ')' : '') + '</option>';
      });
      html += '</select>';

      html += '</div>';
    });
    grid.innerHTML = html;

    // Bind selects
    grid.querySelectorAll('select').forEach(function (sel) {
      sel.addEventListener('change', function () {
        var ability = this.getAttribute('data-ability');
        if (this.value === '') {
          delete state.standardArray[ability];
        } else {
          state.standardArray[ability] = Number(this.value);
        }
        renderStandardArray();
        saveState();
      });
    });
  }

  // ── Point Buy ──
  function renderPointBuy() {
    var grid = $('point-buy-grid');
    var racial = getRacialBonuses();

    // Calculate remaining points
    var spent = 0;
    D.ABILITY_NAMES.forEach(function (a) {
      spent += D.POINT_BUY_COSTS[state.pointBuy[a]] || 0;
    });
    var remaining = D.POINT_BUY_TOTAL - spent;
    $('point-buy-remaining').textContent = remaining;

    var html = '';
    D.ABILITY_NAMES.forEach(function (a, idx) {
      var base = state.pointBuy[a];
      var total = base + (racial[a] || 0);
      var mod = abilityMod(total);
      var canIncrease = base < 15 && (D.POINT_BUY_COSTS[base + 1] - D.POINT_BUY_COSTS[base]) <= remaining;
      var canDecrease = base > 8;

      html += '<div class="ability-card">' +
        '<div class="ability-card-name">' + a + '</div>' +
        '<div class="ability-card-fullname">' + D.ABILITY_FULL_NAMES[idx] + '</div>' +
        '<div class="ability-score-display">' + total + '</div>' +
        '<div class="ability-modifier">' + modStr(mod) + '</div>';

      if (racial[a]) html += '<div class="ability-racial-bonus">+' + racial[a] + ' racial</div>';

      html += '<div class="point-buy-controls">' +
        '<button class="point-buy-btn" data-ability="' + a + '" data-dir="-1"' + (canDecrease ? '' : ' disabled') + '>−</button>' +
        '<span style="font-family:Cinzel,serif;font-size:1rem;min-width:24px;text-align:center">' + base + '</span>' +
        '<button class="point-buy-btn" data-ability="' + a + '" data-dir="1"' + (canIncrease ? '' : ' disabled') + '>+</button>' +
        '</div>';

      html += '</div>';
    });
    grid.innerHTML = html;

    // Bind buttons
    grid.querySelectorAll('.point-buy-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var ability = this.getAttribute('data-ability');
        var dir = Number(this.getAttribute('data-dir'));
        var current = state.pointBuy[ability];
        var next = current + dir;
        if (next < 8 || next > 15) return;
        // Check points budget
        var costDiff = D.POINT_BUY_COSTS[next] - D.POINT_BUY_COSTS[current];
        var currentSpent = 0;
        D.ABILITY_NAMES.forEach(function (a) { currentSpent += D.POINT_BUY_COSTS[state.pointBuy[a]]; });
        if (currentSpent + costDiff > D.POINT_BUY_TOTAL) return;
        state.pointBuy[ability] = next;
        renderPointBuy();
        saveState();
      });
    });
  }

  // ── Roll (4d6 drop lowest) ──
  function roll4d6DropLowest() {
    var dice = [];
    for (var i = 0; i < 4; i++) dice.push(Math.floor(Math.random() * 6) + 1);
    dice.sort(function (a, b) { return a - b; });
    return dice[1] + dice[2] + dice[3]; // drop lowest
  }

  function renderRollGrid() {
    var grid = $('roll-grid');
    var racial = getRacialBonuses();

    if (state.rollResults.length === 0) {
      grid.innerHTML = '<p style="text-align:center;color:var(--text-dim)">Click the button above to roll your ability scores.</p>';
      return;
    }

    var html = '';
    D.ABILITY_NAMES.forEach(function (a, idx) {
      var assignedIdx = state.rollAssign[a];
      var baseVal = (assignedIdx !== undefined) ? state.rollResults[assignedIdx] : 0;
      var total = baseVal + (racial[a] || 0);
      var mod = assignedIdx !== undefined ? abilityMod(total) : '';

      html += '<div class="ability-card">' +
        '<div class="ability-card-name">' + a + '</div>' +
        '<div class="ability-card-fullname">' + D.ABILITY_FULL_NAMES[idx] + '</div>' +
        '<div class="ability-score-display">' + (assignedIdx !== undefined ? total : '—') + '</div>' +
        '<div class="ability-modifier">' + (mod !== '' ? modStr(mod) : '') + '</div>';

      if (racial[a]) html += '<div class="ability-racial-bonus">+' + racial[a] + ' racial</div>';

      // Dropdown using indices to handle duplicates
      html += '<select data-ability="' + a + '">';
      html += '<option value="">—</option>';
      state.rollResults.forEach(function (val, ri) {
        var usedBy = null;
        D.ABILITY_NAMES.forEach(function (other) {
          if (other !== a && state.rollAssign[other] === ri) usedBy = other;
        });
        var disabled = usedBy ? ' disabled' : '';
        var selected = assignedIdx === ri ? ' selected' : '';
        html += '<option value="' + ri + '"' + disabled + selected + '>' + val + (usedBy ? ' (' + usedBy + ')' : '') + '</option>';
      });
      html += '</select>';

      html += '</div>';
    });
    grid.innerHTML = html;

    // Bind selects
    grid.querySelectorAll('select').forEach(function (sel) {
      sel.addEventListener('change', function () {
        var ability = this.getAttribute('data-ability');
        if (this.value === '') {
          delete state.rollAssign[ability];
        } else {
          state.rollAssign[ability] = Number(this.value);
        }
        renderRollGrid();
        saveState();
      });
    });
  }

  function initRollButton() {
    $('roll-abilities-btn').addEventListener('click', function () {
      state.rollResults = [];
      state.rollAssign = {};
      for (var i = 0; i < 6; i++) state.rollResults.push(roll4d6DropLowest());
      // Sort descending for nice display
      state.rollResults.sort(function (a, b) { return b - a; });

      // Animate
      var cards = $('roll-grid').querySelectorAll('.ability-card');
      cards.forEach(function (card) { card.classList.add('rolling'); });
      setTimeout(function () {
        cards.forEach(function (card) { card.classList.remove('rolling'); });
      }, 600);

      renderRollGrid();
      saveState();
    });
  }

  // ================================================================
  //  STEP 6: EQUIPMENT
  // ================================================================
  function renderEquipment() {
    var container = $('equipment-section');
    if (!state.cls) {
      container.innerHTML = '<p style="text-align:center;color:var(--text-dim)">Choose a class first.</p>';
      return;
    }
    var c = D.CLASSES[state.cls];

    var html = '';

    // Class equipment choices
    if (c.startingEquipment.choices.length) {
      html += '<div class="equipment-category"><h4>Class Equipment Choices</h4>';
      c.startingEquipment.choices.forEach(function (options, i) {
        var chosen = state.equipChoices[i] !== undefined ? state.equipChoices[i] : 0;
        html += '<div class="equipment-choice-group">';
        html += '<div class="choice-label">Choose one</div>';
        options.forEach(function (option, j) {
          var checked = chosen === j ? ' checked' : '';
          html += '<label>' +
            '<input type="radio" name="equip-choice-' + i + '" value="' + j + '"' + checked + '> ' +
            option +
            '</label>';
        });
        html += '</div>';
      });
      html += '</div>';
    }

    // Class fixed equipment
    if (c.startingEquipment.fixed.length) {
      html += '<div class="equipment-category"><h4>Class Starting Gear</h4>';
      c.startingEquipment.fixed.forEach(function (item) {
        html += '<div class="equipment-item">' + item + '</div>';
      });
      html += '</div>';
    }

    // Background equipment
    if (state.background) {
      var bg = D.BACKGROUNDS[state.background];
      html += '<div class="equipment-category"><h4>Background Equipment (' + bg.name + ')</h4>';
      bg.equipment.forEach(function (item) {
        html += '<div class="equipment-item">' + item + '</div>';
      });
      html += '</div>';
    }

    container.innerHTML = html;

    // Set default choices
    if (state.equipChoices.length === 0) {
      c.startingEquipment.choices.forEach(function () { state.equipChoices.push(0); });
    }

    // Bind radio buttons
    container.querySelectorAll('input[type="radio"]').forEach(function (radio) {
      radio.addEventListener('change', function () {
        var name = this.getAttribute('name');
        var idx = Number(name.replace('equip-choice-', ''));
        state.equipChoices[idx] = Number(this.value);
        saveState();
      });
    });
  }

  // ================================================================
  //  STEP 7: CHARACTER SHEET
  // ================================================================
  function renderCharSheet() {
    var sheet = $('char-sheet');
    var scores = getFinalScores();
    var hp = getHP();
    var ac = getAC();
    var speed = getSpeed();
    var raceName = state.race ? D.RACES[state.race].name : '—';
    var subraceName = '';
    if (state.race && D.RACES[state.race].subraces && state.subrace !== null) {
      subraceName = D.RACES[state.race].subraces[state.subrace].name;
    }
    var className = state.cls ? D.CLASSES[state.cls].name : '—';
    var bgName = state.background ? D.BACKGROUNDS[state.background].name : '—';
    var fullRace = subraceName ? subraceName + ' ' + raceName : raceName;

    // Dragonborn ancestry label
    var ancestryLabel = '';
    if (state.race === 'dragonborn' && state.draconicAncestry !== null) {
      var da = D.RACES.dragonborn.draconicAncestry[state.draconicAncestry];
      ancestryLabel = ' (' + da.dragon + ' Dragon)';
    }

    var html = '';

    // Header
    html += '<div class="char-sheet-header">';
    html += '<h2>' + (state.name || 'Unnamed Hero') + '</h2>';
    html += '<div class="char-meta">' + fullRace + ancestryLabel + ' ' + className + ' · Level 1 · ' + bgName + '</div>';
    if (state.concept) html += '<div style="color:var(--text-dim);font-size:0.85rem;margin-top:6px;font-style:italic">' + state.concept + '</div>';
    html += '</div>';

    // Body
    html += '<div class="char-sheet-body">';

    // == Ability Scores (full width) ==
    html += '<div class="char-sheet-section full-width">';
    html += '<h3>Ability Scores</h3>';
    html += '<div class="stat-block-grid">';
    D.ABILITY_NAMES.forEach(function (a) {
      var score = scores[a];
      var mod = abilityMod(score);
      html += '<div class="stat-block-item">' +
        '<div class="stat-block-label">' + a + '</div>' +
        '<div class="stat-block-value">' + score + '</div>' +
        '<div class="stat-block-mod">' + modStr(mod) + '</div>' +
        '</div>';
    });
    html += '</div>';

    // Combat stats
    html += '<div class="combat-stats">';
    html += '<div class="combat-stat"><div class="combat-stat-value">' + hp + '</div><div class="combat-stat-label">Hit Points</div></div>';
    html += '<div class="combat-stat"><div class="combat-stat-value">' + ac + '</div><div class="combat-stat-label">Armor Class</div></div>';
    html += '<div class="combat-stat"><div class="combat-stat-value">' + speed + '</div><div class="combat-stat-label">Speed</div></div>';
    html += '<div class="combat-stat"><div class="combat-stat-value">+' + PROFICIENCY_BONUS + '</div><div class="combat-stat-label">Proficiency</div></div>';
    if (state.cls) {
      html += '<div class="combat-stat"><div class="combat-stat-value">d' + D.CLASSES[state.cls].hitDie + '</div><div class="combat-stat-label">Hit Die</div></div>';
    }
    html += '</div>';
    html += '</div>';

    // == Saving Throws ==
    html += '<div class="char-sheet-section">';
    html += '<h3>Saving Throws</h3>';
    html += '<div class="proficiency-list">';
    if (state.cls) {
      D.CLASSES[state.cls].savingThrows.forEach(function (st) {
        var mod = abilityMod(scores[st]) + PROFICIENCY_BONUS;
        html += '<span class="proficiency-pill saving-throw">' + st + ' ' + modStr(mod) + '</span>';
      });
    }
    html += '</div>';
    html += '</div>';

    // == Skill Proficiencies ==
    html += '<div class="char-sheet-section">';
    html += '<h3>Skill Proficiencies</h3>';
    html += '<div class="proficiency-list">';
    getAllSkillProficiencies().forEach(function (skill) {
      var ability = '';
      D.ALL_SKILLS.forEach(function (s) { if (s.name === skill) ability = s.ability; });
      var mod = abilityMod(scores[ability]) + PROFICIENCY_BONUS;
      html += '<span class="proficiency-pill">' + skill + ' ' + modStr(mod) + '</span>';
    });
    html += '</div>';
    html += '</div>';

    // == Proficiencies (Armor/Weapons/Tools) ==
    html += '<div class="char-sheet-section">';
    html += '<h3>Other Proficiencies</h3>';
    var profs = [];
    if (state.cls) {
      D.CLASSES[state.cls].armorProficiencies.forEach(function (p) { profs.push(p); });
      D.CLASSES[state.cls].weaponProficiencies.forEach(function (p) { profs.push(p); });
      D.CLASSES[state.cls].toolProficiencies.forEach(function (p) { profs.push(p); });
    }
    if (state.background) {
      D.BACKGROUNDS[state.background].toolProficiencies.forEach(function (p) {
        if (profs.indexOf(p) === -1) profs.push(p);
      });
    }
    html += '<div class="proficiency-list">';
    profs.forEach(function (p) { html += '<span class="proficiency-pill">' + p + '</span>'; });
    html += '</div>';
    html += '</div>';

    // == Languages ==
    html += '<div class="char-sheet-section">';
    html += '<h3>Languages</h3>';
    var langs = [];
    if (state.race) {
      D.RACES[state.race].languages.forEach(function (l) { langs.push(l); });
    }
    if (state.background && D.BACKGROUNDS[state.background].languages) {
      for (var li = 0; li < D.BACKGROUNDS[state.background].languages; li++) {
        langs.push('One extra language');
      }
    }
    html += '<div class="proficiency-list">';
    langs.forEach(function (l) { html += '<span class="proficiency-pill">' + l + '</span>'; });
    html += '</div>';
    html += '</div>';

    // == Features & Traits ==
    html += '<div class="char-sheet-section full-width">';
    html += '<h3>Features & Traits</h3>';
    html += '<ul style="padding-left:18px">';
    // Race traits
    if (state.race) {
      var race = D.RACES[state.race];
      race.traits.forEach(function (t) {
        html += '<li style="margin-bottom:4px"><strong>' + t.name + '.</strong> ' + t.description + '</li>';
      });
      // Subrace traits
      if (race.subraces && state.subrace !== null) {
        race.subraces[state.subrace].traits.forEach(function (t) {
          html += '<li style="margin-bottom:4px"><strong>' + t.name + '.</strong> ' + t.description + '</li>';
        });
      }
      // Draconic ancestry
      if (state.race === 'dragonborn' && state.draconicAncestry !== null) {
        var da = D.RACES.dragonborn.draconicAncestry[state.draconicAncestry];
        html += '<li style="margin-bottom:4px"><strong>Breath Weapon (' + da.dragon + ').</strong> ' + da.damageType + ' damage, ' + da.breath + '</li>';
        html += '<li style="margin-bottom:4px"><strong>Damage Resistance.</strong> ' + da.damageType + '</li>';
      }
    }
    // Class features
    if (state.cls) {
      D.CLASSES[state.cls].features.forEach(function (f) {
        html += '<li style="margin-bottom:4px"><strong>' + f.name + '.</strong> ' + f.description + '</li>';
      });
    }
    // Background feature
    if (state.background) {
      var bgFeature = D.BACKGROUNDS[state.background].feature;
      html += '<li style="margin-bottom:4px"><strong>' + bgFeature.name + '.</strong> ' + bgFeature.description + '</li>';
    }
    html += '</ul>';
    html += '</div>';

    // == Spellcasting ==
    if (state.cls && D.CLASSES[state.cls].spellcasting) {
      var sc = D.CLASSES[state.cls].spellcasting;
      html += '<div class="char-sheet-section full-width">';
      html += '<h3>Spellcasting</h3>';
      html += '<div style="font-size:0.88rem;margin-bottom:8px">';
      html += '<strong>Ability:</strong> ' + sc.ability + ' · ';
      html += '<strong>Spell Save DC:</strong> ' + (8 + PROFICIENCY_BONUS + abilityMod(scores[sc.ability])) + ' · ';
      html += '<strong>Spell Attack:</strong> ' + modStr(PROFICIENCY_BONUS + abilityMod(scores[sc.ability]));
      html += '</div>';
      if (sc.cantripsKnown) html += '<div style="font-size:0.85rem;color:var(--text-dim)">Cantrips Known: ' + sc.cantripsKnown + '</div>';
      var totalSlots = getSpellSlotMax();
      if (totalSlots) html += '<div style="font-size:0.85rem;color:var(--text-dim)">1st-Level Spell Slots: ' + totalSlots + '</div>';
      if (sc.note) html += '<div style="font-size:0.82rem;color:var(--text-dim);font-style:italic;margin-top:4px">' + sc.note + '</div>';
      html += '</div>';
    }

    // == Equipment ==
    html += '<div class="char-sheet-section full-width">';
    html += '<h3>Equipment</h3>';
    html += '<ul style="padding-left:18px">';
    getEquipmentList().forEach(function (item) {
      html += '<li style="margin-bottom:3px">' + item + '</li>';
    });
    html += '</ul>';
    html += '</div>';

    // == Personality ==
    if (state.background) {
      var bg = D.BACKGROUNDS[state.background];
      html += '<div class="char-sheet-section full-width">';
      html += '<h3>Personality</h3>';
      html += '<div style="font-size:0.88rem">';
      html += '<p style="margin-bottom:6px"><strong>Trait:</strong> ' + bg.personalityTraits[state.personalityTrait] + '</p>';
      html += '<p style="margin-bottom:6px"><strong>Ideal:</strong> ' + bg.ideals[state.ideal] + '</p>';
      html += '<p style="margin-bottom:6px"><strong>Bond:</strong> ' + bg.bonds[state.bond] + '</p>';
      html += '<p><strong>Flaw:</strong> ' + bg.flaws[state.flaw] + '</p>';
      html += '</div>';
      html += '</div>';
    }

    html += '</div>'; // close char-sheet-body
    sheet.innerHTML = html;
  }

  // ================================================================
  //  COPY FOR DM (Vault Template Format)
  // ================================================================
  function copyForDM() {
    var scores = getFinalScores();
    var hp = getHP();
    var ac = getAC();
    var name = state.name || 'Unnamed Hero';
    var raceName = state.race ? D.RACES[state.race].name : '';
    var subraceName = '';
    if (state.race && D.RACES[state.race].subraces && state.subrace !== null) {
      subraceName = D.RACES[state.race].subraces[state.subrace].name;
    }
    var fullRace = subraceName ? subraceName + ' ' + raceName : raceName;
    var className = state.cls ? D.CLASSES[state.cls].name : '';
    var spellSlotMax = getSpellSlotMax();
    var layOnHands = getLayOnHands();

    // Build features list
    var features = [];
    if (state.race) {
      D.RACES[state.race].traits.forEach(function (t) { features.push(t.name); });
      if (D.RACES[state.race].subraces && state.subrace !== null) {
        D.RACES[state.race].subraces[state.subrace].traits.forEach(function (t) { features.push(t.name); });
      }
    }
    if (state.cls) {
      D.CLASSES[state.cls].features.forEach(function (f) { features.push(f.name); });
    }
    if (state.background) {
      features.push(D.BACKGROUNDS[state.background].feature.name);
    }

    var text = '---\n';
    text += 'type: party_member\n';
    text += 'name: "' + name + '"\n';
    text += 'player: ""\n';
    text += 'race: "' + fullRace + '"\n';
    text += 'class: "' + className + '"\n';
    text += 'level: 1\n';
    text += 'hp_current: ' + hp + '\n';
    text += 'hp_max: ' + hp + '\n';
    text += 'ac: ' + ac + '\n';
    text += 'conditions: []\n';
    text += 'spell_slots_used: 0\n';
    text += 'spell_slots_max: ' + spellSlotMax + '\n';
    text += 'lay_on_hands_pool: ' + layOnHands + '\n';
    text += 'tags: [party]\n';
    text += '---\n';
    text += '# ' + name + '\n\n';

    // Stats
    text += '## Stats\n';
    text += '| Stat | Score | Mod |\n';
    text += '|------|-------|-----|\n';
    D.ABILITY_NAMES.forEach(function (a) {
      var score = scores[a];
      var mod = abilityMod(score);
      text += '| ' + a + '  | ' + score + '    | ' + modStr(mod) + '  |\n';
    });
    text += '\n';

    // Features
    text += '## Abilities & Features\n';
    features.forEach(function (f) { text += '- ' + f + '\n'; });
    text += '\n';

    // Spells
    text += '## Prepared Spells\n';
    if (state.cls && D.CLASSES[state.cls].spellcasting && D.CLASSES[state.cls].spellcasting.spellList.length) {
      text += '- _(Choose from: ' + D.CLASSES[state.cls].spellcasting.spellList.join(', ') + ')_\n';
    } else {
      text += '- _(none)_\n';
    }
    text += '\n';

    // Inventory
    text += '## Inventory\n';
    getEquipmentList().forEach(function (item) { text += '- ' + item + '\n'; });
    text += '\n';

    // Personality
    text += '## Personality\n';
    if (state.background) {
      var bg = D.BACKGROUNDS[state.background];
      text += '_**Trait:** ' + bg.personalityTraits[state.personalityTrait] + '_\n';
      text += '_**Ideal:** ' + bg.ideals[state.ideal] + '_\n';
      text += '_**Bond:** ' + bg.bonds[state.bond] + '_\n';
      text += '_**Flaw:** ' + bg.flaws[state.flaw] + '_\n';
    } else {
      text += '_Roleplaying notes, quirks, motivations._\n';
    }
    text += '\n';

    // Bonds & Hooks
    text += '## Bonds & Hooks\n';
    if (state.concept) text += '- ' + state.concept + '\n';
    text += '_Story threads tied to this character._\n\n';

    // Session Notes
    text += '## Session Notes\n';
    text += '_Running notes on this character\'s arc._\n';

    return text;
  }

  // ================================================================
  //  TOAST NOTIFICATION
  // ================================================================
  function showToast(message) {
    var toast = $('toast');
    toast.textContent = message || 'Copied to clipboard!';
    toast.classList.add('show');
    setTimeout(function () { toast.classList.remove('show'); }, 2500);
  }

  // ================================================================
  //  LOCAL STORAGE
  // ================================================================
  var STORAGE_KEY = 'dnd-wizard-state';

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) { /* quota exceeded or private mode */ }
  }

  function loadState() {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        var parsed = JSON.parse(saved);
        Object.keys(parsed).forEach(function (k) {
          if (state.hasOwnProperty(k)) state[k] = parsed[k];
        });
      }
    } catch (e) { /* corrupted data */ }
  }

  // ================================================================
  //  INIT
  // ================================================================
  function init() {
    loadState();

    // Name step
    initNameStep();

    // Ability tabs
    initAbilityTabs();

    // Roll button
    initRollButton();

    // Navigation buttons
    $('prev-btn').addEventListener('click', function () {
      if (state.step > 1) goToStep(state.step - 1);
    });
    $('next-btn').addEventListener('click', function () {
      if (!canAdvance()) {
        // Provide feedback about what's missing
        var msg = '';
        if (state.step === 2 && !state.race) msg = 'Please select a race.';
        else if (state.step === 2 && state.race === 'dragonborn' && state.draconicAncestry === null) msg = 'Please choose a draconic ancestry.';
        else if (state.step === 2 && state.race) {
          var r = D.RACES[state.race];
          if (r.subraces && r.subraces.length > 0 && state.subrace === null) msg = 'Please choose a subrace.';
          if (state.race === 'half-elf' && state.halfElfBonuses.length < r.abilityBonusChoice.count) msg = 'Please choose ' + r.abilityBonusChoice.count + ' ability bonuses.';
        }
        else if (state.step === 3 && !state.cls) msg = 'Please select a class.';
        else if (state.step === 3 && state.cls) msg = 'Please choose all your class skills.';
        else if (state.step === 4) msg = 'Please select a background.';
        else if (state.step === 5) {
          if (state.abilityMethod === 'standard-array') msg = 'Please assign all 6 ability scores.';
          else if (state.abilityMethod === 'roll') msg = 'Please roll and assign all ability scores.';
        }
        if (msg) showToast(msg);
        return;
      }
      goToStep(state.step + 1);
    });

    // Copy and Print buttons
    $('copy-btn').addEventListener('click', function () {
      var text = copyForDM();
      navigator.clipboard.writeText(text).then(function () {
        showToast('Copied to clipboard!');
        var btn = $('copy-btn');
        btn.classList.add('copied');
        btn.textContent = 'Copied!';
        setTimeout(function () {
          btn.classList.remove('copied');
          btn.textContent = 'Copy for DM';
        }, 2000);
      }).catch(function () {
        showToast('Copy failed — try selecting manually');
      });
    });

    $('print-btn').addEventListener('click', function () {
      window.print();
    });

    // Render initial state
    renderProgress();
    updateNameGenerator();

    // If we have a saved step, go to it
    if (state.step > 1) {
      // First hide step 1 (which is active in HTML)
      $('step-1').classList.remove('active');
      $('step-' + state.step).classList.add('active');

      // Render the current step
      if (state.step === 2) renderRaceGrid();
      if (state.step === 3) renderClassGrid();
      if (state.step === 4) renderBackgroundGrid();
      if (state.step === 5) renderAbilityPanel();
      if (state.step === 6) renderEquipment();
      if (state.step === 7) renderCharSheet();

      // Update nav buttons
      $('prev-btn').disabled = (state.step === 1);
      if (state.step === STEPS) $('next-btn').style.display = 'none';
    }

    // Restore name input values
    $('char-name').value = state.name;
    $('char-concept').value = state.concept;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
