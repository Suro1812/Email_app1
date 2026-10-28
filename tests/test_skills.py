"""Tests for app/agent/skills/__init__.py"""

import pytest
from unittest.mock import patch

from app.agent.skills import _normalize_skill_name, list_skills, load_skill


class TestNormalizeSkillName:
    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _normalize_skill_name("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _normalize_skill_name("   ")

    def test_adds_txt_extension_when_none(self):
        assert _normalize_skill_name("classifier") == "classifier.txt"

    def test_preserves_txt_extension(self):
        assert _normalize_skill_name("classifier.txt") == "classifier.txt"

    def test_preserves_md_extension(self):
        assert _normalize_skill_name("summarizer.md") == "summarizer.md"

    def test_strips_surrounding_whitespace(self):
        assert _normalize_skill_name("  classifier  ") == "classifier.txt"


class TestListSkills:
    def test_returns_sorted_stems(self, tmp_path):
        (tmp_path / "zebra.txt").write_text("z")
        (tmp_path / "apple.md").write_text("a")
        (tmp_path / "ignored.py").write_text("py")

        with patch("app.agent.skills.SKILLS_DIR", tmp_path):
            result = list_skills()

        assert result == ["apple", "zebra"]

    def test_empty_directory(self, tmp_path):
        with patch("app.agent.skills.SKILLS_DIR", tmp_path):
            assert list_skills() == []

    def test_ignores_subdirectories(self, tmp_path):
        (tmp_path / "real.txt").write_text("skill")
        (tmp_path / "subdir").mkdir()

        with patch("app.agent.skills.SKILLS_DIR", tmp_path):
            assert list_skills() == ["real"]


class TestLoadSkill:
    def test_loads_txt_file_and_strips(self, tmp_path):
        (tmp_path / "classifier.txt").write_text("  You are a classifier.  ")
        with patch("app.agent.skills.SKILLS_DIR", tmp_path):
            assert load_skill("classifier") == "You are a classifier."

    def test_loads_md_file(self, tmp_path):
        (tmp_path / "summarizer.md").write_text("Summarize emails.")
        with patch("app.agent.skills.SKILLS_DIR", tmp_path):
            assert load_skill("summarizer") == "Summarize emails."

    def test_explicit_extension_loads_file(self, tmp_path):
        (tmp_path / "classifier.txt").write_text("Classify.")
        with patch("app.agent.skills.SKILLS_DIR", tmp_path):
            assert load_skill("classifier.txt") == "Classify."

    def test_raises_file_not_found_for_missing_skill(self, tmp_path):
        with patch("app.agent.skills.SKILLS_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="not found"):
                load_skill("nonexistent")

    def test_error_message_lists_available_skills(self, tmp_path):
        (tmp_path / "available.txt").write_text("skill")
        with patch("app.agent.skills.SKILLS_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="available"):
                load_skill("missing")
