"""
CartographerAgent — AI-powered battlemap generator for Foundry VTT.

Generates top-down battlemap images using Gemini's native image generation,
then creates Foundry VTT scenes with the generated images as backgrounds.

Art style target: Forgotten Adventures hand-painted fantasy battlemaps
(warm earth tones, orthographic bird's-eye view, watercolor aesthetic).
"""

import os
import io
import base64
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from google import genai
from google.genai import types as genai_types
from tools.rate_limiter import gemini_limiter

logger = logging.getLogger('Cartographer')


# ---------------------------------------------------------------------------
# Style Anchor — ensures consistent art direction across all generated maps
# ---------------------------------------------------------------------------

STYLE_PROMPT = """You are creating a top-down battlemap for a tabletop RPG.

CRITICAL REQUIREMENTS:
- View: Perfectly orthographic bird's-eye view (looking STRAIGHT DOWN)
- Style: Hand-painted fantasy cartography with warm watercolor textures
- Color palette: Rich earth tones — warm browns, deep greens, aged stone grays
- Lighting: Soft natural lighting with subtle shadows for depth
- Detail: Visible terrain features, furniture, objects at tabletop scale
- Spaces: Clear walkable open areas suitable for token placement (1-inch grid squares)
- NO text, NO labels, NO grid lines, NO arrows, NO UI elements
- NO perspective distortion — everything must be flat top-down
- NO characters, creatures, or people in the image
- The image should look like a professional hand-painted battlemap pack

The art style should match Forgotten Adventures battlemaps: rich, detailed,
watercolor-style painting with warm tones and clear spatial layout."""


PROMPT_ENGINEER_SYSTEM = """You are an expert at crafting image generation prompts for D&D battlemaps.

Given a location description, you produce a detailed, specific prompt that will generate
a high-quality top-down battlemap image. Your prompts always include:
1. The exact environment type and key features
2. Specific objects and terrain details to include
3. Color palette guidance
4. Spatial layout suggestions (where walls, paths, open areas should be)
5. Mood and atmosphere cues

You respond with ONLY the image generation prompt — no explanation, no JSON, no markdown."""


# ---------------------------------------------------------------------------
# CartographerAgent
# ---------------------------------------------------------------------------

