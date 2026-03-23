"""Tests for SOUL identity layer and Skills pluggable system."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from arch_review.squad.memory import AgentMemory, SquadMemory, _SOULS, _default_soul
from arch_review.skills import SkillRegistry, BUILTIN_SKILLS, Skill


# ── SOUL tests ────────────────────────────────────────────────────────────────

class TestSOUL:
    """Every agent must have a complete SOUL with all required sections."""

    REQUIRED_SOUL_AGENTS = [
        "security_agent", "reliability_agent", "cost_agent",
        "observability_agent", "scalability_agent", "performance_agent",
        "maintainability_agent", "synthesizer_agent", "manager_agent",
    ]

    REQUIRED_SECTIONS = ["Identity", "Analytical Style", "Known Biases", "Tone"]

    def test_all_agents_have_soul_template(self) -> None:
        for agent in self.REQUIRED_SOUL_AGENTS:
            assert agent in _SOULS, f"Missing SOUL for {agent}"

    def test_all_souls_have_required_sections(self) -> None:
        for agent, soul in _SOULS.items():
            for section in self.REQUIRED_SECTIONS:
                assert section in soul, f"{agent} SOUL missing section: {section}"

    def test_all_souls_have_separator(self) -> None:
        """--- separator divides fixed SOUL from evolving lessons."""
        for agent, soul in _SOULS.items():
            assert "---" in soul, f"{agent} SOUL missing --- separator"

    def test_all_souls_have_codename(self) -> None:
        for agent, soul in _SOULS.items():
            assert "Codename:" in soul, f"{agent} SOUL missing Codename"

    def test_all_souls_have_signature_questions(self) -> None:
        for agent, soul in _SOULS.items():
            assert "Signature Questions" in soul, f"{agent} SOUL missing Signature Questions"

    def test_soul_persists_to_disk(self, tmp_path: Path) -> None:
        mem = AgentMemory("security_agent", tmp_path)
        content = mem.read()
        assert "The Adversary" in content
        assert "Identity" in content

    def test_get_soul_section_returns_only_identity(self, tmp_path: Path) -> None:
        mem = AgentMemory("security_agent", tmp_path)
        soul = mem.get_soul_section()
        assert "Identity" in soul
        assert "Lessons Learned" not in soul

    def test_get_lessons_section_returns_only_lessons(self, tmp_path: Path) -> None:
        mem = AgentMemory("security_agent", tmp_path)
        mem.append_lesson("Test lesson", "Test context")
        lessons = mem.get_lessons_section()
        assert "Test lesson" in lessons
        assert "The Adversary" not in lessons

    def test_new_agents_get_soul_on_init(self, tmp_path: Path) -> None:
        for agent in self.REQUIRED_SOUL_AGENTS:
            mem = AgentMemory(agent, tmp_path)
            content = mem.read()
            assert len(content) > 200, f"{agent} SOUL too short"

    def test_default_soul_for_unknown_agent(self, tmp_path: Path) -> None:
        mem = AgentMemory("custom_agent_xyz", tmp_path)
        content = mem.read()
        assert "Custom Agent Xyz" in content
        assert "---" in content

    def test_squad_soul_has_all_9_agents(self) -> None:
        mem_dir = None
        # Just test the template directly
        from arch_review.squad.memory import _SQUAD_SOUL
        for agent in ["Security", "Reliability", "Cost", "Observability",
                      "Scalability", "Performance", "Maintainability",
                      "Synthesizer", "Manager"]:
            assert agent in _SQUAD_SOUL, f"Squad SOUL missing {agent}"

    def test_soul_specialization_history_in_all(self) -> None:
        for agent, soul in _SOULS.items():
            assert "Specialization History" in soul, \
                f"{agent} SOUL missing Specialization History"


# ── SkillRegistry tests ───────────────────────────────────────────────────────

class TestSkillRegistry:

    def test_list_available_returns_all_builtins(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        available = registry.list_available()
        names = [s.name for s in available]
        for builtin in BUILTIN_SKILLS:
            assert builtin in names

    def test_install_database_skill(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        meta = registry.install("database")
        assert meta.name == "database"
        assert meta.installed is True
        assert (tmp_path / "database" / "skill.json").exists()
        assert (tmp_path / "database" / "soul.md").exists()
        assert (tmp_path / "database" / "system.txt").exists()
        assert (tmp_path / "database" / "prompt.py").exists()

    def test_install_all_builtin_skills(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        for name in BUILTIN_SKILLS:
            meta = registry.install(name)
            assert meta.installed is True
            assert meta.agent_key.endswith("_agent")

    def test_install_unknown_skill_raises(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        with pytest.raises(ValueError, match="Unknown skill"):
            registry.install("flying-pigs")

    def test_install_twice_raises(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        registry.install("database")
        with pytest.raises(FileExistsError):
            registry.install("database")

    def test_is_installed(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        assert not registry.is_installed("database")
        registry.install("database")
        assert registry.is_installed("database")

    def test_remove_skill(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        registry.install("database")
        assert registry.remove("database") is True
        assert not registry.is_installed("database")

    def test_remove_nonexistent_returns_false(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        assert registry.remove("does-not-exist") is False

    def test_list_installed_empty(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        assert registry.list_installed() == []

    def test_list_installed_after_install(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        registry.install("database")
        registry.install("api-design")
        installed = registry.list_installed()
        names = [s.name for s in installed]
        assert "database" in names
        assert "api-design" in names

    def test_list_available_marks_installed_correctly(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        registry.install("database")
        available = registry.list_available()
        db = next(s for s in available if s.name == "database")
        api = next(s for s in available if s.name == "api-design")
        assert db.installed is True
        assert api.installed is False


class TestSkillLoading:

    def test_load_database_skill(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        registry.install("database")
        skill = registry.load("database")
        assert isinstance(skill, Skill)
        assert skill.agent_key == "database_agent"
        assert len(skill.soul) > 100
        assert len(skill.system_prompt) > 50
        assert callable(skill.build_prompt)

    def test_loaded_skill_build_prompt_works(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        registry.install("database")
        skill = registry.load("database")
        prompt = skill.build_prompt(
            "PostgreSQL + Redis + S3 architecture",
            "E-commerce platform",
            "",
            "",
        )
        assert len(prompt) > 100
        assert "findings" in prompt.lower() or "database" in prompt.lower()

    def test_skill_as_agent_tuple(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        registry.install("api-design")
        skill = registry.load("api-design")
        agent_tuple = skill.as_agent_tuple
        assert len(agent_tuple) == 3
        name, system, prompt_fn = agent_tuple
        assert name == "api_design_agent"
        assert callable(prompt_fn)

    def test_load_nonexistent_raises(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        with pytest.raises(FileNotFoundError):
            registry.load("database")

    def test_load_all_installed(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        registry.install("database")
        registry.install("ml-ops")
        skills = registry.load_all_installed()
        assert len(skills) == 2
        keys = [s.agent_key for s in skills]
        assert "database_agent" in keys
        assert "ml_ops_agent" in keys

    def test_all_builtin_skills_loadable(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        for name in BUILTIN_SKILLS:
            registry.install(name)
            skill = registry.load(name)
            assert skill.meta.name == name
            assert callable(skill.build_prompt)
            # Verify prompt builds without error
            result = skill.build_prompt("test arch", "test ctx", "", "")
            assert len(result) > 50

    def test_soul_content_in_loaded_skill(self, tmp_path: Path) -> None:
        registry = SkillRegistry(tmp_path)
        registry.install("data-privacy")
        skill = registry.load("data-privacy")
        assert "LGPD" in skill.soul or "Privacy" in skill.soul


class TestSkillSquadIntegration:

    def test_squad_loads_installed_skills(self, tmp_path: Path) -> None:
        from arch_review.skills import SkillRegistry
        registry = SkillRegistry(tmp_path / "skills")
        registry.install("database")

        from arch_review.squad.squad import ReviewSquad
        from unittest.mock import patch
        with patch("arch_review.skills.SKILLS_DIR", tmp_path / "skills"):
            sq = ReviewSquad(memory_dir=tmp_path / "memory")
            agent_keys = [name for name, _, _ in sq._active_agents]
            assert "database_agent" in agent_keys

    def test_squad_with_no_skills_uses_base_7(self, tmp_path: Path) -> None:
        from arch_review.squad.squad import ReviewSquad
        from unittest.mock import patch
        # Empty skills dir
        (tmp_path / "skills").mkdir()
        with patch("arch_review.skills.SKILLS_DIR", tmp_path / "skills"):
            sq = ReviewSquad(memory_dir=tmp_path / "memory")
            assert len(sq._active_agents) == 7
