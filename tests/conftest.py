import pytest

from app.location.assistant import get_location
from app.main import app


@pytest.fixture(autouse=True)
def no_location_assist():
    """Location tools are off unless a test installs its own LocationAssistant."""
    app.dependency_overrides[get_location] = lambda: None
    yield
    app.dependency_overrides.pop(get_location, None)
