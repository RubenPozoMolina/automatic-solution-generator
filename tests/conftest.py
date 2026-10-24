from unittest.mock import MagicMock

import pytest


@pytest.fixture
def logger():
    return MagicMock()
