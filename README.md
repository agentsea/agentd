# agentd

A daemon that makes a desktop OS accessible to AI agents.

For a higher level interface see [AgentDesk](https://github.com/agentsea/agentdesk)

## Usage

Agentd is currently tested on Ubuntu 22.04 cloud image.

We recommend using one of our base vms which is already configured.

```bash
wget https://storage.googleapis.com/agentsea-vms/jammy/latest/agentd-jammy.qcow2
```

If you want to install on a fresh Ubuntu VM, use the a [cloud images base](https://cloud-images.ubuntu.com/jammy/current/) qcow2 image.

```bash
curl -sSL https://raw.githubusercontent.com/agentsea/agentd/main/remote_install.sh | sudo bash
```

To use the image, we need to make a [cloud-init](https://cloud-init.io/) iso with our user-data. See this [tutorial](https://cloudinit.readthedocs.io/en/latest/reference/datasources/nocloud.html), below is how it looks on MacOS

```bash
xorriso -as mkisofs -o cidata.iso -V "cidata" -J -r -iso-level 3 meta/
```

Then the image can be ran with Qemu

```bash
qemu-system-x86_64 -nographic -hda ./agentd-jammy.qcow2 \
-m 4G -smp 2 -netdev user,id=vmnet,hostfwd=tcp::6080-:6080,hostfwd=tcp::8000-:8000,hostfwd=tcp::2222-:22 \
-device e1000,netdev=vmnet -cdrom cidata.iso
```

The agentd service can then be accessed

```bash
curl localhost:8000/health
```

You can login to the machine with

```bash
ssh -p 2222 agentsea@localhost
```

## API Endpoints

### General

- **GET /health** - Checks the API's health.
  - **Response:** `{"status": "ok"}`

### Mouse and Keyboard Control

- **GET /mouse_coordinates** - Retrieves the current mouse coordinates.

  - **Response Model:** `CoordinatesModel`

- **POST /move_mouse** - Moves the mouse to specified coordinates.

  - **Request Body:** `MoveMouseModel`
  - **Response:** `{"status": "success"}` or `{"status": "error", "message": "<error_message>"}`

- **POST /click** - Clicks at the current or specified location.

  - **Request Body:** `ClickModel`
  - **Response:** `{"status": "success"}` or raises `HTTPException`

- **POST /double_click** - Performs a double-click at the current mouse location.

  - **Response:** `{"status": "success"}` or raises `HTTPException`

- **POST /type_text** - Types the specified text.

  - **Request Body:** `TypeTextModel`
  - **Response:** `{"status": "success"}` or raises `HTTPException`

- **POST /press_key** - Presses a specified key.

  - **Request Body:** `PressKeyModel`
  - **Response:** `{"status": "success"}` or raises `HTTPException`

- **POST /scroll** - Scrolls the mouse wheel.

  - **Request Body:** `ScrollModel`
  - **Response:** `{"status": "success"}` or raises `HTTPException`

- **POST /drag_mouse** - Drags the mouse to specified coordinates.
  - **Request Body:** `DragMouseModel`
  - **Response:** `{"status": "success"}` or raises `HTTPException`

### Web Browser Control

- **POST /open_url** - Opens a URL in a Chromium-based browser.
  - **Request Body:** `OpenURLModel`
  - **Response:** `{"status": "success"}` or `{"status": "error", "message": "<error_message>"}`

### Screen Capture

- **POST /screenshot** - Takes a screenshot and returns it as a base64-encoded image.
  - **Response Model:** `ScreenshotResponseModel`

### Session Recording

- **POST /recordings** - Starts a new recording session.

  - **Request Body:** `RecordRequest`
  - **Response Model:** `RecordResponse`

- **GET /recordings** - Lists all recordings.

  - **Response Model:** `Recordings`

- **POST /recordings/{session_id}/stop** - Stops a recording session.

  - **Path Variable:** `session_id`
  - **Response:** None (side effect: stops recording and saves to file)

- **GET /recordings/{session_id}** - Retrieves information about a specific recording session.

  - **Path Variable:** `session_id`
  - **Response Model:** `Recording`

- **GET /recordings/{session_id}/event/{event_id}** - Retrieves a specific event from a recording.

  - **Path Variables:** `session_id`, `event_id`
  - **Response Model:** `RecordedEvent`

- **DELETE /recordings/{session_id}/event/{event_id}** - Deletes a specific event from a recording.

  - **Path Variables:** `session_id`, `event_id`
  - **Response Model:** `Recording`

- **GET /active_sessions** - Lists IDs of all active recording sessions.

  - **Response Model:** `Recordings`

- **GET /recordings/{session_id}/actions** - Retrieves all actions from a specific recording session.
  - **Path Variable:** `session_id`
  - **Response Model:** `Actions`

## Developing

To pack a fresh set of images

```bash
make pack
```

To run from this repo

```bash
make run-jammy
```
