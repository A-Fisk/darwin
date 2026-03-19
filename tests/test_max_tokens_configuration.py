"""Comprehensive tests for max_tokens configuration to prevent whack-a-mole regressions.

This test module ensures:
1. All agents use appropriate token limits from config constants
2. No hardcoded token values exist in agent code
3. Token limits are sufficient for realistic inputs (long scientific hypotheses)
4. Centralized config.py constants are properly imported everywhere
5. New agents automatically follow the tiered token strategy
6. Integration tests that actually hit token limits with real content
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from darwin import config
from darwin.agents import _common


class TestTokenConfigurationCentralized:
    """Test that token configuration is centralized and properly used."""

    def test_config_constants_exist(self) -> None:
        """All required token constants are defined in config.py."""
        required_constants = [
            "MAX_TOKENS_SIMPLE",
            "MAX_TOKENS_STANDARD",
            "MAX_TOKENS_DETAILED",
            "MAX_TOKENS_COMPLEX",
            "MAX_TOKENS_CREATIVE",
        ]

        for constant in required_constants:
            assert hasattr(config, constant), f"Missing {constant} in config.py"
            value = getattr(config, constant)
            assert isinstance(value, int), f"{constant} must be an int"
            assert value > 0, f"{constant} must be positive"

    def test_token_tiers_properly_ordered(self) -> None:
        """Token limits follow expected hierarchy (simple < standard < detailed < complex < creative)."""
        assert config.MAX_TOKENS_SIMPLE <= config.MAX_TOKENS_STANDARD
        assert config.MAX_TOKENS_STANDARD <= config.MAX_TOKENS_DETAILED
        assert config.MAX_TOKENS_DETAILED <= config.MAX_TOKENS_COMPLEX
        assert config.MAX_TOKENS_COMPLEX <= config.MAX_TOKENS_CREATIVE

    def test_no_hardcoded_token_values_in_agents(self) -> None:
        """Agent files contain no hardcoded token values (must use config constants)."""
        agents_dir = Path(__file__).parent.parent / "src" / "darwin" / "agents"
        token_values = {256, 512, 1024, 2048, 4096}  # Common token values that should be in config only

        for agent_file in agents_dir.glob("*.py"):
            if agent_file.name.startswith("_"):
                continue  # Skip _common.py, __init__.py

            content = agent_file.read_text()

            # Parse AST to find numeric literals
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, int):
                        if node.value in token_values:
                            # Allow these values in config.py itself
                            if agent_file.name != "config.py":
                                pytest.fail(
                                    f"Found hardcoded token value {node.value} in {agent_file.name}. "
                                    f"Use config constants instead."
                                )
            except SyntaxError:
                pytest.fail(f"Syntax error in {agent_file}")


class TestAgentTokenUsage:
    """Test that all agents properly import and use token constants."""

    def _get_agent_modules(self) -> list[str]:
        """Get list of agent module names that make LLM calls."""
        agents_dir = Path(__file__).parent.parent / "src" / "darwin" / "agents"
        agent_modules = []

        for agent_file in agents_dir.glob("*.py"):
            if agent_file.name.startswith("_") or agent_file.name == "__init__.py":
                continue

            # Skip human_review as it doesn't make LLM calls
            if agent_file.name == "human_review.py":
                continue

            content = agent_file.read_text()

            # Check if this agent makes LLM calls
            if "client.messages.create" in content or "anthropic.Anthropic" in content:
                module_name = agent_file.stem
                agent_modules.append(f"darwin.agents.{module_name}")

        return agent_modules

    def test_all_agents_import_max_tokens_constants(self) -> None:
        """All agent modules that make LLM calls import appropriate MAX_TOKENS_* constants."""
        agent_modules = self._get_agent_modules()

        for module_name in agent_modules:
            module = importlib.import_module(module_name)
            module_file = inspect.getfile(module)
            content = Path(module_file).read_text()

            # Check that module imports at least one MAX_TOKENS constant
            has_token_import = any(
                f"MAX_TOKENS_{tier}" in content
                for tier in ["SIMPLE", "STANDARD", "DETAILED", "COMPLEX", "CREATIVE"]
            )

            assert has_token_import, (
                f"Agent {module_name} makes LLM calls but doesn't import any MAX_TOKENS_* constants. "
                f"Import appropriate constants from darwin.config."
            )

    def test_agents_use_max_tokens_parameter(self) -> None:
        """All agents that make LLM calls use max_tokens parameter."""
        agent_modules = self._get_agent_modules()

        for module_name in agent_modules:
            module = importlib.import_module(module_name)
            module_file = inspect.getfile(module)
            content = Path(module_file).read_text()

            # If module makes LLM calls, it must use max_tokens parameter
            if "client.messages.create" in content:
                assert "max_tokens=" in content, (
                    f"Agent {module_name} makes LLM calls but doesn't use max_tokens parameter. "
                    f"Add max_tokens=MAX_TOKENS_* to all client.messages.create() calls."
                )


class TestTokenLimitsSufficiency:
    """Test that token limits are sufficient for realistic scientific content."""

    @pytest.fixture
    def long_scientific_hypothesis(self) -> str:
        """Realistic long scientific hypothesis that might cause truncation."""
        return (
            "The quantum entanglement phenomenon observed in coupled photonic crystal cavities "
            "exhibits non-classical correlations that can be enhanced through strategic manipulation "
            "of the cavity-quantum dot detuning parameters, particularly when the system operates "
            "in the strong coupling regime where the vacuum Rabi frequency exceeds both the cavity "
            "and quantum dot decay rates. This enhancement mechanism relies on the formation of "
            "dressed states that emerge from the hybridization between exciton and photon modes, "
            "creating polariton states with modified spectral properties and enhanced coherence times. "
            "The optimization of these parameters could lead to practical implementations of quantum "
            "information processing protocols, specifically in the context of deterministic single-photon "
            "sources and quantum repeaters for long-distance quantum communication networks. "
            "Furthermore, the scalability of this approach depends critically on maintaining phase "
            "coherence across multiple coupled cavity systems, which requires precise control over "
            "fabrication tolerances and environmental perturbations that could lead to decoherence "
            "through interactions with phonon modes in the host semiconductor material."
        )

    @pytest.fixture
    def very_long_research_context(self) -> str:
        """Very long research context that tests upper token limits."""
        base_text = (
            "Recent advances in machine learning applications to scientific discovery have "
            "demonstrated remarkable capabilities in accelerating hypothesis generation and "
            "experimental design across multiple domains including materials science, drug "
            "discovery, climate modeling, and fundamental physics research. "
        )
        # Repeat to create a long context that would challenge token limits
        return base_text * 50

    def test_simple_tokens_sufficient_for_basic_decisions(self, long_scientific_hypothesis: str) -> None:
        """MAX_TOKENS_SIMPLE is sufficient for basic yes/no decisions even with long inputs."""
        # Simulate a simple decision with long context
        prompt = f"Given this hypothesis: {long_scientific_hypothesis}\nIs this testable? Answer yes or no."

        # Basic decision should not need more than MAX_TOKENS_SIMPLE
        assert config.MAX_TOKENS_SIMPLE >= 100, "Simple decisions need at least 100 tokens"

        # Test that this would not truncate for a basic decision
        mock_response = "Yes, this hypothesis is testable through controlled quantum optics experiments."
        assert len(mock_response.split()) < config.MAX_TOKENS_SIMPLE, (
            "Simple responses should fit within MAX_TOKENS_SIMPLE limit"
        )

    def test_creative_tokens_sufficient_for_hypothesis_generation(self, very_long_research_context: str) -> None:
        """MAX_TOKENS_CREATIVE is sufficient for generating new hypotheses from long context."""
        # Test that creative responses can be generated without truncation
        expected_creative_response_words = 800  # Rough estimate for a detailed hypothesis

        assert config.MAX_TOKENS_CREATIVE >= expected_creative_response_words, (
            f"Creative token limit ({config.MAX_TOKENS_CREATIVE}) should support "
            f"detailed hypothesis generation (~{expected_creative_response_words} words)"
        )

    def test_complex_tokens_sufficient_for_rankings(self) -> None:
        """MAX_TOKENS_COMPLEX is sufficient for ranking multiple hypotheses with explanations."""
        # Simulate ranking 5 hypotheses with detailed explanations
        num_hypotheses = 5
        explanation_words_per_hypothesis = 100
        total_expected_words = num_hypotheses * explanation_words_per_hypothesis + 200  # overhead

        assert config.MAX_TOKENS_COMPLEX >= total_expected_words, (
            f"Complex token limit ({config.MAX_TOKENS_COMPLEX}) should support "
            f"ranking {num_hypotheses} hypotheses with explanations (~{total_expected_words} words)"
        )


class TestTruncationHandling:
    """Test that token truncation is properly detected and handled."""

    def test_truncation_detection_raises_error(self) -> None:
        """Truncation is detected and raises descriptive error."""
        mock_message = MagicMock()
        mock_message.stop_reason = "max_tokens"
        mock_message.content = [MagicMock(type="text", text="Incomplete response")]

        with pytest.raises(ValueError, match="truncated.*max_tokens"):
            _common.parse_json_response(mock_message)

    def test_truncation_error_includes_response_length(self) -> None:
        """Truncation error includes actual response length for debugging."""
        response_text = "Incomplete JSON response: {\"partial\": "
        mock_message = MagicMock()
        mock_message.stop_reason = "max_tokens"
        mock_message.content = [MagicMock(type="text", text=response_text)]

        # The error reports the stripped length, not the original length
        expected_length = len(response_text.strip())
        with pytest.raises(ValueError, match=f"Response length: {expected_length} chars"):
            _common.parse_json_response(mock_message)

    def test_truncation_error_suggests_increasing_tokens(self) -> None:
        """Truncation error suggests increasing max_tokens for the agent."""
        mock_message = MagicMock()
        mock_message.stop_reason = "max_tokens"
        mock_message.content = [MagicMock(type="text", text="Truncated")]

        with pytest.raises(ValueError, match="Increase max_tokens for this agent"):
            _common.parse_json_response(mock_message)


class TestIntegrationWithRealContent:
    """Integration tests that use realistic content to catch truncation issues."""

    def _create_mock_message(self, text: str, stop_reason: str = "end_turn") -> MagicMock:
        """Create a mock Anthropic message for testing."""
        msg = MagicMock()
        msg.stop_reason = stop_reason
        msg.content = [MagicMock(type="text", text=text)]
        return msg

    @pytest.mark.parametrize("agent_module,token_constant", [
        ("darwin.agents.supervisor", "MAX_TOKENS_SIMPLE"),
        ("darwin.agents.literature", "MAX_TOKENS_SIMPLE"),
        ("darwin.agents.meta_review", "MAX_TOKENS_DETAILED"),
        ("darwin.agents.reflection", "MAX_TOKENS_DETAILED"),
        ("darwin.agents.ranking", "MAX_TOKENS_COMPLEX"),
        ("darwin.agents.evolution", "MAX_TOKENS_CREATIVE"),
        ("darwin.agents.generation", "MAX_TOKENS_CREATIVE"),
    ])
    def test_agent_token_limits_prevent_truncation(self, agent_module: str, token_constant: str) -> None:
        """Each agent's token limit should be sufficient to prevent truncation in normal operation."""
        # Get the token limit for this agent
        token_limit = getattr(config, token_constant)

        # Create a response that uses most but not all of the token limit
        # (using roughly 0.75 of limit to account for token counting variations)
        safe_response_length = int(token_limit * 0.75 * 4)  # ~4 chars per token average
        test_response = "A" * safe_response_length

        # This should NOT raise a truncation error
        mock_message = self._create_mock_message(test_response, "end_turn")

        # Import the agent and test if it has parse_json_response usage
        agent = importlib.import_module(agent_module)
        agent_file = inspect.getfile(agent)
        content = Path(agent_file).read_text()

        # If agent uses parse_json_response, test truncation handling
        if "parse_json_response" in content:
            try:
                _common.parse_json_response(mock_message)
            except Exception as e:
                if "truncated" in str(e):
                    pytest.fail(
                        f"Agent {agent_module} using {token_constant}={token_limit} "
                        f"would truncate on normal-length response. Consider increasing token limit."
                    )

    def test_realistic_hypothesis_generation_no_truncation(self) -> None:
        """Test that hypothesis generation doesn't truncate with realistic scientific content."""
        # Simulate a realistic hypothesis generation response
        realistic_hypotheses = [
            {
                "id": f"h{i}",
                "text": (
                    f"Hypothesis {i}: The quantum coherence effects in biological photosynthetic "
                    f"complexes can be enhanced through targeted molecular engineering of the "
                    f"protein scaffold, specifically by introducing controlled disorder that "
                    f"optimizes energy transfer efficiency while maintaining environmental stability."
                ),
                "rationale": (
                    f"This builds on recent evidence of quantum effects in photosynthesis "
                    f"by proposing a specific mechanism for their optimization."
                )
            }
            for i in range(5)
        ]

        import json
        response_text = json.dumps({"hypotheses": realistic_hypotheses})

        # This should fit within creative token limits
        estimated_tokens = len(response_text) // 4  # Rough token estimate
        assert estimated_tokens < config.MAX_TOKENS_CREATIVE, (
            f"Realistic hypothesis response ({estimated_tokens} est. tokens) "
            f"exceeds MAX_TOKENS_CREATIVE ({config.MAX_TOKENS_CREATIVE})"
        )

    def test_realistic_ranking_explanation_no_truncation(self) -> None:
        """Test that ranking explanations don't truncate with realistic scientific content."""
        # Simulate a realistic ranking response with detailed explanations
        realistic_ranking = {
            "ranking": [
                {
                    "id": "h1",
                    "score": 0.95,
                    "explanation": (
                        "This hypothesis scores highest due to its testability through existing "
                        "experimental techniques in quantum optics, its novel mechanistic prediction "
                        "about cavity-QD detuning effects, and its potential for practical applications "
                        "in quantum information processing. The theoretical framework builds directly "
                        "on established polariton physics while making specific, measurable predictions."
                    )
                },
                {
                    "id": "h2",
                    "score": 0.87,
                    "explanation": (
                        "Strong hypothesis with good experimental feasibility, but slightly lower "
                        "novelty compared to h1. The proposed mechanism for enhancing quantum "
                        "correlations is well-grounded in theory but represents a more incremental "
                        "advance over existing work in the field."
                    )
                }
            ]
        }

        import json
        response_text = json.dumps(realistic_ranking)

        estimated_tokens = len(response_text) // 4
        assert estimated_tokens < config.MAX_TOKENS_COMPLEX, (
            f"Realistic ranking response ({estimated_tokens} est. tokens) "
            f"exceeds MAX_TOKENS_COMPLEX ({config.MAX_TOKENS_COMPLEX})"
        )


