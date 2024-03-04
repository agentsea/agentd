API Reference
=============

The `agentd` demon provides a number of HTTP endpoints for interacting with the VM via HTTP.

GET "/"
^^^^^^^

The root endpoint returns a welcome message. This endpoint serves as a basic check to ensure 
the agent service is running and accessible.

**Request:**

No parameters required.

**Response:**

Returns a JSON response with a welcome message.

.. code-block:: json

    {
        "message": "Agent in the shell"
    }

GET /health
^^^^^^^^^^^

The health endpoint returns a health check for the agent service.

**Request:**

No parameters required.

**Response:**

Returns a JSON response with a health check.

.. code-block:: json

    {
        "status": "ok"
    }

GET /info
^^^^^^^^^

The info endpoint returns detailed information about the system where the agent is running.

**Request:**

No parameters required.

**Response:**

Returns a JSON response with the system information.

.. code-block:: json

    {
        "last_activity_ts": 1625079600,
        "screen_size": {
            "x": 1920,
            "y": 1080
        },
        "os_info": "Linux 5.8.0-53-generic",
        "code_version": "a1b2c3d4"
    }

The response includes the last activity timestamp (`last_activity_ts`), screen size (`screen_size`), operating system information (`os_info`), and the current code version (`code_version`).

GET /screen_size
^^^^^^^^^^^^^^^^

The screen_size endpoint returns the current screen size of the system where the agent is running.

**Request:**

No parameters required.

**Response:**

Returns a JSON response with the screen size.

.. code-block:: json

    {
        "x": 1920,
        "y": 1080
    }

The response includes the width (`x`) and height (`y`) of the screen in pixels.

GET /mouse_coordinates
^^^^^^^^^^^^^^^^^^^^^^^

The mouse_coordinates endpoint returns the current mouse position on the screen.

**Request:**

No parameters required.

**Response:**

Returns a JSON response with the current mouse coordinates.

.. code-block:: json

    {
        "x": 1024,
        "y": 768
    }

The response includes the x and y coordinates of the mouse position in pixels.

POST /open_url
^^^^^^^^^^^^^^

The open_url endpoint opens a specified URL in the Chromium browser.

**Request:**

.. code-block:: json

    {
        "url": "https://example.com"
    }

Attributes:

- `url` (str): The URL to be opened in the browser.

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible `status` values:

- `success`: The URL was successfully opened in the browser.
- `error`: An error occurred while attempting to open the URL. An additional `message` field will provide details about the error.

POST /move_mouse
^^^^^^^^^^^^^^^^

The move_mouse endpoint moves the mouse cursor to a specified position on the screen.

**Request:**

.. code-block:: json

    {
        "x": 500,
        "y": 300,
        "duration": 2.0,
        "tween": "easeInOutQuad"
    }

Attributes:

- `x` (int): The x-coordinate to move the mouse to.
- `y` (int): The y-coordinate to move the mouse to.
- `duration` (float, optional): The time in seconds over which the movement should occur. Defaults to 1.0.
- `tween` (str, optional): The name of the tweening/easing function to use for the movement. Defaults to "easeInOutQuad".

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible `status` values:

- `success`: The mouse was successfully moved to the specified coordinates.
- `error`: An error occurred while attempting to move the mouse. An additional `message` field will provide details about the error.

POST /click
^^^^^^^^^^^

The click endpoint simulates a mouse click at a specified location on the screen or a simple click if no location is provided.

**Request:**

.. code-block:: json

    {
        "button": "left",
        "location": {
            "x": 500,
            "y": 300,
            "duration": 2.0,
            "tween": "easeInOutQuad"
        }
    }

Attributes:

- `button` (str, optional): The mouse button to click. Defaults to "left". Other possible values include "right" and "middle".
- `location` (object, optional): An object containing the coordinates and other optional parameters for moving the mouse before clicking. If not provided, the click occurs at the current mouse location.
    - `x` (int): The x-coordinate to move the mouse to.
    - `y` (int): The y-coordinate to move the mouse to.
    - `duration` (float, optional): The time in seconds over which the mouse movement should occur. Defaults to 1.0.
    - `tween` (str, optional): The name of the tweening/easing function to use for the mouse movement. Defaults to "easeInOutQuad".

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible `status` values:

