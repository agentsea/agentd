Browser Operations
==================

POST /open_url
^^^^^^^^^^^^^^

The ``/open_url`` endpoint opens a specified URL in the Chromium browser.

**Request:**

.. code-block:: json

    {
        "url": "https://example.com"
    }

Attributes:

- ``url`` (str): The URL to be opened in the browser.

**Response:**

Returns a JSON response indicating the status of the operation.

.. code-block:: json

    {
        "status": "success"
    }

Possible ``status`` values:

- ``success``: The URL was successfully opened in the browser.
- ``error``: An error occurred while attempting to open the URL. An additional ``message`` field will provide details about the error.
