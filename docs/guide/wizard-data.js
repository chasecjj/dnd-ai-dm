/* ================================================================
   Character Creation Wizard — D&D 5e PHB Level 1 Data
   All data needed for the 7-step character builder.
   Loaded via <script> tag — no modules.
   ================================================================ */

window.WIZARD_DATA = {

  // ── Constants ──────────────────────────────────────────────────
  STANDARD_ARRAY: [15, 14, 13, 12, 10, 8],
  POINT_BUY_COSTS: { 8:0, 9:1, 10:2, 11:3, 12:4, 13:5, 14:7, 15:9 },
  POINT_BUY_TOTAL: 27,
  ABILITY_NAMES: ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
  ABILITY_FULL_NAMES: ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"],

  // ── Races ──────────────────────────────────────────────────────
  RACES: {
    human: {
      name: "Human",
      description: "The most widespread race in the realms, driven by endless ambition and remarkable adaptability.",
      abilityBonuses: { STR: 1, DEX: 1, CON: 1, INT: 1, WIS: 1, CHA: 1 },
      speed: 30, size: "Medium", darkvision: 0,
      languages: ["Common", "One extra language of your choice"],
      traits: [
        { name: "Ability Score Increase", description: "+1 to all six ability scores." },
        { name: "Extra Language", description: "You can speak, read, and write one extra language of your choice." },
        { name: "Versatile", description: "Humans excel in any class thanks to their balanced stats." }
      ],
      skillProficiencies: [],
      nameTable: {
        male: ["Aldric","Bran","Cedric","Darvin","Edmund","Fenton","Gareth","Hadrian","Ivan","Jasper","Kendric","Leander","Marcus","Nolan","Orion","Preston","Quinn","Roland","Silas","Theron","Urien","Victor","Wesley","Alaric","Dorian","Everett","Florian","Godwin"],
        female: ["Adara","Brianna","Celeste","Diana","Elena","Fiona","Gwendolyn","Helena","Iris","Jasmine","Katarina","Lydia","Miranda","Nadia","Ophelia","Petra","Rosalind","Seraphina","Theresa","Ursula","Vivian","Willa","Yara","Arabella","Cordelia","Elara","Isolde","Rowena"],
        surname: ["Ashford","Blackwood","Cromwell","Dunbar","Elsworth","Fairfax","Gallagher","Hartwell","Ironside","Kingsley","Lancaster","Mercer","Northwind","Oakhart","Pemberton","Ravencroft","Stirling","Thornwall","Whitmore","Blackthorn"]
      },
      accentColor: "gold", iconId: "icon-race-human"
    },

    elf: {
      name: "Elf",
      description: "Long-lived beings of otherworldly grace, attuned to magic and the beauty of the natural world.",
      abilityBonuses: { DEX: 2 },
      speed: 30, size: "Medium", darkvision: 60,
      languages: ["Common", "Elvish"],
      traits: [
        { name: "Darkvision", description: "You can see in dim light within 60 feet as if it were bright light." },
        { name: "Keen Senses", description: "You have proficiency in the Perception skill." },
        { name: "Fey Ancestry", description: "You have advantage on saving throws against being charmed, and magic can't put you to sleep." },
        { name: "Trance", description: "You don't need to sleep. Instead, you meditate for 4 hours a day." }
      ],
      skillProficiencies: ["Perception"],
      subraces: [
        { name: "High Elf", abilityBonuses: { INT: 1 }, traits: [{ name: "Cantrip", description: "You know one wizard cantrip of your choice." }] },
        { name: "Wood Elf", abilityBonuses: { WIS: 1 }, traits: [{ name: "Fleet of Foot", description: "Your base walking speed increases to 35 feet." }, { name: "Mask of the Wild", description: "You can attempt to hide when lightly obscured by natural phenomena." }] }
      ],
      nameTable: {
        male: ["Adran","Aelar","Aramil","Arannis","Aust","Beiro","Berrian","Carric","Enialis","Erdan","Erevan","Galinndan","Hadarai","Heian","Himo","Immeral","Ivellios","Laucian","Mindartis","Paelias","Peren","Quarion","Riardon","Rolen","Soveliss","Thamior","Theren","Varis"],
        female: ["Adrie","Althaea","Anastrianna","Andraste","Antinua","Bethrynna","Birel","Caelynn","Dara","Drusilia","Enna","Felosial","Ielenia","Jelenneth","Keyleth","Leshanna","Lia","Meriele","Mialee","Naivara","Quelenna","Quillathe","Sariel","Shanairra","Shava","Silaqui","Thia","Valanthe","Xanaphia"],
        surname: ["Amakiir","Amastacia","Galanodel","Holimion","Ilphelkiir","Liadon","Meliamne","Nailo","Siannodel","Xiloscient"]
      },
      accentColor: "teal", iconId: "icon-race-elf"
    },

    dwarf: {
      name: "Dwarf",
      description: "Hardy folk forged in mountain halls, renowned for their craftsmanship and unyielding resolve.",
      abilityBonuses: { CON: 2 },
      speed: 25, size: "Medium", darkvision: 60,
      languages: ["Common", "Dwarvish"],
      traits: [
        { name: "Darkvision", description: "You can see in dim light within 60 feet as if it were bright light." },
        { name: "Dwarven Resilience", description: "You have advantage on saving throws against poison, and resistance against poison damage." },
        { name: "Stonecunning", description: "Whenever you make a History check related to stonework, add double your proficiency bonus." },
        { name: "Tool Proficiency", description: "You gain proficiency with smith's tools, brewer's supplies, or mason's tools." }
      ],
      skillProficiencies: [],
      subraces: [
        { name: "Hill Dwarf", abilityBonuses: { WIS: 1 }, traits: [{ name: "Dwarven Toughness", description: "Your hit point maximum increases by 1, and by 1 again every time you gain a level." }] },
        { name: "Mountain Dwarf", abilityBonuses: { STR: 2 }, traits: [{ name: "Dwarven Armor Training", description: "You have proficiency with light and medium armor." }] }
      ],
      nameTable: {
        male: ["Adrik","Alberich","Baern","Barendd","Brottor","Bruenor","Dain","Darrak","Delg","Eberk","Einkil","Fargrim","Flint","Gardain","Harbek","Kildrak","Morgran","Orsik","Oskar","Rangrim","Rurik","Taklinn","Thoradin","Thorin","Tordek","Traubon","Travok","Ulfgar","Vondal"],
        female: ["Amber","Artin","Audhild","Bardryn","Dagnal","Diesa","Eldeth","Falkrunn","Finellen","Gunnloda","Gurdis","Helja","Hlin","Kathra","Kristryd","Ilde","Liftrasa","Mardred","Riswynn","Sannl","Torbera","Torgga","Vistra"],
        surname: ["Balderk","Battlehammer","Brawnanvil","Dankil","Fireforge","Frostbeard","Gorunn","Holderhek","Ironfist","Loderr","Lutgehr","Rumnaheim","Strakeln","Torunn","Ungart"]
      },
      accentColor: "orange", iconId: "icon-race-dwarf"
    },

    halfling: {
      name: "Halfling",
      description: "Cheerful wanderers whose uncanny luck and steady nerve carry them through dangers far larger than themselves.",
      abilityBonuses: { DEX: 2 },
      speed: 25, size: "Small", darkvision: 0,
      languages: ["Common", "Halfling"],
      traits: [
        { name: "Lucky", description: "When you roll a 1 on a d20 for an attack roll, ability check, or saving throw, you can reroll and must use the new roll." },
        { name: "Brave", description: "You have advantage on saving throws against being frightened." },
        { name: "Halfling Nimbleness", description: "You can move through the space of any creature that is of a size larger than yours." }
      ],
      skillProficiencies: [],
      subraces: [
        { name: "Lightfoot", abilityBonuses: { CHA: 1 }, traits: [{ name: "Naturally Stealthy", description: "You can attempt to hide even when obscured only by a creature one size larger than you." }] },
        { name: "Stout", abilityBonuses: { CON: 1 }, traits: [{ name: "Stout Resilience", description: "You have advantage on saving throws against poison, and resistance against poison damage." }] }
      ],
      nameTable: {
        male: ["Alton","Ander","Cade","Corrin","Eldon","Errich","Finnan","Garret","Lindal","Lyle","Merric","Milo","Osborn","Perrin","Reed","Roscoe","Wellby","Wendel","Gorbo","Dannad"],
        female: ["Andry","Bree","Callie","Cora","Euphemia","Jillian","Kithri","Lavinia","Lidda","Merla","Nedda","Paela","Portia","Seraphina","Shaena","Trym","Vani","Verna","Wella","Yondalla"],
        surname: ["Brushgather","Goodbarrel","Greenbottle","High-hill","Hilltopple","Leagallow","Tealeaf","Thorngage","Tosscobble","Underbough"]
      },
      accentColor: "green", iconId: "icon-race-halfling"
    },

    gnome: {
      name: "Gnome",
      description: "Tiny tinkerers and illusionists brimming with energy, curiosity, and an innate resistance to magic.",
      abilityBonuses: { INT: 2 },
      speed: 25, size: "Small", darkvision: 60,
      languages: ["Common", "Gnomish"],
      traits: [
        { name: "Darkvision", description: "You can see in dim light within 60 feet as if it were bright light." },
        { name: "Gnome Cunning", description: "You have advantage on Intelligence, Wisdom, and Charisma saving throws against magic." }
      ],
      skillProficiencies: [],
      subraces: [
        { name: "Forest Gnome", abilityBonuses: { DEX: 1 }, traits: [{ name: "Natural Illusionist", description: "You know the minor illusion cantrip." }, { name: "Speak with Small Beasts", description: "You can communicate simple ideas with Small or smaller beasts." }] },
        { name: "Rock Gnome", abilityBonuses: { CON: 1 }, traits: [{ name: "Artificer's Lore", description: "Double proficiency bonus on History checks related to magic items or technological devices." }, { name: "Tinker", description: "You can craft tiny clockwork devices." }] }
      ],
      nameTable: {
        male: ["Alston","Alvyn","Boddynock","Brocc","Burgell","Dimble","Eldon","Erky","Fonkin","Frug","Gerbo","Gimble","Glim","Jebeddo","Kellen","Namfoodle","Orryn","Roondar","Seebo","Sindri","Warryn","Wrenn","Zook"],
        female: ["Bimpnottin","Breena","Caramip","Carlin","Donella","Duvamil","Ella","Ellyjobell","Ellywick","Lilli","Loopmottin","Lorilla","Mardnab","Nissa","Nyx","Oda","Orla","Roywyn","Shamil","Tana","Waywocket","Zanna"],
        surname: ["Beren","Daergel","Folkor","Garrick","Nackle","Murnig","Ningel","Raulnor","Scheppen","Timbers","Turen"]
      },
      accentColor: "purple", iconId: "icon-race-gnome"
    },

    "half-elf": {
      name: "Half-Elf",
      description: "Diplomatic and versatile, half-elves walk between cultures and excel wherever their talents take them.",
      abilityBonuses: { CHA: 2 },
      abilityBonusChoice: { count: 2, amount: 1, exclude: ["CHA"] },
      speed: 30, size: "Medium", darkvision: 60,
      languages: ["Common", "Elvish", "One extra language of your choice"],
      traits: [
        { name: "Darkvision", description: "You can see in dim light within 60 feet as if it were bright light." },
        { name: "Fey Ancestry", description: "You have advantage on saving throws against being charmed, and magic can't put you to sleep." },
        { name: "Skill Versatility", description: "You gain proficiency in two skills of your choice." }
      ],
      skillProficiencies: [],
      skillBonusChoices: 2,
      nameTable: {
        male: ["Adran","Aelar","Beiro","Carric","Darian","Erdan","Galinndan","Heian","Kael","Laucian","Mindartis","Riardon","Soveliss","Theren","Varis","Aldric","Bran","Darvin","Edmund","Gareth","Ivan","Marcus","Nolan","Roland","Silas"],
        female: ["Adrie","Birel","Caelynn","Dara","Enna","Ielenia","Keyleth","Lia","Meriele","Naivara","Sariel","Shava","Thia","Valanthe","Xanaphia","Adara","Brianna","Elena","Fiona","Helena","Lydia","Miranda","Seraphina","Vivian"],
        surname: ["Amakiir","Galanodel","Liadon","Siannodel","Ashford","Blackwood","Cromwell","Fairfax","Hartwell","Oakhart"]
      },
      accentColor: "teal", iconId: "icon-race-halfelf"
    },

    "half-orc": {
      name: "Half-Orc",
      description: "Fierce and imposing, half-orcs channel their orcish heritage with determination and tenacity.",
      abilityBonuses: { STR: 2, CON: 1 },
      speed: 30, size: "Medium", darkvision: 60,
      languages: ["Common", "Orc"],
      traits: [
        { name: "Darkvision", description: "You can see in dim light within 60 feet as if it were bright light." },
        { name: "Relentless Endurance", description: "When you are reduced to 0 hit points but not outright defeated, you can drop to 1 hit point instead. Once per long rest." },
        { name: "Savage Attacks", description: "When you score a critical hit with a melee weapon, you can roll one of the weapon's damage dice one additional time." },
        { name: "Menacing", description: "You gain proficiency in the Intimidation skill." }
      ],
      skillProficiencies: ["Intimidation"],
      nameTable: {
        male: ["Dench","Feng","Gell","Henk","Holg","Imsh","Keth","Krusk","Mhurren","Ront","Shump","Thokk","Brug","Durth","Grumbar","Harg","Lurtz","Mog","Ogg","Rendar","Skarr","Tusk","Vrag","Zug"],
        female: ["Baggi","Emen","Engong","Kansif","Myev","Neega","Ovak","Ownka","Shautha","Sutha","Vola","Yevelda","Droga","Grisha","Harsk","Kulva","Mogra","Rutha","Togra","Ushka"],
        surname: ["Bonecrusher","Doomhammer","Frostmane","Ironhide","Skullsplitter","Thunderfist","Warsong","Bloodfist","Grimjaw","Stormrage"]
      },
      accentColor: "red", iconId: "icon-race-halforc"
    },

    tiefling: {
      name: "Tiefling",
      description: "Descendants of an ancient pact, tieflings bear horns, tails, and innate magical power as marks of their bloodline.",
      abilityBonuses: { CHA: 2, INT: 1 },
      speed: 30, size: "Medium", darkvision: 60,
      languages: ["Common", "Infernal"],
      traits: [
        { name: "Darkvision", description: "You can see in dim light within 60 feet as if it were bright light." },
        { name: "Hellish Resistance", description: "You have resistance to fire damage." },
        { name: "Infernal Legacy", description: "You know the thaumaturgy cantrip. At 3rd level, you can cast hellish rebuke once per long rest. At 5th level, you can cast darkness once per long rest. Charisma is your spellcasting ability." }
      ],
      skillProficiencies: [],
      nameTable: {
        male: ["Akmenos","Amnon","Barakas","Damakos","Ekemon","Iados","Kairon","Leucis","Melech","Mordai","Morthos","Pelaios","Skamos","Therai","Zariel","Aeson","Crixus","Dematos","Erevan","Kyrus","Malvius","Nixor","Ravos","Vesper"],
        female: ["Akta","Anakis","Bryseis","Criella","Damaia","Ea","Kallista","Lerissa","Makaria","Nemeia","Orianna","Phelaia","Rieta","Brielle","Davina","Esmeray","Hela","Lilith","Nyx","Raven","Serafina","Valeria","Zarya"],
        surname: ["Ashcrown","Blackthorn","Darkmore","Hellsong","Nightshade","Shadowmere","Soulfire","Thornheart","Grimsong","Flareheart"]
      },
      accentColor: "red", iconId: "icon-race-tiefling"
    },

    dragonborn: {
      name: "Dragonborn",
      description: "Noble beings of draconic ancestry who breathe elemental energy and resist it in equal measure.",
      abilityBonuses: { STR: 2, CHA: 1 },
      speed: 30, size: "Medium", darkvision: 0,
      languages: ["Common", "Draconic"],
      traits: [
        { name: "Breath Weapon", description: "You can use your action to exhale destructive energy. The damage type and area depend on your draconic ancestry." },
        { name: "Damage Resistance", description: "You have resistance to the damage type associated with your draconic ancestry." }
      ],
      skillProficiencies: [],
      draconicAncestry: [
        { dragon: "Black",   damageType: "Acid",      breath: "5x30 ft. line (DEX save)" },
        { dragon: "Blue",    damageType: "Lightning",  breath: "5x30 ft. line (DEX save)" },
        { dragon: "Brass",   damageType: "Fire",       breath: "5x30 ft. line (DEX save)" },
        { dragon: "Bronze",  damageType: "Lightning",  breath: "5x30 ft. line (DEX save)" },
        { dragon: "Copper",  damageType: "Acid",       breath: "5x30 ft. line (DEX save)" },
        { dragon: "Gold",    damageType: "Fire",       breath: "15 ft. cone (DEX save)" },
        { dragon: "Green",   damageType: "Poison",     breath: "15 ft. cone (CON save)" },
        { dragon: "Red",     damageType: "Fire",       breath: "15 ft. cone (DEX save)" },
        { dragon: "Silver",  damageType: "Cold",       breath: "15 ft. cone (CON save)" },
        { dragon: "White",   damageType: "Cold",       breath: "15 ft. cone (CON save)" }
      ],
      nameTable: {
        male: ["Arjhan","Balasar","Bharash","Donaar","Ghesh","Heskan","Kriv","Medrash","Mehen","Nadarr","Pandjed","Patrin","Rhogar","Shamash","Shedinn","Tarhun","Torinn","Balazar","Drakon","Gorath","Korinn","Razaan","Suresh","Vorthas"],
        female: ["Akra","Biri","Daar","Farideh","Harann","Havilar","Jheri","Kava","Korinn","Mishann","Nala","Perra","Raiann","Sora","Surina","Thava","Uadjit","Anari","Drakka","Essendra","Kalira","Merys","Nyssara","Vyara"],
        surname: ["Clethtinthiallor","Daardendrian","Delmirev","Drachedandion","Fenkenkabradon","Kepeshkmolik","Kerrhylon","Kimbatuul","Linxakasendalor","Myastan","Nemmonis","Norixius","Ophinshtalajiir","Prexijandilin","Shestendeliath","Turnuroth","Verthisathurgiesh","Yarjerit"]
      },
      accentColor: "orange", iconId: "icon-race-dragonborn"
    }
  },

  // ── Classes ────────────────────────────────────────────────────
  CLASSES: {
    barbarian: {
      name: "Barbarian",
      description: "Fierce warriors who channel primal rage to shrug off damage and overpower foes.",
      hitDie: 12,
      primaryAbility: "Strength",
      savingThrows: ["STR", "CON"],
      armorProficiencies: ["Light armor", "Medium armor", "Shields"],
      weaponProficiencies: ["Simple weapons", "Martial weapons"],
      toolProficiencies: [],
      skillChoices: { pick: 2, from: ["Animal Handling", "Athletics", "Intimidation", "Nature", "Perception", "Survival"] },
      startingEquipment: {
        choices: [
          ["A greataxe", "Any martial melee weapon"],
          ["Two handaxes", "Any simple weapon"]
        ],
        fixed: ["Explorer's pack", "Four javelins"]
      },
      features: [
        { name: "Rage", description: "In battle, you can enter a rage as a bonus action. While raging, you gain advantage on STR checks and saves, bonus melee damage, and resistance to bludgeoning, piercing, and slashing damage. 2 rages per long rest at level 1." },
        { name: "Unarmored Defense", description: "While not wearing armor, your AC equals 10 + DEX modifier + CON modifier." }
      ],
      spellcasting: null,
      accentColor: "red", iconId: "icon-class-barbarian"
    },

    bard: {
      name: "Bard",
      description: "Charismatic performers who weave magic through music, bolstering allies and beguiling enemies.",
      hitDie: 8,
      primaryAbility: "Charisma",
      savingThrows: ["DEX", "CHA"],
      armorProficiencies: ["Light armor"],
      weaponProficiencies: ["Simple weapons", "Hand crossbows", "Longswords", "Rapiers", "Shortswords"],
      toolProficiencies: ["Three musical instruments of your choice"],
      skillChoices: { pick: 3, from: ["Acrobatics","Animal Handling","Arcana","Athletics","Deception","History","Insight","Intimidation","Investigation","Medicine","Nature","Perception","Performance","Persuasion","Religion","Sleight of Hand","Stealth","Survival"] },
      startingEquipment: {
        choices: [
          ["A rapier", "A longsword", "Any simple weapon"],
          ["A diplomat's pack", "An entertainer's pack"]
        ],
        fixed: ["Leather armor", "Dagger", "A musical instrument"]
      },
      features: [
        { name: "Bardic Inspiration", description: "You can inspire others with your performance. As a bonus action, give one creature within 60 feet a d6 Bardic Inspiration die. CHA modifier times per long rest." },
        { name: "Spellcasting", description: "You have learned to weave magic through music and oration. Charisma is your spellcasting ability." }
      ],
      spellcasting: {
        ability: "CHA", cantripsKnown: 2, spellsKnown: 4, prepared: false,
        spellSlots: { 1: 2 },
        spellList: ["Charm Person","Cure Wounds","Detect Magic","Disguise Self","Faerie Fire","Healing Word","Heroism","Silent Image","Sleep","Speak with Animals","Thunderwave","Dissonant Whispers","Feather Fall","Identify"]
      },
      accentColor: "purple", iconId: "icon-class-bard"
    },

    cleric: {
      name: "Cleric",
      description: "Holy conduits who heal the wounded, protect the faithful, and channel divine power.",
      hitDie: 8,
      primaryAbility: "Wisdom",
      savingThrows: ["WIS", "CHA"],
      armorProficiencies: ["Light armor", "Medium armor", "Shields"],
      weaponProficiencies: ["Simple weapons"],
      toolProficiencies: [],
      skillChoices: { pick: 2, from: ["History", "Insight", "Medicine", "Persuasion", "Religion"] },
      startingEquipment: {
        choices: [
          ["A mace", "A warhammer (if proficient)"],
          ["Scale mail", "Leather armor", "Chain mail (if proficient)"],
          ["A light crossbow and 20 bolts", "Any simple weapon"],
          ["A priest's pack", "An explorer's pack"]
        ],
        fixed: ["A shield", "A holy symbol"]
      },
      features: [
        { name: "Spellcasting", description: "As a conduit for divine power, you can cast cleric spells. Wisdom is your spellcasting ability." },
        { name: "Divine Domain", description: "Choose a domain related to your deity: Knowledge, Life, Light, Nature, Tempest, Trickery, or War. Each grants bonus spells and features." }
      ],
      spellcasting: {
        ability: "WIS", cantripsKnown: 3, spellsKnown: null, prepared: true,
        spellSlots: { 1: 2 },
        spellList: ["Bless","Command","Cure Wounds","Detect Magic","Guiding Bolt","Healing Word","Inflict Wounds","Protection from Evil and Good","Sanctuary","Shield of Faith"]
      },
      accentColor: "gold", iconId: "icon-class-cleric"
    },

    druid: {
      name: "Druid",
      description: "Guardians of the wild who command the elements and can take the forms of beasts.",
      hitDie: 8,
      primaryAbility: "Wisdom",
      savingThrows: ["INT", "WIS"],
      armorProficiencies: ["Light armor", "Medium armor", "Shields (druids will not wear metal armor or shields)"],
      weaponProficiencies: ["Clubs", "Daggers", "Darts", "Javelins", "Maces", "Quarterstaffs", "Scimitars", "Sickles", "Slings", "Spears"],
      toolProficiencies: ["Herbalism kit"],
      skillChoices: { pick: 2, from: ["Arcana", "Animal Handling", "Insight", "Medicine", "Nature", "Perception", "Religion", "Survival"] },
      startingEquipment: {
        choices: [
          ["A wooden shield", "Any simple weapon"],
          ["A scimitar", "Any simple melee weapon"]
        ],
        fixed: ["Leather armor", "An explorer's pack", "A druidic focus"]
      },
      features: [
        { name: "Druidic", description: "You know Druidic, the secret language of druids." },
        { name: "Spellcasting", description: "Drawing on the divine essence of nature, you can cast spells. Wisdom is your spellcasting ability." }
      ],
      spellcasting: {
        ability: "WIS", cantripsKnown: 2, spellsKnown: null, prepared: true,
        spellSlots: { 1: 2 },
        spellList: ["Cure Wounds","Detect Magic","Entangle","Faerie Fire","Fog Cloud","Goodberry","Healing Word","Speak with Animals","Thunderwave","Animal Friendship"]
      },
      accentColor: "green", iconId: "icon-class-druid"
    },

    fighter: {
      name: "Fighter",
      description: "Versatile warriors who excel with every weapon and armor, mastering many combat techniques.",
      hitDie: 10,
      primaryAbility: "Strength or Dexterity",
      savingThrows: ["STR", "CON"],
      armorProficiencies: ["All armor", "Shields"],
      weaponProficiencies: ["Simple weapons", "Martial weapons"],
      toolProficiencies: [],
      skillChoices: { pick: 2, from: ["Acrobatics", "Animal Handling", "Athletics", "History", "Insight", "Intimidation", "Perception", "Survival"] },
      startingEquipment: {
        choices: [
          ["Chain mail", "Leather armor, longbow, and 20 arrows"],
          ["A martial weapon and a shield", "Two martial weapons"],
          ["A light crossbow and 20 bolts", "Two handaxes"],
          ["A dungeoneer's pack", "An explorer's pack"]
        ],
        fixed: []
      },
      features: [
        { name: "Fighting Style", description: "Choose a fighting style: Archery (+2 ranged attack), Defense (+1 AC in armor), Dueling (+2 damage one-handed), Great Weapon Fighting (reroll 1s and 2s on damage with two-handed), Protection (impose disadvantage on attacks against allies), or Two-Weapon Fighting (add ability mod to off-hand damage)." },
        { name: "Second Wind", description: "On your turn, you can use a bonus action to regain 1d10 + your fighter level hit points. Once per short or long rest." }
      ],
      spellcasting: null,
      accentColor: "orange", iconId: "icon-class-fighter"
    },

    monk: {
      name: "Monk",
      description: "Martial artists who channel ki energy to perform extraordinary feats of speed and power.",
      hitDie: 8,
      primaryAbility: "Dexterity & Wisdom",
      savingThrows: ["STR", "DEX"],
      armorProficiencies: [],
      weaponProficiencies: ["Simple weapons", "Shortswords"],
      toolProficiencies: ["One type of artisan's tools or one musical instrument"],
      skillChoices: { pick: 2, from: ["Acrobatics", "Athletics", "History", "Insight", "Religion", "Stealth"] },
      startingEquipment: {
        choices: [
          ["A shortsword", "Any simple weapon"],
          ["A dungeoneer's pack", "An explorer's pack"]
        ],
        fixed: ["10 darts"]
      },
      features: [
        { name: "Unarmored Defense", description: "While wearing no armor and not wielding a shield, your AC equals 10 + DEX modifier + WIS modifier." },
        { name: "Martial Arts", description: "You can use DEX instead of STR for unarmed strikes and monk weapons. You can roll a d4 in place of the normal damage. When you take the Attack action with an unarmed strike or monk weapon, you can make one unarmed strike as a bonus action." }
      ],
      spellcasting: null,
      accentColor: "teal", iconId: "icon-class-monk"
    },

    paladin: {
      name: "Paladin",
      description: "Holy warriors bound by a sacred oath who wield divine power alongside martial might.",
      hitDie: 10,
      primaryAbility: "Strength & Charisma",
      savingThrows: ["WIS", "CHA"],
      armorProficiencies: ["All armor", "Shields"],
      weaponProficiencies: ["Simple weapons", "Martial weapons"],
      toolProficiencies: [],
      skillChoices: { pick: 2, from: ["Athletics", "Insight", "Intimidation", "Medicine", "Persuasion", "Religion"] },
      startingEquipment: {
        choices: [
          ["A martial weapon and a shield", "Two martial weapons"],
          ["Five javelins", "Any simple melee weapon"],
          ["A priest's pack", "An explorer's pack"]
        ],
        fixed: ["Chain mail", "A holy symbol"]
      },
      features: [
        { name: "Divine Sense", description: "As an action, you can detect celestials, fiends, and undead within 60 feet until the end of your next turn. 1 + CHA modifier uses per long rest." },
        { name: "Lay on Hands", description: "You have a pool of healing power equal to your paladin level x 5. As an action, touch a creature and restore any number of hit points from the pool." }
      ],
      spellcasting: {
        ability: "CHA", cantripsKnown: 0, spellsKnown: null, prepared: true,
        spellSlots: { 1: 2 },
        note: "Paladins gain spellcasting at level 2. At level 1, you have Divine Sense and Lay on Hands.",
        spellList: ["Bless","Command","Cure Wounds","Detect Magic","Divine Favor","Heroism","Protection from Evil and Good","Searing Smite","Shield of Faith","Thunderous Smite","Wrathful Smite"]
      },
      accentColor: "gold", iconId: "icon-class-paladin"
    },

    ranger: {
      name: "Ranger",
      description: "Skilled scouts who blend martial prowess with nature magic, deadly with bow or blade.",
      hitDie: 10,
      primaryAbility: "Dexterity & Wisdom",
      savingThrows: ["STR", "DEX"],
      armorProficiencies: ["Light armor", "Medium armor", "Shields"],
      weaponProficiencies: ["Simple weapons", "Martial weapons"],
      toolProficiencies: [],
      skillChoices: { pick: 3, from: ["Animal Handling", "Athletics", "Insight", "Investigation", "Nature", "Perception", "Stealth", "Survival"] },
      startingEquipment: {
        choices: [
          ["Scale mail", "Leather armor"],
          ["Two shortswords", "Two simple melee weapons"],
          ["A dungeoneer's pack", "An explorer's pack"]
        ],
        fixed: ["A longbow and a quiver of 20 arrows"]
      },
      features: [
        { name: "Favored Enemy", description: "Choose a type of favored enemy: aberrations, beasts, celestials, constructs, dragons, elementals, fey, fiends, giants, monstrosities, oozes, plants, or undead. You have advantage on Survival checks to track them and Intelligence checks to recall information about them." },
        { name: "Natural Explorer", description: "Choose a favored terrain: arctic, coast, desert, forest, grassland, mountain, swamp, or Underdark. In your favored terrain, you gain benefits to travel and foraging." }
      ],
      spellcasting: {
        ability: "WIS", cantripsKnown: 0, spellsKnown: 0, prepared: false,
        spellSlots: {},
        note: "Rangers gain spellcasting at level 2.",
        spellList: ["Alarm","Animal Friendship","Cure Wounds","Detect Magic","Ensnaring Strike","Fog Cloud","Goodberry","Hail of Thorns","Hunter's Mark","Longstrider","Speak with Animals"]
      },
      accentColor: "green", iconId: "icon-class-ranger"
    },

    rogue: {
      name: "Rogue",
      description: "Cunning operatives who deal devastating sneak attacks and excel at skills others can only dream of.",
      hitDie: 8,
      primaryAbility: "Dexterity",
      savingThrows: ["DEX", "INT"],
      armorProficiencies: ["Light armor"],
      weaponProficiencies: ["Simple weapons", "Hand crossbows", "Longswords", "Rapiers", "Shortswords"],
      toolProficiencies: ["Thieves' tools"],
      skillChoices: { pick: 4, from: ["Acrobatics", "Athletics", "Deception", "Insight", "Intimidation", "Investigation", "Perception", "Performance", "Persuasion", "Sleight of Hand", "Stealth"] },
      startingEquipment: {
        choices: [
          ["A rapier", "A shortsword"],
          ["A shortbow and quiver of 20 arrows", "A shortsword"],
          ["A burglar's pack", "A dungeoneer's pack", "An explorer's pack"]
        ],
        fixed: ["Leather armor", "Two daggers", "Thieves' tools"]
      },
      features: [
        { name: "Expertise", description: "Choose two of your skill proficiencies, or one skill proficiency and thieves' tools. Your proficiency bonus is doubled for any ability check you make with them." },
        { name: "Sneak Attack", description: "Once per turn, you can deal an extra 1d6 damage to one creature you hit with an attack if you have advantage on the attack roll. You don't need advantage if another enemy of the target is within 5 feet of it. The attack must use a finesse or a ranged weapon." },
        { name: "Thieves' Cant", description: "You have learned thieves' cant, a secret mix of dialect, jargon, and code." }
      ],
      spellcasting: null,
      accentColor: "red", iconId: "icon-class-rogue"
    },

    sorcerer: {
      name: "Sorcerer",
      description: "Innate spellcasters who bend and twist their magic with metamagic, reshaping spells on the fly.",
      hitDie: 6,
      primaryAbility: "Charisma",
      savingThrows: ["CON", "CHA"],
      armorProficiencies: [],
      weaponProficiencies: ["Daggers", "Darts", "Slings", "Quarterstaffs", "Light crossbows"],
      toolProficiencies: [],
      skillChoices: { pick: 2, from: ["Arcana", "Deception", "Insight", "Intimidation", "Persuasion", "Religion"] },
      startingEquipment: {
        choices: [
          ["A light crossbow and 20 bolts", "Any simple weapon"],
          ["A component pouch", "An arcane focus"],
          ["A dungeoneer's pack", "An explorer's pack"]
        ],
        fixed: ["Two daggers"]
      },
      features: [
        { name: "Spellcasting", description: "You can cast sorcerer spells using Charisma as your spellcasting ability. Your magic comes from an innate source within you." },
        { name: "Sorcerous Origin", description: "Choose a source of your innate magic: Draconic Bloodline or Wild Magic. Your origin grants you features at 1st level and beyond." }
      ],
      spellcasting: {
        ability: "CHA", cantripsKnown: 4, spellsKnown: 2, prepared: false,
        spellSlots: { 1: 2 },
        spellList: ["Burning Hands","Charm Person","Chromatic Orb","Color Spray","Detect Magic","Disguise Self","Expeditious Retreat","False Life","Fog Cloud","Jump","Mage Armor","Magic Missile","Shield","Sleep","Thunderwave"]
      },
      accentColor: "blue", iconId: "icon-class-sorcerer"
    },

    warlock: {
      name: "Warlock",
      description: "Pact-bound spellcasters who wield eldritch power granted by otherworldly patrons.",
      hitDie: 8,
      primaryAbility: "Charisma",
      savingThrows: ["WIS", "CHA"],
      armorProficiencies: ["Light armor"],
      weaponProficiencies: ["Simple weapons"],
      toolProficiencies: [],
      skillChoices: { pick: 2, from: ["Arcana", "Deception", "History", "Intimidation", "Investigation", "Nature", "Religion"] },
      startingEquipment: {
        choices: [
          ["A light crossbow and 20 bolts", "Any simple weapon"],
          ["A component pouch", "An arcane focus"],
          ["A scholar's pack", "A dungeoneer's pack"]
        ],
        fixed: ["Leather armor", "Any simple weapon", "Two daggers"]
      },
      features: [
        { name: "Otherworldly Patron", description: "Choose a patron: The Archfey, The Fiend, or The Great Old One. Your patron grants you features and an expanded spell list." },
        { name: "Pact Magic", description: "You can cast warlock spells using Charisma. You have a limited number of spell slots that recharge on a short rest, rather than a long rest." }
      ],
      spellcasting: {
        ability: "CHA", cantripsKnown: 2, spellsKnown: 2, prepared: false,
        spellSlots: { 1: 1 },
        spellList: ["Armor of Agathys","Arms of Hadar","Charm Person","Comprehend Languages","Expeditious Retreat","Hellish Rebuke","Hex","Illusory Script","Protection from Evil and Good","Unseen Servant","Witch Bolt"]
      },
      accentColor: "purple", iconId: "icon-class-warlock"
    },

    wizard: {
      name: "Wizard",
      description: "Scholarly mages who command the largest spell list in the game through rigorous study and preparation.",
      hitDie: 6,
      primaryAbility: "Intelligence",
      savingThrows: ["INT", "WIS"],
      armorProficiencies: [],
      weaponProficiencies: ["Daggers", "Darts", "Slings", "Quarterstaffs", "Light crossbows"],
      toolProficiencies: [],
      skillChoices: { pick: 2, from: ["Arcana", "History", "Insight", "Investigation", "Medicine", "Religion"] },
      startingEquipment: {
        choices: [
          ["A quarterstaff", "A dagger"],
          ["A component pouch", "An arcane focus"],
          ["A scholar's pack", "An explorer's pack"]
        ],
        fixed: ["A spellbook"]
      },
      features: [
        { name: "Spellcasting", description: "As a student of arcane magic, you have a spellbook containing spells. Intelligence is your spellcasting ability." },
        { name: "Arcane Recovery", description: "Once per day during a short rest, you can recover expended spell slots. The slots can have a combined level equal to or less than half your wizard level (rounded up)." }
      ],
      spellcasting: {
        ability: "INT", cantripsKnown: 3, spellsKnown: 6, prepared: true,
        spellSlots: { 1: 2 },
        note: "You start with a spellbook containing 6 first-level wizard spells.",
        spellList: ["Burning Hands","Charm Person","Chromatic Orb","Color Spray","Comprehend Languages","Detect Magic","Disguise Self","Expeditious Retreat","False Life","Feather Fall","Find Familiar","Fog Cloud","Grease","Identify","Mage Armor","Magic Missile","Shield","Silent Image","Sleep","Thunderwave"]
      },
      accentColor: "blue", iconId: "icon-class-wizard"
    }
  },

  // ── Backgrounds ────────────────────────────────────────────────
  BACKGROUNDS: {
    acolyte: {
      name: "Acolyte",
      description: "You have spent your life in the service of a temple to a specific god or pantheon of gods.",
      skillProficiencies: ["Insight", "Religion"],
      toolProficiencies: [],
      languages: 2,
      equipment: ["A holy symbol", "A prayer book or prayer wheel", "5 sticks of incense", "Vestments", "Common clothes", "Belt pouch with 15 gp"],
      feature: { name: "Shelter of the Faithful", description: "You and your companions can expect to receive free healing and care at a temple of your faith, and you can call upon the priests for non-hazardous assistance." },
      personalityTraits: ["I idolize a particular hero of my faith.","I can find common ground between the fiercest enemies.","I see omens in every event and action.","Nothing can shake my optimistic attitude.","I quote sacred texts and proverbs in almost every situation.","I am tolerant of other faiths and respect their practices.","I've enjoyed fine food, drink, and high society. Rough living grates on me.","I've spent so long in the temple that I have little experience with the outside world."],
      ideals: ["Tradition \u2014 The ancient traditions of worship must be preserved. (Lawful)","Charity \u2014 I always try to help those in need. (Good)","Change \u2014 We must help bring about the changes the gods are working in the world. (Chaotic)","Power \u2014 I hope to one day rise to the top of my faith's hierarchy. (Lawful)","Faith \u2014 I trust that my deity will guide my actions. (Lawful)","Aspiration \u2014 I seek to prove myself worthy of my god's favor. (Any)"],
      bonds: ["I would die to recover an ancient relic of my faith.","I will someday get revenge on the corrupt temple hierarchy.","I owe my life to the priest who took me in as an orphan.","Everything I do is for the common people.","I will do anything to protect the temple where I served.","I seek to preserve a sacred text that my enemies seek to destroy."],
      flaws: ["I judge others harshly, and myself even more severely.","I put too much trust in those who wield power within my temple's hierarchy.","My piety sometimes leads me to blindly trust those that profess faith in my god.","I am inflexible in my thinking.","I am suspicious of strangers and expect the worst of them.","Once I pick a goal, I become obsessed with it to the detriment of everything else."]
    },
    charlatan: {
      name: "Charlatan",
      description: "You have always had a way with people. You know what makes them tick and can tease out their desires.",
      skillProficiencies: ["Deception", "Sleight of Hand"],
      toolProficiencies: ["Disguise kit", "Forgery kit"],
      languages: 0,
      equipment: ["Fine clothes", "Disguise kit", "Tools of the con of your choice", "Belt pouch with 15 gp"],
      feature: { name: "False Identity", description: "You have created a second identity including documentation, acquaintances, and disguises. You can forge documents including official papers and personal letters." },
      personalityTraits: ["I fall in and out of love easily.","I have a joke for every occasion.","Flattery is my preferred trick for getting what I want.","I'm a born gambler who can't resist taking a risk.","I lie about almost everything, even when there's no reason to.","Sarcasm and insults are my weapons of choice.","I keep multiple holy symbols on me and invoke whichever deity might be useful.","I pocket anything I see that might have some value."],
      ideals: ["Independence \u2014 I am a free spirit. No one tells me what to do. (Chaotic)","Fairness \u2014 I never target people who can't afford to lose a few coins. (Lawful)","Charity \u2014 I distribute the money I acquire to the people who really need it. (Good)","Creativity \u2014 I never run the same con twice. (Chaotic)","Friendship \u2014 Material goods come and go. Bonds of friendship last forever. (Good)","Aspiration \u2014 I'm determined to make something of myself. (Any)"],
      bonds: ["I fleeced the wrong person and must work to ensure they never cross paths with me again.","I owe everything to my mentor, a horrible person who's probably rotting in jail.","Somewhere out there, I have a child who doesn't know me.","I come from a noble family, and one day I'll reclaim my lands and title.","A powerful person took something from me, and I aim to take it back.","I swindled an innocent person and I seek to atone."],
      flaws: ["I can't resist a pretty face.","I'm always in debt.","I'm convinced that no one could ever fool me the way I fool others.","I'm too greedy for my own good.","I can't resist swindling people who are more powerful than me.","I hate to admit it and will hate myself for it, but I'll run to preserve my own hide."]
    },
    criminal: {
      name: "Criminal",
      description: "You have a history of breaking the law and have spent a lot of time among other criminals.",
      skillProficiencies: ["Deception", "Stealth"],
      toolProficiencies: ["One type of gaming set", "Thieves' tools"],
      languages: 0,
      equipment: ["A crowbar", "Dark common clothes including a hood", "Belt pouch with 15 gp"],
      feature: { name: "Criminal Contact", description: "You have a reliable and trustworthy contact who acts as your liaison to a network of other criminals." },
      personalityTraits: ["I always have a plan for what to do when things go wrong.","I am always calm, no matter the situation.","The first thing I do in a new place is note the locations of everything valuable.","I would rather make a new friend than a new enemy.","I am incredibly slow to trust.","I don't pay attention to the risks in a situation.","The best way to get me to do something is to tell me I can't.","I blow up at the slightest insult."],
      ideals: ["Honor \u2014 I don't steal from others in the trade. (Lawful)","Freedom \u2014 Chains are meant to be broken, as are those who would forge them. (Chaotic)","Charity \u2014 I steal from the wealthy so that I can help people in need. (Good)","Greed \u2014 I will do whatever it takes to become wealthy. (Evil)","People \u2014 I'm loyal to my friends, not to any ideals. (Neutral)","Redemption \u2014 There's a spark of good in everyone. (Good)"],
      bonds: ["I'm trying to pay off an old debt I owe to a generous benefactor.","My ill-gotten gains go to support my family.","Something important was taken from me, and I aim to steal it back.","I will become the greatest thief that ever lived.","I'm guilty of a terrible crime. I hope I can redeem myself for it.","Someone I loved died because of a mistake I made."],
      flaws: ["When I see something valuable, I can't think about anything but how to steal it.","When faced with a choice between money and my friends, I usually choose the money.","If there's a plan, I'll forget it. If I don't forget it, I'll ignore it.","I have a tell that reveals when I'm lying.","I turn tail and run when things look bad.","An innocent person is in prison for a crime that I committed. I'm okay with that."]
    },
    entertainer: {
      name: "Entertainer",
      description: "You thrive in front of an audience. You know how to entrance them, entertain them, and inspire them.",
      skillProficiencies: ["Acrobatics", "Performance"],
      toolProficiencies: ["Disguise kit", "One type of musical instrument"],
      languages: 0,
      equipment: ["A musical instrument of your choice", "The favor of an admirer", "A costume", "Belt pouch with 15 gp"],
      feature: { name: "By Popular Demand", description: "You can always find a place to perform. You receive free lodging and food in exchange for performing each night." },
      personalityTraits: ["I know a story relevant to almost every situation.","Whenever I come to a new place, I collect local rumors and spread gossip.","I'm a hopeless romantic, always searching for that special someone.","Nobody stays angry at me for long, since I can defuse any tension.","I love a good insult, even one directed at me.","I get bitter if I'm not the center of attention.","I'll settle for nothing less than perfection.","I change my mood or my mind as quickly as I change key in a song."],
      ideals: ["Beauty \u2014 When I perform, I make the world better. (Good)","Tradition \u2014 The stories, legends, and songs of the past must never be forgotten. (Lawful)","Creativity \u2014 The world is in need of new ideas and bold action. (Chaotic)","Greed \u2014 I'm only in it for the money and fame. (Evil)","People \u2014 I like seeing smiles on people's faces. That's all that matters. (Neutral)","Honesty \u2014 Art should reflect the soul; it should come from within. (Any)"],
      bonds: ["My instrument is my most treasured possession.","Someone stole my precious instrument, and I will get it back.","I want to be famous, whatever it takes.","I idolize a hero of the old tales and measure my deeds against theirs.","I will do anything to prove myself superior to a hated rival.","I would do anything for the other members of my old troupe."],
      flaws: ["I'll do anything to win fame and renown.","I'm a sucker for a pretty face.","A scandal prevents me from ever going home. That kind of trouble follows me.","I once satirized a noble who still wants my head. It was a mistake I will likely repeat.","I have trouble keeping my true feelings hidden.","Despite my best efforts, I am unreliable to my friends."]
    },
    "folk-hero": {
      name: "Folk Hero",
      description: "You come from a humble social rank, but you are destined for so much more. The common people regard you as their champion.",
      skillProficiencies: ["Animal Handling", "Survival"],
      toolProficiencies: ["One type of artisan's tools", "Vehicles (land)"],
      languages: 0,
      equipment: ["A set of artisan's tools", "A shovel", "An iron pot", "Common clothes", "Belt pouch with 10 gp"],
      feature: { name: "Rustic Hospitality", description: "Since you come from the ranks of the common folk, you fit in among them with ease. You can find a place to hide, rest, or recuperate among commoners." },
      personalityTraits: ["I judge people by their actions, not their words.","If someone is in trouble, I'm always ready to lend help.","When I set my mind to something, I follow through no matter what.","I have a strong sense of fair play.","I'm confident in my own abilities and do what I can to instill confidence in others.","Thinking is for other people. I prefer action.","I misuse long words in an attempt to sound smarter.","I get bored easily. When am I going to get on with my destiny?"],
      ideals: ["Respect \u2014 People deserve to be treated with dignity. (Good)","Fairness \u2014 No one should get preferential treatment before the law. (Lawful)","Freedom \u2014 Tyrants must not be allowed to oppress the people. (Chaotic)","Might \u2014 If I become strong, I can take what I want. (Evil)","Sincerity \u2014 There's no good in pretending to be something I'm not. (Neutral)","Destiny \u2014 Nothing and no one can steer me away from my higher calling. (Any)"],
      bonds: ["I have a family, but I have no idea where they are.","I worked the land, I love the land, and I will protect the land.","A proud noble once gave me a horrible beating, and I will take my revenge.","My tools are symbols of my past life, and I carry them so I will never forget my roots.","I protect those who cannot protect themselves.","I wish my childhood sweetheart had come with me to pursue my destiny."],
      flaws: ["The tyrant who rules my land will stop at nothing to see me killed.","I'm convinced of the significance of my destiny.","I have a weakness for the vices of the city.","Secretly, I believe that things would be better if I were a tyrant.","I have trouble trusting in my allies.","I'm too enamored of ale."]
    },
    "guild-artisan": {
      name: "Guild Artisan",
      description: "You are a member of an artisan's guild, skilled in a particular field and closely associated with other artisans.",
      skillProficiencies: ["Insight", "Persuasion"],
      toolProficiencies: ["One type of artisan's tools"],
      languages: 1,
      equipment: ["A set of artisan's tools", "A letter of introduction from your guild", "Traveler's clothes", "Belt pouch with 15 gp"],
      feature: { name: "Guild Membership", description: "Your guild provides lodging if available. You can gain an audience with powerful people through your guild contacts." },
      personalityTraits: ["I believe that anything worth doing is worth doing right.","I'm rude to people who lack my commitment to hard work.","I like to talk at length about my profession.","I don't part with my money easily and will haggle tirelessly.","I'm well known for my work, and I want to make sure everyone appreciates it.","I've been isolated in my workshop for so long that I don't deal well with people.","I'm full of witty aphorisms and have a proverb for every occasion.","I'm always looking for ways to improve my craft."],
      ideals: ["Community \u2014 It is the duty of all civilized people to strengthen the bonds of community. (Lawful)","Generosity \u2014 My talents were given to me so I could use them to benefit the world. (Good)","Freedom \u2014 Everyone should be free to pursue their own livelihood. (Chaotic)","Greed \u2014 I'm only in it for the money. (Evil)","People \u2014 I'm committed to the people I care about, not to ideals. (Neutral)","Aspiration \u2014 I work hard to be the best there is at my craft. (Any)"],
      bonds: ["The workshop where I learned my trade is the most important place in the world to me.","I created a great work for someone, and then found them unworthy to receive it.","I owe my guild a great debt for forging me into the person I am today.","I pursue wealth to secure someone's love.","One day I will return to my guild and prove that I am the greatest artisan of them all.","I will get revenge on the evil forces that destroyed my place of business."],
      flaws: ["I'll do anything to get my hands on something rare or priceless.","I'm quick to assume that someone is trying to cheat me.","No one must ever learn that I once stole money from guild coffers.","I'm never satisfied with what I have.","I would do anything for a member of my former guild.","I'm horribly jealous of anyone who can outshine my handiwork."]
    },
    hermit: {
      name: "Hermit",
      description: "You lived in seclusion for a formative part of your life, in a place of contemplation and spiritual significance.",
      skillProficiencies: ["Medicine", "Religion"],
      toolProficiencies: ["Herbalism kit"],
      languages: 1,
      equipment: ["A scroll case stuffed with notes from your studies", "A winter blanket", "Common clothes", "Herbalism kit", "5 gp"],
      feature: { name: "Discovery", description: "The quiet seclusion of your hermitage gave you access to a unique and powerful discovery. It might be a great truth, a hidden site, a long-forgotten fact, or unearthed relic." },
      personalityTraits: ["I've been isolated for so long that I rarely speak.","I am utterly serene, even in the face of disaster.","The leader of my community had something wise to say on every topic.","I feel tremendous empathy for all who suffer.","I'm oblivious to etiquette and social expectations.","I connect everything that happens to me to a grand, cosmic plan.","I often get lost in my own thoughts and contemplation.","I am working on a grand philosophical theory."],
      ideals: ["Greater Good \u2014 My gifts are meant to be shared with all. (Good)","Logic \u2014 Emotions must not cloud our sense of what is right. (Lawful)","Free Thinking \u2014 Inquiry and curiosity are the pillars of progress. (Chaotic)","Power \u2014 Solitude and contemplation are paths toward mystical power. (Evil)","Live and Let Live \u2014 Meddling in the affairs of others only causes trouble. (Neutral)","Self-Knowledge \u2014 If you know yourself, there's nothing left to know. (Any)"],
      bonds: ["Nothing is more important than the other members of my hermitage.","I entered seclusion to hide from the ones who might still be hunting me.","I'm still seeking the enlightenment I pursued in my seclusion.","I entered seclusion because I loved someone I could not have.","Should my discovery come to light, it could bring ruin to the world.","My isolation gave me great insight into a great evil that only I can destroy."],
      flaws: ["Now that I've returned to the world, I enjoy its delights a little too much.","I harbor dark, bloodthirsty thoughts that my isolation failed to quell.","I am dogmatic in my thoughts and philosophy.","I let my need to win arguments overshadow friendships and harmony.","I'd risk too much to uncover a bit of lost knowledge.","I like keeping secrets and won't share them with anyone."]
    },
    noble: {
      name: "Noble",
      description: "You understand wealth, power, and privilege. You carry a noble title, and your family owns land.",
      skillProficiencies: ["History", "Persuasion"],
      toolProficiencies: ["One type of gaming set"],
      languages: 1,
      equipment: ["Fine clothes", "A signet ring", "A scroll of pedigree", "A purse with 25 gp"],
      feature: { name: "Position of Privilege", description: "Thanks to your noble birth, people are inclined to think the best of you. You are welcome in high society, and common folk make every effort to accommodate you." },
      personalityTraits: ["My eloquent flattery makes everyone I talk to feel like the most important person in the world.","The common folk love me for my kindness and generosity.","No one could doubt by looking at my regal bearing that I am above the common rabble.","I take great pains to always look my best and follow the latest fashions.","I don't like to get my hands dirty, and I won't be caught in unsuitable accommodations.","Despite my noble birth, I do not place myself above other folk. We all have the same blood.","My favor, once lost, is lost forever.","If you do me an injury, I will crush you, ruin your name, and salt your fields."],
      ideals: ["Respect \u2014 Respect is due to me because of my position, but all people deserve to be treated with dignity. (Good)","Responsibility \u2014 It is my duty to respect the authority of those above me. (Lawful)","Independence \u2014 I must prove that I can handle myself without the coddling of my family. (Chaotic)","Power \u2014 If I can attain more power, no one will tell me what to do. (Evil)","Family \u2014 Blood runs thicker than water. (Any)","Noble Obligation \u2014 It is my duty to protect and care for the people beneath me. (Good)"],
      bonds: ["I will face any challenge to win the approval of my family.","My house's alliance with another noble family must be sustained at all costs.","Nothing is more important than the other members of my family.","I am in love with the heir of a family that my family despises.","My loyalty to my sovereign is unwavering.","The common folk must see me as a hero of the people."],
      flaws: ["I secretly believe that everyone is beneath me.","I hide a truly scandalous secret that could ruin my family forever.","I too often hear veiled insults and threats in every word addressed to me.","I have an insatiable desire for carnal pleasures.","In fact, the world does revolve around me.","By my words and actions, I often bring shame to my family."]
    },
    outlander: {
      name: "Outlander",
      description: "You grew up in the wilds, far from civilization and the comforts of town and technology.",
      skillProficiencies: ["Athletics", "Survival"],
      toolProficiencies: ["One type of musical instrument"],
      languages: 1,
      equipment: ["A staff", "A hunting trap", "A trophy from an animal you've encountered", "Traveler's clothes", "Belt pouch with 10 gp"],
      feature: { name: "Wanderer", description: "You have an excellent memory for maps and geography. You can always recall the general layout of terrain, settlements, and features around you. You can find food and fresh water for yourself and up to five others each day." },
      personalityTraits: ["I'm driven by a wanderlust that led me away from home.","I watch over my friends as if they were a litter of newborn pups.","I once ran twenty-five miles without stopping to warn my clan of danger.","I have a lesson for every situation, drawn from observing nature.","I place no stock in wealthy or well-mannered folk.","I'm always picking things up, absently fiddling with them.","I feel far more comfortable around animals than people.","I was raised by wolves."],
      ideals: ["Change \u2014 Life is like the seasons, in constant change. (Chaotic)","Greater Good \u2014 It is each person's responsibility to make the most happiness for the whole tribe. (Good)","Honor \u2014 If I dishonor myself, I dishonor my whole clan. (Lawful)","Might \u2014 The strongest are meant to rule. (Evil)","Nature \u2014 The natural world is more important than all the constructs of civilization. (Neutral)","Glory \u2014 I must earn glory in battle, for myself and my clan. (Any)"],
      bonds: ["My family, clan, or tribe is the most important thing in my life.","An injury to the unspoiled wilderness of my home is an injury to me.","I will bring terrible wrath down on the evildoers who destroyed my homeland.","I am the last of my tribe, and it is up to me to ensure their names enter legend.","I suffer awful visions of a coming disaster and will do anything to prevent it.","It is my duty to provide children to sustain my tribe."],
      flaws: ["I am too enamored of ale and other intoxicants.","There's no room for caution in a life lived to the fullest.","I remember every insult I've received and nurse a silent resentment toward anyone who's ever wronged me.","I am slow to trust members of other races, tribes, and societies.","Violence is my answer to almost any challenge.","Don't expect me to save those who can't save themselves."]
    },
    sage: {
      name: "Sage",
      description: "You spent years learning the lore of the multiverse. You scoured manuscripts, studied scrolls, and listened to experts.",
      skillProficiencies: ["Arcana", "History"],
      toolProficiencies: [],
      languages: 2,
      equipment: ["A bottle of black ink", "A quill", "A small knife", "A letter from a dead colleague with a question you have not yet answered", "Common clothes", "Belt pouch with 10 gp"],
      feature: { name: "Researcher", description: "When you attempt to learn or recall a piece of lore, if you do not know that information, you often know where and from whom you can obtain it." },
      personalityTraits: ["I use polysyllabic words that convey the impression of great erudition.","I've read every book in the world's greatest libraries.","I'm used to helping out those who aren't as smart as I am.","There's nothing I like more than a good mystery.","I'm willing to listen to every side of an argument before I make my own judgment.","I speak slowly when talking to anyone else, as though they were all hard of hearing.","I am horribly, horribly awkward in social situations.","I'm convinced that people are always trying to steal my secrets."],
      ideals: ["Knowledge \u2014 The path to power and self-improvement is through knowledge. (Neutral)","Beauty \u2014 What is beautiful points us beyond itself toward what is true. (Good)","Logic \u2014 Emotions must not cloud our logical thinking. (Lawful)","No Limits \u2014 Nothing should fetter the infinite possibility inherent in all existence. (Chaotic)","Power \u2014 Knowledge is the path to power and domination. (Evil)","Self-Improvement \u2014 The goal of a life of study is the betterment of oneself. (Any)"],
      bonds: ["It is my duty to protect my students.","I have an ancient text that holds terrible secrets that must not fall into the wrong hands.","I work to preserve a library, university, scriptorium, or monastery.","My life's work is a series of tomes related to a specific field of lore.","I've been searching my whole life for the answer to a certain question.","I sold my soul for knowledge. I hope to do great deeds and win it back."],
      flaws: ["I am easily distracted by the promise of information.","Most people scream and run when they see a demon. I stop and take notes.","Unlocking an ancient mystery is worth the price of a civilization.","I overlook obvious solutions in favor of complicated ones.","I speak without really thinking through my words, invariably insulting others.","I can't keep a secret to save my life, or anyone else's."]
    },
    sailor: {
      name: "Sailor",
      description: "You sailed on a seagoing vessel for years. You've weathered mighty storms, braved open oceans, and faced many challenges.",
      skillProficiencies: ["Athletics", "Perception"],
      toolProficiencies: ["Navigator's tools", "Vehicles (water)"],
      languages: 0,
      equipment: ["A belaying pin (club)", "50 feet of silk rope", "A lucky charm", "Common clothes", "Belt pouch with 10 gp"],
      feature: { name: "Ship's Passage", description: "When you need to, you can secure free passage on a sailing ship for yourself and your companions. In return, you and your companions are expected to assist the crew during the voyage." },
      personalityTraits: ["My friends know they can rely on me, no matter what.","I work hard so that I can play hard when the work is done.","I enjoy sailing into new ports and making new friends.","I stretch the truth for the sake of a good story.","To me, a tavern brawl is a nice way to get to know a new city.","I never pass up a friendly wager.","My language is as foul as an otyugh nest.","I like a job well done, especially if I can convince someone else to do it."],
      ideals: ["Respect \u2014 The thing that keeps a ship together is mutual respect between captain and crew. (Good)","Fairness \u2014 We all do the work, so we all share in the rewards. (Lawful)","Freedom \u2014 The sea is freedom \u2014 the freedom to go anywhere and do anything. (Chaotic)","Mastery \u2014 I'm a predator, and the other ships on the sea are my prey. (Evil)","People \u2014 I'm committed to my crewmates, not to ideals. (Neutral)","Aspiration \u2014 Someday I'll own my own ship and chart my own destiny. (Any)"],
      bonds: ["I'm loyal to my captain first, everything else second.","The ship is most important \u2014 crewmates and captains come and go.","I'll always remember my first ship.","In a harbor town, I have a paramour whose eyes nearly stole me from the sea.","I was cheated out of my fair share of the profits, and I want to get my due.","Ruthless pirates murdered my captain and crewmates, plundered our ship, and left me to die."],
      flaws: ["I follow orders, even if I think they're wrong.","I'll say anything to avoid having to do extra work.","Once someone questions my courage, I never back down no matter how dangerous the situation.","Once I start drinking, it's hard for me to stop.","I can't help but pocket loose coins and other trinkets I come across.","My pride will probably lead to my destruction."]
    },
    soldier: {
      name: "Soldier",
      description: "You have served in an army and know military discipline. You trained with weapons and armor every day.",
      skillProficiencies: ["Athletics", "Intimidation"],
      toolProficiencies: ["One type of gaming set", "Vehicles (land)"],
      languages: 0,
      equipment: ["An insignia of rank", "A trophy taken from a fallen foe", "A set of bone dice or deck of cards", "Common clothes", "Belt pouch with 10 gp"],
      feature: { name: "Military Rank", description: "You have a military rank from your career as a soldier. Soldiers loyal to your former military organization still recognize your authority, and you can invoke your rank to exert influence." },
      personalityTraits: ["I'm always polite and respectful.","I'm haunted by memories of war. I can't get the images of violence out of my mind.","I've lost too many friends, and I'm slow to make new ones.","I'm full of inspiring and cautionary tales from my military experience.","I can stare down a hell hound without flinching.","I enjoy being strong and like breaking things.","I have a crude sense of humor.","I face problems head-on. A simple, direct solution is the best path to success."],
      ideals: ["Greater Good \u2014 Our lot is to lay down our lives in defense of others. (Good)","Responsibility \u2014 I do what I must and obey just authority. (Lawful)","Independence \u2014 When people follow orders blindly, they embrace a kind of tyranny. (Chaotic)","Might \u2014 In life as in war, the stronger force wins. (Evil)","Live and Let Live \u2014 Ideals aren't worth fighting over. (Neutral)","Nation \u2014 My city, nation, or people are all that matter. (Any)"],
      bonds: ["I would still lay down my life for the people I served with.","Someone saved my life on the battlefield. To this day, I will never leave a friend behind.","My honor is my life.","I'll never forget the crushing defeat my company suffered.","Those who serve with me are those worth dying for.","I fight for those who cannot fight for themselves."],
      flaws: ["The monstrous enemy we faced in battle still leaves me quivering with fear.","I have little respect for anyone who is not a proven warrior.","I made a terrible mistake in battle that cost many lives, and I would do anything to keep that secret.","My hatred of my enemies is blind and unreasoning.","I obey the law, even if the law causes misery.","I'd rather eat my armor than admit when I'm wrong."]
    },
    urchin: {
      name: "Urchin",
      description: "You grew up on the streets alone, orphaned, and poor. You had no one to watch over you, so you learned to watch over yourself.",
      skillProficiencies: ["Sleight of Hand", "Stealth"],
      toolProficiencies: ["Disguise kit", "Thieves' tools"],
      languages: 0,
      equipment: ["A small knife", "A map of the city you grew up in", "A pet mouse", "A token to remember your parents by", "Common clothes", "Belt pouch with 10 gp"],
      feature: { name: "City Secrets", description: "You know the secret patterns and flow to cities and can find passages through the urban sprawl that others would miss. When you are not in combat, you and companions you lead can travel between any two locations in the city twice as fast." },
      personalityTraits: ["I hide scraps of food and trinkets away in my pockets.","I ask a lot of questions.","I like to squeeze into small places where no one else can get to me.","I sleep with my back to a wall or tree, with everything I own wrapped in a bundle in my arms.","I eat like a pig and have bad manners.","I think anyone who's nice to me is hiding evil intent.","I don't like to bathe.","I bluntly say what other people are hinting at or hiding."],
      ideals: ["Respect \u2014 All people, rich or poor, deserve respect. (Good)","Community \u2014 We have to take care of each other. (Lawful)","Change \u2014 The low are lifted up, and the high and mighty are brought down. (Chaotic)","Retribution \u2014 The rich need to be shown what life and death are like in the gutters. (Evil)","People \u2014 I help the people who help me. (Neutral)","Aspiration \u2014 I'm going to prove that I'm worthy of a better life. (Any)"],
      bonds: ["My town or city is my home, and I'll fight to defend it.","I sponsor an orphanage to keep others from enduring what I was forced to endure.","I owe my survival to another urchin who taught me to live on the streets.","I owe a debt I can never repay to the person who took pity on me.","I escaped my life of poverty by robbing an important person, and I'm wanted for it.","No one else should have to endure the hardships I've been through."],
      flaws: ["If I'm outnumbered, I will run away from a fight.","Gold seems like a lot of money to me, and I'll do just about anything for more of it.","I will never fully trust anyone other than myself.","I'd rather kill someone in their sleep than fight fair.","It's not stealing if I need it more than someone else.","People who can't take care of themselves get what they deserve."]
    }
  },

  // ── All Skills (for skill choice UI) ──────────────────────────
  ALL_SKILLS: [
    { name: "Acrobatics", ability: "DEX" },
    { name: "Animal Handling", ability: "WIS" },
    { name: "Arcana", ability: "INT" },
    { name: "Athletics", ability: "STR" },
    { name: "Deception", ability: "CHA" },
    { name: "History", ability: "INT" },
    { name: "Insight", ability: "WIS" },
    { name: "Intimidation", ability: "CHA" },
    { name: "Investigation", ability: "INT" },
    { name: "Medicine", ability: "WIS" },
    { name: "Nature", ability: "INT" },
    { name: "Perception", ability: "WIS" },
    { name: "Performance", ability: "CHA" },
    { name: "Persuasion", ability: "CHA" },
    { name: "Religion", ability: "INT" },
    { name: "Sleight of Hand", ability: "DEX" },
    { name: "Stealth", ability: "DEX" },
    { name: "Survival", ability: "WIS" }
  ]
};
