# from google.cloud import storage
import os


def upload_directory_to_gcs(bucket_name, source_directory, destination_blob_prefix):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    for root, dirs, files in os.walk(source_directory):
        for file in files:
            file_path = os.path.join(root, file)
            blob_path = os.path.join(
                destination_blob_prefix,
                os.path.relpath(file_path, start=source_directory),
            )
            blob = bucket.blob(blob_path)
            blob.upload_from_filename(file_path)
