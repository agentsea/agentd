Mouse Operations
=================

GET /mouse_coordinates
^^^^^^^^^^^^^^^^^^^^^^^

The ``/mouse_coordinates`` endpoint returns the current mouse position on the screen.

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

POST /move_mouse
^^^^^^^^^^^^^^^^

The ``/move_mouse`` endpoint moves the mouse cursor to a specified position on the screen.

**Request:**

.. code-block:: json

    {
        "x": 500,
        "y": 300,
        "duration": 2.0,
        "tween": "easeInOutQuad"
    }

Attributes:

- ``x`` (int): The x-coordinate to move the mouse to.
- ``y`` (int): The y-coordinate to move the mouse to.
- ``duration`` (float, optional): The time in seconds over which the movement should occur. Defaults to 1.0.
- ``tween`` (str, optional): The name of the tweening/easing function to use for the movement. Defaults to "easeInOutQuad".

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible ``status`` values:

- ``success``: The mouse was successfully moved to the specified coordinates.
- ``error``: An error occurred while attempting to move the mouse. An additional ``message`` field will provide details about the error.

POST /click
^^^^^^^^^^^

The ``/click`` endpoint simulates a mouse click at a specified location on the screen or a simple click if no location is provided.

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

- ``button`` (str, optional): The mouse button to click. Defaults to "left". Other possible values include "right" and "middle".
- ``location`` (object, optional): An object containing the coordinates and other optional parameters for moving the mouse before clicking. If not provided, the click occurs at the current mouse location.
    - ``x`` (int): The x-coordinate to move the mouse to.
    - ``y`` (int): The y-coordinate to move the mouse to.
    - ``duration`` (float, optional): The time in seconds over which the mouse movement should occur. Defaults to 1.0.
    - ``tween`` (str, optional): The name of the tweening/easing function to use for the mouse movement. Defaults to "easeInOutQuad".

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible ``status`` values:

- ``success``: The mouse was successfully clicked at the specified location or at the current location if no coordinates were provided.
- ``error``: An error occurred while attempting to click the mouse. An additional ``message`` field will provide details about the error.

POST /double_click
^^^^^^^^^^^^^^^^^^

The ``/double_click`` endpoint simulates a double mouse click at the current mouse location.

**Request:**

No parameters required.

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible ``status`` values:

- ``success``: The mouse was successfully double-clicked at the current location.
- ``error``: An error occurred while attempting to double-click the mouse. An additional ``message`` field will provide details about the error.

POST /scroll
^^^^^^^^^^^^

The ``/scroll`` endpoint simulates scrolling the mouse wheel.

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

Possible ``status`` values:

- ``success``: The scroll action was successfully performed.
- ``error``: An error occurred while attempting to perform the scroll action. An additional ``message`` field will provide details about the error.

POST /drag_mouse
^^^^^^^^^^^^^^^^

The ``/drag_mouse`` endpoint drags the mouse cursor from its current location to a specified location on the screen.

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

Possible ``status`` values:

- ``success``: The mouse was successfully dragged to the specified location.
- ``error``: An error occurred while attempting to drag the mouse. An additional ``message`` field will provide details about the error.
