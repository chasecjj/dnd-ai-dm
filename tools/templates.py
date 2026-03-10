"""
Canonical vault templates — Single source of truth for entity structure.

All code that creates NPC or location vault files should use these
builders. The Obsidian _templates/*.md files mirror this structure
for manual creation, but THIS module is the authoritative reference.

If you add/remove/reorder a section here, also update the matching
_templates/*.md file for consistency.
"""

from typing import Dict, Any, Optional


# ---------------------------------------------------------------------------
# Canonical section orders (used by normalize_vault.py too)
# ---------------------------------------------------------------------------

NPC_SECTIONS = [
    "Description",
    "Personality",
    "Background",
    "Secret",
    "Connections",
    "Party Relationship",
    "Plot Hooks",
    "DM Notes",
]

LOCATION_SECTIONS = [
    "Description",
    "Current State",
    "Notable Features",
    "NPCs Present",
    "Connections",
    "DM Notes",
]

PC_SECTIONS = [
    "Stats",
    "Abilities & Features",
    "Prepared Spells",
    "Inventory",
    "Personality",
    "Bonds & Hooks",
    "Session Notes",
]


# ---------------------------------------------------------------------------
# Canonical frontmatter field order
# ---------------------------------------------------------------------------

NPC_FRONTMATTER_ORDER = [
    "type", "name", "race", "role", "location", "faction",
    "disposition", "status", "first_seen_session", "last_seen_session",
    "auto_generated", "tags",
]


# ---------------------------------------------------------------------------
# NPC body builder
# ---------------------------------------------------------------------------

def build_npc_body(
    name: str,
    description: str = "_Physical appearance, mannerisms, voice._",
    personality: str = "_Key personality traits._",
    background: str = "_Unknown._",
    secret: str = "_Unknown._",
    connections: str = "_None established._",
    party_relationship: str = "",
    plot_hooks: str = "_None yet._",
    dm_notes: str = "",
    session_number: Optional[int] = None,
    auto_generated: bool = False,
) -> str:
    """Build a canonical NPC markdown body.

    Args:
        name: NPC name (used for H1 header).
        description: Physical description text.
        personality: Personality traits text.
        background: Background/history text.
        secret: Hidden information text.
        connections: Connections to other entities.
        party_relationship: How they relate to the party.
        plot_hooks: Story hooks involving this NPC.
        dm_notes: DM-only notes.
        session_number: If provided, used in default party_relationship/dm_notes.
        auto_generated: If True, adds auto-generation note to DM Notes.

    Returns:
        Canonical markdown body string.
    """
    if not party_relationship:
        if session_number is not None:
            party_relationship = f"_First encountered session {session_number}._"
        else:
            party_relationship = "_Not yet met._"

    if not dm_notes:
        if auto_generated and session_number is not None:
            dm_notes = f"_Auto-generated during session {session_number}._"
        else:
            dm_notes = "_Created by World Architect._"

    return (
        f"# {name}\n\n"
        f"## Description\n{description}\n\n"
        f"## Personality\n{personality}\n\n"
        f"## Background\n{background}\n\n"
        f"## Secret\n{secret}\n\n"
        f"## Connections\n{connections}\n\n"
        f"## Party Relationship\n{party_relationship}\n\n"
        f"## Plot Hooks\n{plot_hooks}\n\n"
        f"## DM Notes\n{dm_notes}"
    )


def build_npc_frontmatter(
    name: str,
    race: str = "Unknown",
    role: str = "Commoner",
    location: str = "Unknown",
    faction: str = "unaffiliated",
    disposition: str = "neutral",
    status: str = "alive",
    first_seen_session: Optional[int] = None,
    last_seen_session: Optional[int] = None,
    auto_generated: bool = False,
    tags: list = None,
    **extra,
) -> Dict[str, Any]:
    """Build canonical NPC frontmatter dict in correct key order.

    Returns:
        Ordered dict with canonical frontmatter fields.
    """
    fm = {
        "type": "npc",
        "name": name,
        "race": race,
        "role": role,
        "location": location,
        "faction": faction,
        "disposition": disposition,
        "status": status,
        "first_seen_session": first_seen_session,
        "last_seen_session": last_seen_session,
        "auto_generated": auto_generated,
        "tags": tags if tags is not None else ["npc"],
    }
    # Preserve any extra fields
    fm.update(extra)
    return fm


# ---------------------------------------------------------------------------
# Location body builder
# ---------------------------------------------------------------------------

def build_location_body(
    name: str,
    description: str = "_What this place looks like, sounds like, smells like._",
    current_state: str = "_What's happening here right now._",
    features: str = "_Notable features._",
    npcs: str = "_NPCs that can be found here._",
    connections: str = "_Links to other locations._",
    dm_notes: str = "_Hidden elements, upcoming events._",
    secrets: str = "",
    encounters: str = "",
) -> str:
    """Build a canonical location markdown body.

    Args:
        name: Location name (used for H1 header).
        Remaining args map to section content.

    Returns:
        Canonical markdown body string.
    """
    body = (
        f"# {name}\n\n"
        f"## Description\n{description}\n\n"
        f"## Current State\n{current_state}\n\n"
        f"## Notable Features\n{features}\n\n"
        f"## NPCs Present\n{npcs}\n\n"
        f"## Connections\n{connections}\n\n"
    )
    # Optional sections from WorldArchitect
    if secrets:
        body += f"## Secrets\n{secrets}\n\n"
    if encounters:
        body += f"## Encounter Possibilities\n{encounters}\n\n"
    body += f"## DM Notes\n{dm_notes}"
    return body
