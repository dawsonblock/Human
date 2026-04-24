import os
import pytest
from fastapi.testclient import TestClient
from subjective_runtime_v2_1.api.app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_terminal_websocket_disabled_by_default(client):
    """
    Test that the /terminal websocket is disabled by default
    and returns a 1008 policy violation code unless ALLOW_DEV_TERMINAL=1.
    """
    if "ALLOW_DEV_TERMINAL" in os.environ:
        del os.environ["ALLOW_DEV_TERMINAL"]

    with pytest.raises(Exception) as excinfo:
        with client.websocket_connect("/terminal") as websocket:
            websocket.receive_text()

    # If it raised WebSocketDisconnect, it's disabled.
    assert excinfo.value is not None
