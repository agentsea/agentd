from httpx import AsyncClient
from unittest.mock import patch
import pytest
from agentd.server import app
from agentd.recording import RecordingSession, RecordedEvent

@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Agent in the shell"}

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_info():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/info")
    assert response.status_code == 200
    assert "last_activity_ts" in response.json()
    assert "screen_size" in response.json()
    assert "os_info" in response.json()
    assert "code_version" in response.json()

@pytest.mark.asyncio
async def test_screen_size():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/screen_size")
    assert response.status_code == 200
    assert "x" in response.json()
    assert "y" in response.json()

@pytest.mark.asyncio
async def test_mouse_coordinates():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/mouse_coordinates")
    assert response.status_code == 200
    assert "x" in response.json()
    assert "y" in response.json()

@pytest.mark.asyncio
async def test_system_usage():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/system_usage")
    assert response.status_code == 200
    assert "cpu_percent" in response.json()
    assert "memory_percent" in response.json()
    assert "disk_percent" in response.json()

@pytest.mark.asyncio
async def test_open_url():
    with patch('agentd.server.is_chromium_running', return_value=False), \
         patch('agentd.server.gracefully_terminate_chromium') as mock_terminate, \
         patch('agentd.server.is_chromium_window_open', return_value=True), \
         patch('agentd.server.subprocess.Popen') as mock_popen:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/open_url", json={"url": "http://example.com"})
        
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        mock_terminate.assert_not_called()
        mock_popen.assert_called_once()

@pytest.mark.asyncio
async def test_move_mouse():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/move_mouse", json={"x": 100, "y": 200, "duration": 1.0, "tween": "linear"})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

@pytest.mark.asyncio
async def test_click():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/click", json={"button": "left"})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

@pytest.mark.asyncio
async def test_double_click():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/double_click")
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

@pytest.mark.asyncio
async def test_type_text():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/type_text", json={"text": "hello", "min_interval": 0.05, "max_interval": 0.25})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

@pytest.mark.asyncio
async def test_press_key():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/press_key", json={"key": "enter"})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

@pytest.mark.asyncio
async def test_scroll():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/scroll", json={"clicks": 3})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

@pytest.mark.asyncio
async def test_drag_mouse():
    with patch('agentd.server.pyautogui.dragTo') as mock_dragTo:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/drag_mouse", json={"x": 300, "y": 400})
        
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        mock_dragTo.assert_called_once_with(300, 400)
        
@pytest.mark.asyncio
async def test_take_screenshot():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/screenshot")
    assert response.status_code == 200
    assert "status" in response.json()
    assert response.json()["status"] == "success"
    assert "image" in response.json()
    assert "file_path" in response.json()

@pytest.fixture
def mocker():
    from unittest.mock import MagicMock
    return MagicMock()

@pytest.mark.asyncio
async def test_recording_workflow(mocker):
    async with AsyncClient(app=app, base_url="http://test") as ac:

        # Test start recording
        description = "Test recording"
        response_start = await ac.post("/recordings", json={"description": description})
        assert response_start.status_code == 200
        assert "session_id" in response_start.json()
        session_id = response_start.json()["session_id"]

        # Test list recordings
        mocker.patch('agentd.server.list_recordings', return_value={"recordings": []})
        response_list = await ac.get("/recordings")
        assert response_list.status_code == 200
        recordings_list = response_list.json()["recordings"]
        assert session_id in recordings_list

        # Test stop recording
        mocker.patch('agentd.server.sessions.get', return_value=RecordingSession(session_id, "Test"))
        mocker.patch('agentd.server.RecordingSession.stop', return_value=None)
        mocker.patch('agentd.server.RecordingSession.save_to_file', return_value="path/to/file")
        response_stop = await ac.post(f"/recordings/{session_id}/stop")
        assert response_stop.status_code == 200

        # Test get recording
        response_get = await ac.get(f"/recordings/{session_id}")
        assert response_get.status_code == 200
        assert "id" in response_get.json()
        assert "end_time" in response_get.json()

        # Test delete event
        event_id = "test_event"
        session = RecordingSession(session_id, "Test")
        mocker.patch('agentd.server.sessions.get', return_value=session)
        mocker.patch('agentd.server.RecordingSession.delete_event', return_value=None)
        response_delete_event = await ac.delete(f"/recordings/{session_id}/event/{event_id}")
        assert response_delete_event.status_code == 200
        assert "id" in response_delete_event.json()

        # Test get actions
        mocker.patch('agentd.server.sessions.get', return_value=RecordingSession(session_id, "Test"))
        response_get_actions = await ac.get(f"/recordings/{session_id}/actions")
        assert response_get_actions.status_code == 200
        assert "actions" in response_get_actions.json()
