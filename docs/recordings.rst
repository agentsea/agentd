Making Recordings
==================

POST /recordings
^^^^^^^^^^^^^^^^

The ``/recordings`` endpoint starts a new recording session.

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

The ``/recordings`` endpoint retrieves a list of all recording sessions.

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
- ``session_id``: The unique identifier of the recording session to be stopped.

**Response:**

Returns a JSON response indicating the success of the operation.

GET /recordings/{session_id}
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The endpoint to retrieve a specific recording session by its session ID.

**Request:**

Path Parameters:
- ``session_id``: The unique identifier of the recording session to be retrieved.

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
- ``session_id``: The unique identifier of the recording session.
- ``event_id``: The unique identifier of the event within the recording session.

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
- ``session_id``: The unique identifier of the recording session.
- ``event_id``: The unique identifier of the event within the recording session.

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

