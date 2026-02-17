"""
Smoke tests for the CartographerAgent (agents/cartographer.py).

Tests use mock AI clients — no live Gemini or Foundry connection needed.
"""

import sys
import os
import asyncio
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Mock Helpers
# ---------------------------------------------------------------------------

class MockImagePart:
    """Simulates a Gemini image response part."""
    def __init__(self, image_bytes, mime_type="image/png"):
        self.inline_data = MagicMock()
        self.inline_data.mime_type = mime_type
        self.inline_data.data = image_bytes


class MockTextPart:
    """Simulates a Gemini text response part."""
    def __init__(self, text):
        self.text = text
        self.inline_data = None


class MockCandidate:
    """Simulates a Gemini response candidate."""
    def __init__(self, parts):
        self.content = MagicMock()
        self.content.parts = parts


class MockGeminiResponse:
    """Simulates a Gemini response."""
    def __init__(self, text=None, image_bytes=None):
        self.text = text or ""
        parts = []
        if text:
            parts.append(MockTextPart(text))
        if image_bytes:
            parts.append(MockImagePart(image_bytes))
        self.candidates = [MockCandidate(parts)] if parts else []


class MockGeminiClient:
    """Mock Gemini client that returns canned responses."""
    def __init__(self, responses=None):
        self._responses = responses or []
        self._call_count = 0

    @property
    def aio(self):
        return self

    @property
    def models(self):
        return self

    async def generate_content(self, **kwargs):
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = MockGeminiResponse(text="Fallback response")
        self._call_count += 1
        return resp


class MockFoundryClient:
    """Mock FoundryClient."""
    def __init__(self, connected=True):
        self._connected = connected
        self._created_entities = []

    @property
    def is_connected(self):
        return self._connected

    def create_entity(self, entity_type, data):
        self._created_entities.append((entity_type, data))
        return {"uuid": "test-uuid-123", "name": data.get("name", "?")}


class MockVault:
    """Mock VaultManager."""
    def list_files(self, subfolder):
        return []
    def read_file(self, path):
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCartographerImports(unittest.TestCase):
    """Test that the cartographer module imports correctly."""

    def test_import_module(self):
        from agents.cartographer import CartographerAgent
        self.assertTrue(CartographerAgent is not None)

    def test_import_constants(self):
        from agents.cartographer import STYLE_PROMPT, PROMPT_ENGINEER_SYSTEM
        self.assertIn("top-down", STYLE_PROMPT)
        self.assertIn("battlemap", PROMPT_ENGINEER_SYSTEM.lower())


class TestCartographerInit(unittest.TestCase):
    """Test CartographerAgent initialization."""

    def test_default_init(self):
        from agents.cartographer import CartographerAgent
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CartographerAgent(
                client=MockGeminiClient(),
                foundry=MockFoundryClient(),
                vault=MockVault(),
                output_dir=tmpdir,
            )
            self.assertIsNotNone(agent)
            self.assertEqual(agent.model_id, "gemini-2.0-flash")

    def test_output_dir_created(self):
        from agents.cartographer import CartographerAgent
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_maps")
            agent = CartographerAgent(
                client=MockGeminiClient(),
                foundry=MockFoundryClient(),
                vault=MockVault(),
                output_dir=output_path,
            )
            self.assertTrue(os.path.isdir(output_path))


class TestCartographerSanitizeFilename(unittest.TestCase):
    """Test filename sanitization."""

    def test_basic_name(self):
        from agents.cartographer import CartographerAgent
        self.assertEqual(CartographerAgent._sanitize_filename("Forest Path"), "forest_path")

    def test_special_chars(self):
        from agents.cartographer import CartographerAgent
        self.assertEqual(
            CartographerAgent._sanitize_filename("Zhentarim's Warehouse [30x20]"),
            "zhentarims_warehouse_30x20"
        )

    def test_empty_name(self):
        from agents.cartographer import CartographerAgent
        self.assertEqual(CartographerAgent._sanitize_filename(""), "unnamed_map")

    def test_name_with_dashes(self):
        from agents.cartographer import CartographerAgent
        result = CartographerAgent._sanitize_filename("Dark-Forest Clearing")
        self.assertIn("dark", result)
        self.assertIn("forest", result)


