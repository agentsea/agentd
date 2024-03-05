System Information and Health
=============================

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

The ``/health`` endpoint returns a health check for the agent service.

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

The ``/info`` endpoint returns detailed information about the system where the agent is running.

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

The response includes the last activity timestamp (``last_activity_ts``), screen size (``screen_size``), operating system information (``os_info``), and the current code version (``code_version``).

GET /screen_size
^^^^^^^^^^^^^^^^

The ``/screen_size`` endpoint returns the current screen size of the system where the agent is running.

**Request:**

No parameters required.

**Response:**

Returns a JSON response with the screen size.

.. code-block:: json

    {
        "x": 1920,
        "y": 1080
    }

The response includes the width (``x``) and height (``y``) of the screen in pixels.

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