class CartographerAgent:
    """Generates battlemap images and creates Foundry VTT scenes."""

    def __init__(
        self,
        client,
        foundry,
        vault,
        model_id: str = "gemini-2.0-flash",
        image_model: str = "gemini-2.5-flash-image",
        output_dir: Optional[str] = None,
    ):
        """
        Args:
            client: Google Gemini client.
            foundry: FoundryClient for VTT operations.
            vault: VaultManager for campaign data.
            model_id: Model for text generation (prompt crafting).
            image_model: Model for image generation (must support image output).
            output_dir: Directory to save generated map images.
                        Defaults to 'generated_maps/' relative to working directory.
        """
        self.client = client
        self.foundry = foundry
        self.vault = vault
        self.model_id = model_id
        self.image_model = image_model

        # Output directory for generated images
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path("generated_maps")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_scene(
        self,
        location_name: str,
        description: str,
        grid_size: str = "30x20",
        lighting: str = "bright",
    ) -> Dict[str, Any]:
        """Generate a battlemap image and optionally create a Foundry scene.

        Args:
            location_name: Name for the scene (e.g. "Zhentarim Warehouse").
            description: Natural-language description of the location.
            grid_size: Grid dimensions as "WxH" (e.g. "30x20").
            lighting: Lighting mood — "bright", "dim", "dark".

        Returns:
            Dict with keys: success, scene_name, image_path, error
        """
        logger.info(f"Generating map for '{location_name}': {description}")

        result = {
            "success": False,
            "scene_name": location_name,
            "image_path": "",
            "error": "",
        }

        try:
            # Step 1: Craft an optimized image prompt
            image_prompt = await self._craft_image_prompt(
                location_name, description, grid_size, lighting
            )
            logger.info(f"Image prompt crafted ({len(image_prompt)} chars)")

            # Step 2: Generate the battlemap image
            image_bytes = await self._generate_image(image_prompt)
            if not image_bytes:
                result["error"] = "Image generation returned no image data"
                return result

            # Step 3: Save the image
            safe_name = self._sanitize_filename(location_name)
            image_filename = f"{safe_name}.png"
            image_path = self.output_dir / image_filename
            image_path.write_bytes(image_bytes)
            result["image_path"] = str(image_path)
            logger.info(f"Map saved to {image_path} ({len(image_bytes)} bytes)")

            # Step 4: Create Foundry scene (if connected)
            if self.foundry and self.foundry.is_connected:
                # Convert absolute path to Vault-relative path for Foundry
                # Foundry's data directory now has a symposium link to campaign_vault
                try:
                    rel_path = str(image_path).replace(str(self.vault.vault_path), "campaign_vault").replace("\\", "/")
                except Exception:
                    # Fallback to absolute if path manipulation fails
                    rel_path = str(image_path)
                
                scene_result = await self._create_foundry_scene(
                    location_name, rel_path, grid_size, lighting
                )
                if scene_result:
                    logger.info(f"Foundry scene created: {scene_result}")

            result["success"] = True
            return result

        except Exception as e:
            error_msg = f"Map generation failed for '{location_name}': {e}"
            logger.error(error_msg, exc_info=True)
            result["error"] = str(e)
            return result

    async def _craft_image_prompt(
        self,
        location_name: str,
        description: str,
        grid_size: str,
        lighting: str,
    ) -> str:
        """Use AI to craft an optimized image generation prompt from the location description."""
        try:
            width, height = grid_size.split("x")
            aspect = "landscape" if int(width) > int(height) else "square"
        except (ValueError, IndexError):
            aspect = "landscape"

        lighting_desc = {
            "bright": "well-lit with natural daylight",
            "dim": "dimly lit with flickering torchlight and long shadows",
            "dark": "very dark with only faint moonlight or magical glow",
        }.get(lighting, "naturally lit")

        user_prompt = f"""Create an image generation prompt for this D&D battlemap:

Location: {location_name}
Description: {description}
Grid size: {grid_size} squares ({aspect} orientation)
Lighting: {lighting_desc}

The prompt should produce a top-down orthographic battlemap in hand-painted watercolor style.
Include specific terrain features, objects, and environmental details."""

        try:
            await gemini_limiter.acquire()
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=PROMPT_ENGINEER_SYSTEM,
                    temperature=0.7,
                )
            )
            crafted_prompt = response.text.strip()

            # Prepend the style anchor to ensure consistent art direction
            full_prompt = f"{STYLE_PROMPT}\n\n{crafted_prompt}"
            return full_prompt

        except Exception as e:
            logger.warning(f"Prompt crafting failed, using fallback: {e}")
            # Fallback: use description directly with style anchor
            return f"{STYLE_PROMPT}\n\nGenerate a top-down battlemap of: {location_name}. {description}"

    async def _generate_image(self, prompt: str) -> Optional[bytes]:
        """Generate a battlemap image using Gemini's native image generation.

        Returns image bytes or None on failure.
        """
        try:
            await gemini_limiter.acquire()
            response = await self.client.aio.models.generate_content(
                model=self.image_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_modalities=["Text", "Image"],
                    temperature=0.8,
                )
            )

            # Extract image from response
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        mime_type = part.inline_data.mime_type or ""
                        if mime_type.startswith("image/"):
                            return part.inline_data.data

            logger.warning("No image data in response")
            return None

        except Exception as e:
            logger.error(f"Image generation failed: {e}", exc_info=True)
            return None

    async def _create_foundry_scene(
        self,
        name: str,
        image_path: str,
        grid_size: str,
        lighting: str,
    ) -> Optional[Dict]:
        """Create a Foundry VTT scene with the generated image as background.

        Note: This requires the image to be accessible by Foundry's server.
        If the image is saved to a path Foundry can read, we reference it directly.
        Otherwise, this step is skipped.
        """
        try:
            width, height = grid_size.split("x")
            grid_w = int(width)
            grid_h = int(height)
        except (ValueError, IndexError):
            grid_w, grid_h = 30, 20

        darkness = {
            "bright": 0.0,
            "dim": 0.3,
            "dark": 0.7,
        }.get(lighting, 0.0)

        try:
            # Create the scene via Foundry REST API
            # The image path needs to be relative to Foundry's data directory
            # or an absolute path that Foundry's server can access
            scene_data = {
                "name": name,
                "navigation": True,
                "width": grid_w * 140,       # ~140px per grid square (standard)
                "height": grid_h * 140,
                "grid": {"size": 140, "type": 1},  # type 1 = square grid
                "darkness": darkness,
                "img": image_path,           # Foundry needs to be able to access this
            }

            result = self.foundry.create_entity("Scene", scene_data)
            logger.info(f"Foundry scene created: {result}")
            return result

        except Exception as e:
            logger.warning(f"Foundry scene creation failed (non-blocking): {e}")
            return None

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Convert a location name to a safe filename."""
        # Replace spaces and special chars with underscores
        safe = "".join(c if c.isalnum() or c in "- " else "" for c in name)
        safe = safe.strip().replace(" ", "_").lower()
        return safe or "unnamed_map"
