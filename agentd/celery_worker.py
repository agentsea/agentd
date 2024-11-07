import os
import subprocess
from celery import Celery
from skillpacks import V1Action, V1ActionEvent, V1ToolRef, ActionEvent, EnvState
from celery.app.task import Task
from taskara.task import Task as App_task
Task.__class_getitem__ = classmethod(lambda cls, *args, **kwargs: cls) # type: ignore[attr-defined]



# Create a new Celery application instance with the filesystem as the broker
celery_app = Celery('send_actions', broker_url='filesystem://', CELERY_RESULT_BACKEND='file:///config/app/celery', broker_transport_options={ # type: ignore
        'data_folder_in': '/config/app/celery',
        'data_folder_out': '/config/app/celery/',
        'control_folder': '/config/app/celery/',
    })

celery_app.conf.update(
    worker_concurrency=1,  # Set concurrency to 1 we need to add order tracking to actions in order to increase this
    task_serializer='json', # Specify the task serializer if needed
)


@celery_app.task
def send_action(taskID, remote_address, auth_token, owner_id, v1actionEvent: dict):
    print("starting send action function in worker")
    action = ActionEvent.from_v1(V1ActionEvent(**v1actionEvent))
    print(f"action {action.id} variable created in worker process")
    tasks = App_task.find( # TODO avoid having to get the task every time
            remote=remote_address,
            id=taskID,
            auth_token=auth_token,
            owner_id=owner_id,
        )
    task = tasks[0]
    print(f"task {task.id} variable created in worker process")
    task.record_action_event(action)
    print(f"finished sending action {action.id} for task {task.id}")
    return f"finished sending action {action.id} for task {task.id}"