class TestCartographerPromptCrafting(unittest.TestCase):
    """Test image prompt generation."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch('agents.cartographer.gemini_limiter')
    def test_craft_prompt_returns_string(self, mock_limiter):
        mock_limiter.acquire = AsyncMock()

        from agents.cartographer import CartographerAgent

        prompt_response = MockGeminiResponse(
            text="A detailed top-down forest clearing with ancient ruins and a stream"
        )
        mock_client = MockGeminiClient(responses=[prompt_response])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CartographerAgent(
                client=mock_client,
                foundry=MockFoundryClient(),
                vault=MockVault(),
                output_dir=tmpdir,
            )

            result = self._run(agent._craft_image_prompt(
                "Forest Ruins", "Ancient ruins in a forest clearing", "30x20", "dim"
            ))

            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 50)
            # Should include the style anchor
            self.assertIn("orthographic", result.lower())

    @patch('agents.cartographer.gemini_limiter')
    def test_craft_prompt_fallback_on_error(self, mock_limiter):
        """If prompt crafting fails, should use a reasonable fallback."""
        mock_limiter.acquire = AsyncMock(side_effect=Exception("API error"))

        from agents.cartographer import CartographerAgent

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CartographerAgent(
                client=MockGeminiClient(),
                foundry=MockFoundryClient(),
                vault=MockVault(),
                output_dir=tmpdir,
            )

            result = self._run(agent._craft_image_prompt(
                "Test Location", "A test location", "20x20", "bright"
            ))

            # Should still return a usable prompt
            self.assertIn("Test Location", result)
            self.assertIn("top-down", result.lower())


class TestCartographerImageGeneration(unittest.TestCase):
    """Test image generation."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch('agents.cartographer.gemini_limiter')
    def test_generate_image_returns_bytes(self, mock_limiter):
        mock_limiter.acquire = AsyncMock()

        from agents.cartographer import CartographerAgent

        # Create a mock response with image data
        fake_image = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # Fake PNG header
        image_response = MockGeminiResponse(image_bytes=fake_image)
        mock_client = MockGeminiClient(responses=[image_response])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CartographerAgent(
                client=mock_client,
                foundry=MockFoundryClient(),
                vault=MockVault(),
                output_dir=tmpdir,
            )

            result = self._run(agent._generate_image("A forest clearing"))
            self.assertIsNotNone(result)
            self.assertIsInstance(result, bytes)
            self.assertEqual(result, fake_image)

    @patch('agents.cartographer.gemini_limiter')
    def test_generate_image_returns_none_on_no_image(self, mock_limiter):
        mock_limiter.acquire = AsyncMock()

        from agents.cartographer import CartographerAgent

        # Response with text only, no image
        text_response = MockGeminiResponse(text="I cannot generate images")
        mock_client = MockGeminiClient(responses=[text_response])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CartographerAgent(
                client=mock_client,
                foundry=MockFoundryClient(),
                vault=MockVault(),
                output_dir=tmpdir,
            )

            result = self._run(agent._generate_image("A forest clearing"))
            self.assertIsNone(result)


class TestCartographerFullPipeline(unittest.TestCase):
    """Test the full generate_scene pipeline."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch('agents.cartographer.gemini_limiter')
    def test_generate_scene_success(self, mock_limiter):
        mock_limiter.acquire = AsyncMock()

        from agents.cartographer import CartographerAgent

        fake_image = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        prompt_response = MockGeminiResponse(text="Top-down forest clearing with stream")
        image_response = MockGeminiResponse(image_bytes=fake_image)
        mock_client = MockGeminiClient(responses=[prompt_response, image_response])
        mock_foundry = MockFoundryClient(connected=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CartographerAgent(
                client=mock_client,
                foundry=mock_foundry,
                vault=MockVault(),
                output_dir=tmpdir,
            )

            result = self._run(agent.generate_scene(
                location_name="Forest Clearing",
                description="A sun-dappled clearing with ancient stones",
                grid_size="30x20",
                lighting="bright",
            ))

            self.assertTrue(result["success"])
            self.assertEqual(result["scene_name"], "Forest Clearing")
            self.assertIn("forest_clearing.png", result["image_path"])
            self.assertEqual(result["error"], "")

            # Verify image was saved
            self.assertTrue(os.path.exists(result["image_path"]))

            # Verify Foundry scene was created
            self.assertEqual(len(mock_foundry._created_entities), 1)
            entity_type, data = mock_foundry._created_entities[0]
            self.assertEqual(entity_type, "Scene")
            self.assertEqual(data["name"], "Forest Clearing")

    @patch('agents.cartographer.gemini_limiter')
    def test_generate_scene_no_image(self, mock_limiter):
        mock_limiter.acquire = AsyncMock()

        from agents.cartographer import CartographerAgent

        prompt_response = MockGeminiResponse(text="A prompt")
        no_image_response = MockGeminiResponse(text="Sorry, I can't generate images")
        mock_client = MockGeminiClient(responses=[prompt_response, no_image_response])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CartographerAgent(
                client=mock_client,
                foundry=MockFoundryClient(),
                vault=MockVault(),
                output_dir=tmpdir,
            )

            result = self._run(agent.generate_scene(
                location_name="Test",
                description="Test location",
            ))

            self.assertFalse(result["success"])
            self.assertIn("no image data", result["error"].lower())

    @patch('agents.cartographer.gemini_limiter')
    def test_generate_scene_no_foundry(self, mock_limiter):
        """Scene should still succeed even if Foundry isn't connected."""
        mock_limiter.acquire = AsyncMock()

        from agents.cartographer import CartographerAgent

        fake_image = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        prompt_response = MockGeminiResponse(text="A prompt")
        image_response = MockGeminiResponse(image_bytes=fake_image)
        mock_client = MockGeminiClient(responses=[prompt_response, image_response])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = CartographerAgent(
                client=mock_client,
                foundry=MockFoundryClient(connected=False),
                vault=MockVault(),
                output_dir=tmpdir,
            )

            result = self._run(agent.generate_scene(
                location_name="Test Map",
                description="A test",
            ))

            # Image should be generated and saved
            self.assertTrue(result["success"])
            self.assertTrue(os.path.exists(result["image_path"]))


if __name__ == '__main__':
    unittest.main()
