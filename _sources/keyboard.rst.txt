Keyboard Operations
====================

POST /type_text
^^^^^^^^^^^^^^^

The ``/type_text`` endpoint simulates typing text at the current cursor location.

**Request:**

.. code-block:: json

    {
        "text": "Hello, world!",
        "min_interval": 0.05,
        "max_interval": 0.25
    }

Attributes:

- ``text`` (str): The text to be typed.
- ``min_interval`` (float, optional): The minimum interval between key presses. Defaults to 0.05 seconds.
- ``max_interval`` (float, optional): The maximum interval between key presses. Defaults to 0.25 seconds.

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible ``status`` values:

- ``success``: The text was successfully typed at the current cursor location.
- ``error``: An error occurred while attempting to type the text. An additional ``message`` field will provide details about the error.

POST /press_key
^^^^^^^^^^^^^^^

The ``/press_key`` endpoint simulates pressing a key on the keyboard.

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

Possible ``status`` values:

- ``success``: The key was successfully pressed.
- ``error``: An error occurred while attempting to press the key. An additional ``message`` field will provide details about the error.
