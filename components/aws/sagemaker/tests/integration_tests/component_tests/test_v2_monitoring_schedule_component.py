import time
import pytest
import os
import utils
from utils import kfp_client_utils
from utils import ack_utils
from utils import sagemaker_utils
import json
from sagemaker import get_execution_role, image_uris, Session
from sagemaker.model import Model
from sagemaker.model_monitor import DataCaptureConfig


@pytest.mark.parametrize(
    "test_file_dir",
    [
        pytest.param(
            "resources/config/ack-model-bias-job-definition",
            marks=pytest.mark.canary_test,
        ),
    ],
)
def test_v2_model_bias_job_definition(
    kfp_client, experiment_id, test_file_dir, deploy_endpoint
):
    download_dir = utils.mkdir(os.path.join(test_file_dir + "/generated"))
    test_params = utils.load_params(
        utils.replace_placeholders(
            os.path.join(test_file_dir, "config.yaml"),
            os.path.join(download_dir, "config.yaml"),
        )
    )
    k8s_client = ack_utils.k8s_client()
    job_definition_name = (
        utils.generate_random_string(10) + "-v2-model-bias-job-definition"
    )
    test_params["Arguments"]["job_definition_name"] = job_definition_name
    test_params["Arguments"]["model_bias_job_input"]["endpointInput"][
        "endpointName"
    ] = deploy_endpoint

    print(test_params)

    try:
        _, _, _ = kfp_client_utils.compile_run_monitor_pipeline(
            kfp_client,
            experiment_id,
            test_params["PipelineDefinition"],
            test_params["Arguments"],
            download_dir,
            test_params["TestName"],
            test_params["Timeout"],
        )

        job_definition_describe = ack_utils._get_resource(
            k8s_client, job_definition_name, "modelbiasjobdefinitions"
        )

        assert (
            job_definition_describe["status"]["conditions"][0]["type"]
            == "ACK.ResourceSynced"
        )

        assert job_definition_describe["status"]["ackResourceMetadata"]["arn"] != None

    finally:
        ack_utils._delete_resource(
            k8s_client, job_definition_name, "modelbiasjobdefinitions"
        )


@pytest.mark.parametrize(
    "test_file_dir",
    [
        pytest.param(
            "resources/config/ack-monitoring-schedule",
            marks=pytest.mark.canary_test,
        ),
    ],
)
def test_v2_monitoring_schedule(
    kfp_client, experiment_id, test_file_dir, deploy_endpoint, sagemaker_client
):
    download_dir = utils.mkdir(os.path.join(test_file_dir + "/generated"))
    test_params = utils.load_params(
        utils.replace_placeholders(
            os.path.join(test_file_dir, "config.yaml"),
            os.path.join(download_dir, "config.yaml"),
        )
    )
    k8s_client = ack_utils.k8s_client()

    # parameters for model bias job definition
    job_definition_name = (
        utils.generate_random_string(10) + "-v2-model-bias-job-definition"
    )
    test_params["Arguments"]["job_definition_name"] = job_definition_name
    test_params["Arguments"]["model_bias_job_input"]["endpointInput"][
        "endpointName"
    ] = deploy_endpoint

    # parameters for monitoring schedule
    monitoring_schedule_name = (
        utils.generate_random_string(10) + "-v2-monitoring-schedule"
    )
    test_params["Arguments"]["monitoring_schedule_name"] = monitoring_schedule_name
    test_params["Arguments"]["monitoring_schedule_config"][
        "monitoringJobDefinitionName"
    ] = job_definition_name

    print(test_params)

    try:
        _, _, _ = kfp_client_utils.compile_run_monitor_pipeline(
            kfp_client,
            experiment_id,
            test_params["PipelineDefinition"],
            test_params["Arguments"],
            download_dir,
            test_params["TestName"],
            test_params["Timeout"],
        )

        job_definition_describe = ack_utils._get_resource(
            k8s_client, job_definition_name, "modelbiasjobdefinitions"
        )

        # Check if the job definition is created
        assert (
            job_definition_describe["status"]["conditions"][0]["type"]
            == "ACK.ResourceSynced"
        )

        assert job_definition_describe["status"]["ackResourceMetadata"]["arn"] != None

        # Check if the monitoring schedule is created
        print("Describe monitoring Schedule Name: " + monitoring_schedule_name)
        monitoring_schedule_describe = sagemaker_client.describe_monitoring_schedule(
            MonitoringScheduleName=monitoring_schedule_name
        )

        print(f"Describe monitoring Schedule \n {monitoring_schedule_describe}")

        # Check if the monitoring schedule is created
        assert monitoring_schedule_describe["MonitoringScheduleArn"] != None

        assert (
            monitoring_schedule_describe["MonitoringScheduleStatus"] == "Scheduled"
            or "Pending"
        )

    finally:
        ack_utils._delete_resource(
            k8s_client, job_definition_name, "modelbiasjobdefinitions"
        )
        try:
            start_time = time.time()
            while time.time() - start_time < 10 * 60:
                res = ack_utils._delete_resource(
                    k8s_client, monitoring_schedule_name, "monitoringschedules"
                )

                if res == None:
                    print("MonitoringSchedule resource deleted")
                    break

                time.sleep(30)
        except:
            print("MonitoringSchedule resource failed")
            raise
