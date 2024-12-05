import os
import subprocess
from celery import Celery
import requests
from skillpacks import V1Action, V1ActionEvent, V1ToolRef, ActionEvent, EnvState
from celery.app.task import Task
from taskara.task import V1TaskUpdate
from taskara.task import Task as App_task
Task.__class_getitem__ = classmethod(lambda cls, *args, **kwargs: cls) # type: ignore[attr-defined]



# Create a new Celery application instance with the filesystem as the broker
celery_app = Celery('send_actions', broker_url='filesystem://', CELERY_RESULT_BACKEND='file:///config/app/celery', broker_transport_options={ # type: ignore
        'data_folder_in': '/config/app/celery',
        'data_folder_out': '/config/app/celery/',
        'control_folder': '/config/app/celery/',
    })

celery_app.conf.update(
    worker_concurrency=1,  # Set concurrency to 1 we need to either change the data model or enable object locking to do this.
    task_serializer='json', # Specify the task serializer if needed
)


@celery_app.task
def send_action(taskID, remote_address, auth_token, owner_id, v1actionEvent: dict):
    print("send_action: starting send action function in worker")
    action = ActionEvent.from_v1(V1ActionEvent(**v1actionEvent))
    print(f"send_action: action {action.id} variable created in worker process")
    tasks = App_task.find( # TODO avoid having to get the task every time
            remote=remote_address,
            id=taskID,
            auth_token=auth_token,
            owner_id=owner_id,
        )
    task = tasks[0]
    print(f"send_action: task {task.id} variable created in worker process")
    try:
        task.record_action_event(action)
    except Exception as e:
         print(f"send_action: record_action_event failed due to error: {e} for task ID: {taskID} and action {v1actionEvent}")
    print(f"send_action: finished sending action {action.id} for task {task.id}")
    return f"send_action: finished sending action {action.id} for task {task.id}"

@celery_app.task
def update_task(taskID, remote_address, auth_token, v1taskupdate: dict):
    print("update_task: starting update task function in worker")
    print(f"update_task: task: {taskID} with be updated with {v1taskupdate}")
    # Ensure the v1taskupdate dictionary matches the Pydantic model
    try:
        updateData = V1TaskUpdate(**v1taskupdate)
    except Exception as e:
        print(f"update_task: Error while parsing update data: {e}")
        raise

    print(f"update_task: Task {taskID} update {updateData.model_dump()} created in worker process")

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    else:
        print("update_task: Error: no auth token!!")
    
    url = f"{remote_address}/v1/tasks/{taskID}"
    print(url, headers, "update_task: url and headers")
    try:
        response = requests.put(url, json=updateData.model_dump(), headers=headers)
        try:
                response.raise_for_status()
        except requests.exceptions.HTTPError as e:

                print(f"update_task: HTTP Error: {e}")
                print(f"update_task: Status Code: {response.status_code}")
                try:
                    print(f"update_task: Response Body: {response.json()}")
                except ValueError:
                    print(f"update_task: Raw Response: {response.text}")
                raise
        print(f"update_task: response: {response.__dict__}")
        print(f"update_task: response.status_code: {response.status_code}")
        try:
            response_json = response.json()
            print(f"update_task: response_json: {response_json}")
            return response_json
        except ValueError:
            print(f"update_task: Raw Response: {response.text}")
            return None

    except requests.RequestException as e:
        print(f"update_task: Request failed: {e}")
        raise e
    
    return "Something went wrong"