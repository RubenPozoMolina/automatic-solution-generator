import sys
from unittest.mock import patch

import main as main_module
from src.errors import SolutionGenerationError


def run_main(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "-c", "config.yaml"])
    return main_module.main()


def test_main_returns_zero_when_generation_succeeds(monkeypatch):
    with patch("main.LogUtils"), \
         patch("main.ConfigUtils") as config_utils, \
         patch("main.AutomaticSolutionGenerator") as generator_class:
        config_utils.return_value.load_config.return_value = {"project_path": "project"}

        assert run_main(monkeypatch) == 0
        generator_class.return_value.generate_solution.assert_called_once()


def test_main_returns_one_when_generation_fails(monkeypatch):
    with patch("main.LogUtils"), \
         patch("main.ConfigUtils") as config_utils, \
         patch("main.AutomaticSolutionGenerator") as generator_class:
        config_utils.return_value.load_config.return_value = {"project_path": "project"}
        generator_class.return_value.generate_solution.side_effect = SolutionGenerationError("boom")

        assert run_main(monkeypatch) == 1
