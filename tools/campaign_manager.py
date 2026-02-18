import os
import shutil
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger('CampaignManager')

class CampaignManager:
    """Manages multiple campaign vaults via directory junctions."""
    
    def __init__(self, root_dir: str = "."):
        self.root = Path(root_dir).resolve()
        self.campaigns_dir = self.root / "campaigns"
        self.vault_link = self.root / "campaign_vault"
        
        # Ensure campaigns directory exists
        if not self.campaigns_dir.exists():
            self.campaigns_dir.mkdir()

    def ensure_migration(self):
        """Migrate existing campaign_vault to campaigns/Default if needed."""
        if not self.vault_link.exists():
            # Nothing to migrate, just create Default
            logger.info("No campaign_vault found. Creating Default campaign.")
            self.create_campaign("Default")
            self.set_campaign("Default")
            return
            
        if self._is_junction(self.vault_link):
            logger.info("campaign_vault is already a junction.")
            return

        if self.vault_link.is_dir():
            logger.info("Migrating existing campaign_vault to campaigns/Default...")
            default_path = self.campaigns_dir / "Default"
            
            # Move the directory
            try:
                # Rename is atomic-ish and fast
                shutil.move(str(self.vault_link), str(default_path))
                logger.info(f"Moved vault to {default_path}")
                
                # Create the junction
                self.set_campaign("Default")
            except Exception as e:
                logger.error(f"Migration failed: {e}")
                # Try to restore if something went wrong
                if default_path.exists() and not self.vault_link.exists():
                    shutil.move(str(default_path), str(self.vault_link))

    def list_campaigns(self) -> List[str]:
        """List available campaigns."""
        return [d.name for d in self.campaigns_dir.iterdir() if d.is_dir()]

    def create_campaign(self, name: str) -> bool:
        """Create a new campaign with default structure."""
        target = self.campaigns_dir / name
        if target.exists():
            logger.warning(f"Campaign '{name}' already exists.")
            return False
            
        try:
            target.mkdir()
            
            # Create standard subfolders
            subfolders = [
                "00 - Session Log",
                "01 - Party",
                "02 - NPCs",
                "03 - Locations",
                "04 - Quests/Active",
                "04 - Quests/Completed",
                "05 - Factions",
                "06 - World State",
                "07 - Lore",
                "Assets/Maps",
                "Assets/Tokens",
                "_templates"
            ]
            
            for folder in subfolders:
                (target / folder).mkdir(parents=True, exist_ok=True)
                
            # Create default clock
            world_state = target / "06 - World State"
            with open(world_state / "clock.md", "w", encoding="utf-8") as f:
                f.write("---\ncurrent_date: 1492-01-01\ntime_of_day: Morning\nsession: 1\n---\n# World Clock\n\n| Session | Time | Events |\n|---|---|---|\n")

            logger.info(f"Created campaign '{name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to create campaign '{name}': {e}")
            return False

    def set_campaign(self, name: str) -> bool:
        """Switch the active campaign via directory junction."""
        target = self.campaigns_dir / name
        if not target.exists():
            logger.error(f"Campaign '{name}' does not exist.")
            return False
            
        try:
            # Remove existing link/junction if it exists
            if self.vault_link.exists():
                if self._is_junction(self.vault_link):
                    self.vault_link.rmdir() # rmdir removes junctions without deleting contents
                else:
                    # It's a real directory and we shouldn't be here if migration ran,
                    # but safety first: don't delete a real directory!
                    logger.error(f"Cannot switch: {self.vault_link} is a real directory, not a junction.")
                    return False
            
            # Create junction
            # cmd /c mklink /J "link" "target"
            subprocess.run(
                ['cmd', '/c', 'mklink', '/J', str(self.vault_link), str(target)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info(f"Switched to campaign '{name}'")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create junction: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Failed to switch campaign: {e}")
            return False

    def get_active_campaign(self) -> Optional[str]:
        """Get the name of the currently active campaign."""
        if not self.vault_link.exists():
            return None
            
        try:
            # os.readlink works on junctions in Python 3.8+
            target = os.readlink(str(self.vault_link))
            return Path(target).name
        except OSError:
            return None

    def _is_junction(self, path: Path) -> bool:
        """Check if a path is a directory junction."""
        try:
            return path.is_symlink() or bool(os.readlink(str(path)))
        except OSError:
            return False