- `success`: The mouse was successfully clicked at the specified location or at the current location if no coordinates were provided.
- `error`: An error occurred while attempting to click the mouse. An additional `message` field will provide details about the error.

POST /double_click
^^^^^^^^^^^^^^^^^^

The double_click endpoint simulates a double mouse click at the current mouse location.

**Request:**

No parameters required.

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible `status` values:

- `success`: The mouse was successfully double-clicked at the current location.
- `error`: An error occurred while attempting to double-click the mouse. An additional `message` field will provide details about the error.

POST /type_text
^^^^^^^^^^^^^^^

The type_text endpoint simulates typing text at the current cursor location.

**Request:**

.. code-block:: json

    {
        "text": "Hello, world!",
        "min_interval": 0.05,
        "max_interval": 0.25
    }

Attributes:

- `text` (str): The text to be typed.
- `min_interval` (float, optional): The minimum interval between key presses. Defaults to 0.05 seconds.
- `max_interval` (float, optional): The maximum interval between key presses. Defaults to 0.25 seconds.

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible `status` values:

- `success`: The text was successfully typed at the current cursor location.
- `error`: An error occurred while attempting to type the text. An additional `message` field will provide details about the error.

POST /press_key
^^^^^^^^^^^^^^^

The press_key endpoint simulates pressing a key on the keyboard.

**Request:**

.. code-block:: json
   
   {
      "key": "string"
   }

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible `status` values:

- `success`: The key was successfully pressed.
- `error`: An error occurred while attempting to press the key. An additional `message` field will provide details about the error.


POST /scroll
^^^^^^^^^^^^

The scroll endpoint simulates scrolling the mouse wheel.

**Request:**

.. code-block:: json

   {
      "clicks": "int"
   }

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible `status` values:

- `success`: The scroll action was successfully performed.
- `error`: An error occurred while attempting to perform the scroll action. An additional `message` field will provide details about the error.

POST /drag_mouse
^^^^^^^^^^^^^^^^

The drag_mouse endpoint drags the mouse cursor from its current location to a specified location on the screen.

**Request:**

.. code-block:: json

   {
      "x": "int",
      "y": "int"
   }

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible `status` values:

- `success`: The mouse was successfully dragged to the specified location.
- `error`: An error occurred while attempting to drag the mouse. An additional `message` field will provide details about the error.

POST /screenshot
^^^^^^^^^^^^^^^^

The screenshot endpoint captures the current screen and returns an image.

**Request:**

No parameters required.

**Response:**

Returns a JSON response containing the screenshot image encoded in base64 and the file path where the screenshot is saved.

.. code-block:: json

    {
        "status": "success",
        "image": "base64_encoded_image",
        "file_path": "path/to/screenshot.png"
    }

Possible `status` values:

- `success`: The screenshot was successfully captured and returned.
- `error`: An error occurred while attempting to capture the screenshot. An additional `message` field will provide details about the error.

POST /recordings
^^^^^^^^^^^^^^^^

The recordings endpoint starts a new recording session.

**Request:**

.. code-block:: json

    {
        "description": "string"
    }

**Response:**

Returns a JSON response containing the session ID of the newly started recording session.

.. code-block:: json

    {
        "session_id": "uuid"
    }

GET /recordings
^^^^^^^^^^^^^^^

The recordings endpoint retrieves a list of all recording sessions.

**Request:**

No parameters required.

**Response:**

Returns a JSON response containing a list of recording session IDs.

.. code-block:: json

    {
        "recordings": [
            "uuid1",
            "uuid2",
            "uuid3"
        ]
    }

This endpoint allows you to retrieve all the recording sessions that have been initiated.

POST /recordings/{session_id}/stop
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The endpoint to stop a recording session.

**Request:**

Path Parameters:
- `session_id`: The unique identifier of the recording session to be stopped.

**Response:**

Returns a JSON response indicating the success of the operation.

GET /recordings/{session_id}
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The endpoint to retrieve a specific recording session by its session ID.

**Request:**

Path Parameters:
- `session_id`: The unique identifier of the recording session to be retrieved.

**Response:**

