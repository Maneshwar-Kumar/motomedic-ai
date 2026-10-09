import base64
import json
import os
import functions_framework
from google.cloud import billing_v1
from policy import should_stop

PROJECT = "motomedic-ai-20261009"


@functions_framework.cloud_event
def stop_billing(event):
    message = json.loads(base64.b64decode(event.data["message"]["data"], validate=True))
    stop = should_stop(message)
    print(json.dumps({"project": PROJECT, "cost_inr": message["costAmount"], "stop": stop}))
    if not stop:
        return
    client = billing_v1.CloudBillingClient()
    name = f"projects/{PROJECT}"
    current = client.get_project_billing_info(name=name)
    if not current.billing_enabled:
        print("Billing already disabled")
        return
    if os.environ.get("SIMULATE", "true").lower() == "true":
        print("SIMULATION: would disable MotoMedic billing")
        return
    client.update_project_billing_info(name=name,
        project_billing_info=billing_v1.ProjectBillingInfo(billing_account_name=""))
    print("MotoMedic billing disabled at the conservative spending threshold")