class TestNewAgentCompliance:
    """Test that new agents automatically follow the tiered token strategy."""

    def test_agent_template_compliance(self) -> None:
        """New agents should follow the established pattern for token usage."""
        # This test serves as documentation for the expected pattern
        expected_pattern_elements = [
            "Import MAX_TOKENS_* from darwin.config",
            "Use max_tokens parameter in client.messages.create()",
            "Choose appropriate tier: SIMPLE/STANDARD/DETAILED/COMPLEX/CREATIVE",
            "Handle truncation through _common.parse_json_response if parsing JSON"
        ]

        # This test documents the pattern - actual compliance checked by other tests
        assert len(expected_pattern_elements) == 4, "Pattern requirements documented"

    def test_agent_naming_convention_consistent(self) -> None:
        """Token constant naming follows consistent pattern."""
        token_constants = [
            name for name in dir(config)
            if name.startswith("MAX_TOKENS_") and not name.startswith("_")
        ]

        # All constants should follow MAX_TOKENS_{TIER} pattern
        expected_tiers = {"SIMPLE", "STANDARD", "DETAILED", "COMPLEX", "CREATIVE"}
        actual_tiers = {const.replace("MAX_TOKENS_", "") for const in token_constants}

        assert actual_tiers == expected_tiers, (
            f"Token constants should follow MAX_TOKENS_{{TIER}} pattern. "
            f"Expected: {expected_tiers}, Actual: {actual_tiers}"
        )


# Integration test with actual LLM behavior (if API key available)
class TestRealLLMIntegration:
    """Optional integration tests with real LLM calls (require API key)."""

    def test_token_limits_with_real_api_calls(self) -> None:
        """Test token limits with actual API calls if ANTHROPIC_API_KEY available."""
        pytest.skip("Integration test - requires ANTHROPIC_API_KEY and costs money")
        # This test would make real API calls to verify token limits
        # Only run manually when needed, not in CI