Returns a JSON response containing the details of the specified recording session, including the session ID, description, start time, end time, and a list of recorded events.

.. code-block:: json

    {
        "id": "uuid",
        "description": "Session Description",
        "start_time": 1622547600,
        "end_time": 1622547900,
        "events": [
            {
                "id": "uuid",
                "type": "click",
                "timestamp": 1622547605,
                "coordinates": {
                    "x": 100,
                    "y": 200
                },
                "screenshot_path": "path/to/screenshot",
                "click_data": {
                    "button": "left",
                    "pressed": true
                }
            },
            {
                "id": "uuid",
                "type": "key",
                "timestamp": 1622547610,
                "key_data": {
                    "key": "a"
                }
            }
        ]
    }

This endpoint allows you to retrieve detailed information about a specific recording session, including all the events that occurred during the session.

GET /recordings/{session_id}/event/{event_id}
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The endpoint to retrieve a specific event from a recording session by its session ID and event ID.

**Request:**

Path Parameters:
- `session_id`: The unique identifier of the recording session.
- `event_id`: The unique identifier of the event within the recording session.

**Response:**

Returns a JSON response containing the details of the specified event, including the event ID, type, timestamp, coordinates, and any associated data such as click data, key data, scroll data, or text data.

.. code-block:: json

    {
        "id": "uuid",
        "type": "click",
        "timestamp": 1622547605,
        "coordinates": {
            "x": 100,
            "y": 200
        },
        "screenshot_path": "path/to/screenshot",
        "click_data": {
            "button": "left",
            "pressed": true
        }
    }

This endpoint allows you to retrieve detailed information about a specific event within a recording session.

DELETE /recordings/{session_id}/event/{event_id}
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The endpoint to delete a specific event from a recording session by its session ID and event ID.

**Request:**

Path Parameters:
- `session_id`: The unique identifier of the recording session.
- `event_id`: The unique identifier of the event within the recording session.

**Response:**

Returns a JSON response containing the updated recording session details without the deleted event.

.. code-block:: json

    {
        "id": "session_uuid",
        "description": "Session Description",
        "start_time": 1622547600,
        "end_time": 1622547615,
        "events": [
            {
                "id": "uuid",
                "type": "click",
                "timestamp": 1622547605,
                "coordinates": {
                    "x": 100,
                    "y": 200
                },
                "screenshot_path": "path/to/screenshot",
                "click_data": {
                    "button": "left",
                    "pressed": true
                }
            }
            // Other events
        ]
    }

This endpoint allows you to delete a specific event from a recording session.

GET /active_sessions
^^^^^^^^^^^^^^^^^^^^

This endpoint lists all active recording sessions.

**Response:**

Returns a JSON response containing a list of session IDs for all active recording sessions.

.. code-block:: json

    {
        "recordings": [
            "session_id_1",
            "session_id_2",
            // Other session IDs
        ]
    }

This endpoint allows you to retrieve a list of all active recording sessions.

GET /recordings/{session_id}/actions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This endpoint retrieves a list of actions for a specific recording session.

**Parameters:**

- ``session_id``: The unique identifier for the recording session.

**Response:**

Returns a JSON response containing a list of actions for the specified recording session.

.. code-block:: json

    {
        "actions": [
            {
                "id": "action_uuid",
                "type": "click",
                "timestamp": 1622547605,
                "details": {
                    "coordinates": {
                        "x": 100,
                        "y": 200
                    },
                    "button": "left",
                    "pressed": true
                }
            },
            {
                "id": "action_uuid",
                "type": "keypress",
                "timestamp": 1622547610,
                "details": {
                    "key": "space"
                }
            }
            // Other actions
        ]
    }

This endpoint allows you to retrieve a list of all actions (clicks, keypresses, etc.) that occurred during a specific recording session.

GET /system_usage
^^^^^^^^^^^^^^^^^

This endpoint retrieves the current system usage statistics.

**Response:**

Returns a JSON response containing the current system usage statistics including CPU, memory, and disk usage percentages.

.. code-block:: json

    {
        "cpu_percent": 23.5,
        "memory_percent": 74.2,
        "disk_percent": 55.3
    }

This endpoint allows you to monitor the health and performance of the system where the agent is running.
