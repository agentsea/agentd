<!-- PROJECT LOGO -->
<br />
<p align="center">
  <!-- <a href="https://github.com/agentsea/skillpacks">
    <img src="https://project-logo.png" alt="Logo" width="80">
  </a> -->

  <h1 align="center">agentd</h1>

  <p align="center">
    A daemon that makes a desktop OS accessible to AI agents.
    <br />
    <a href="https://docs.hub.agentsea.ai/agentd/intro"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/agentsea/agentd/issues">Report Bug</a>
    ·
    <a href="https://github.com/agentsea/agentd/issues">Request Feature</a>
  </p>
  <br>
</p>

`AgentD` makes a desktop OS accessible to AI agents by exposing an HTTP API.

For a higher level interface see [AgentDesk](https://github.com/agentsea/agentdesk).

## Usage

`AgentD` is currently tested on Ubuntu 22.04 cloud image.

We recommend using one of our base vms which is already configured.

### Qemu

For Qemu, download the qcow2 image:
```bash
wget https://storage.googleapis.com/agentsea-vms/jammy/latest/agentd-jammy.qcow2
```

To use the image, we need to make a [cloud-init](https://cloud-init.io/) iso with our user-data. See this [tutorial](https://cloudinit.readthedocs.io/en/latest/reference/datasources/nocloud.html), below is how it looks on MacOS:

```bash
xorriso -as mkisofs -o cidata.iso -V "cidata" -J -r -iso-level 3 meta/
```
Then the image can be ran with Qemu:

```bash
qemu-system-x86_64 -nographic -hda ./agentd-jammy.qcow2 \
-m 4G -smp 2 -netdev user,id=vmnet,hostfwd=tcp::6080-:6080,hostfwd=tcp::8000-:8000,hostfwd=tcp::2222-:22 \
-device e1000,netdev=vmnet -cdrom cidata.iso
```
Once running, the agentd service can be accessed:

```bash
curl localhost:8000/health
```   
To login to the machine:

```bash
ssh -p 2222 agentsea@localhost
```   

### AWS
For AWS, use public AMI `ami-01a893c1530453073`.   

Create a cloud-init script with your ssh key:

```yaml
#cloud-config

users:
  - name: agentsea
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    groups: sudo
    ssh_authorized_keys:
      - your-ssh-public-key

package_upgrade: true
```

```bash
aws ec2 run-instances \
    --image-id ami-01a893c1530453073 \
    --count 1 \
    --instance-type t2.micro \
    --key-name $KEY_NAME \
    --security-group-ids $SG_NAME \
    --subnet-id $SUBNET_NAME \
    --user-data file://path/to/cloud-init-config.yaml
```

### GCE

For GCE, use the public image `ubuntu-22-04-20240208044623`.

```bash
gcloud compute instances create $NAME \
    --machine-type "n1-standard-1" \
    --image "ubuntu-22-04-20240208044623" \
    --image-project $PROJECT_ID \
    --zone $ZONE \
    --metadata ssh-keys="agentsea:$(cat path/to/your/public/ssh/key.pub)"
```

### Custom

If you want to install on a fresh Ubuntu VM, use the a [cloud images base](https://cloud-images.ubuntu.com/jammy/current/) qcow2 image.

```bash
curl -sSL https://raw.githubusercontent.com/agentsea/agentd/main/remote_install.sh | sudo bash
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
&nbsp;  
To run from this repo

```bash
make run-jammy
```
