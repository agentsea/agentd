Making Screenshots
===================

POST /screenshot
^^^^^^^^^^^^^^^^

The ``/screenshot`` endpoint captures the current screen and returns an image.

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

Possible ``status`` values:

- ``success``: The screenshot was successfully captured and returned.
- ``error``: An error occurred while attempting to capture the screenshot. An additional ``message`` field will provide details about the error.
