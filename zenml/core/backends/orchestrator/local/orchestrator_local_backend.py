#  Copyright (c) maiot GmbH 2020. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
"""Definition of the base Orchestrator Backend"""

import os
from typing import Dict, Text, Any

from tfx.orchestration import pipeline

from zenml.core.backends.base_backend import BaseBackend
from zenml.core.backends.orchestrator.local.zenml_local_orchestrator import \
    ZenMLLocalDagRunner
from zenml.core.backends.processing.processing_local_backend import \
    ProcessingLocalBackend
from zenml.core.standards import standard_keys as keys


class OrchestratorLocalBackend(BaseBackend):
    """
    Local ZenML orchestrator backend. Use this to run a ZenML pipeline
    locally on a machine.

    An orchestrator backend is responsible for scheduling, initializing and
    running different pipeline components. Examples of orchestrators are
    Apache Beam, Kubeflow or (here) Local Orchestration.

    Abstracting the pipeline logic from the orchestrator backend enables
    machine learning workloads to be run in different kinds of environments.
    For larger, decentralized data processing applications, a cloud-based
    backend can be used to distribute work across multiple machines.
    For quick prototyping and local tests, a single-machine direct backend can
    be selected to execute an ML Pipeline with minimal orchestration overhead.
    """
    BACKEND_TYPE = 'local'
    BACKEND_KEY = 'orchestrator'

    @staticmethod
    def get_tfx_pipeline(config: Dict[Text, Any]) -> pipeline.Pipeline:
        """
        Converts ZenML config dict to TFX pipeline.

        Args:
            config: A ZenML config dict

        Returns:
            tfx_pipeline: A TFX pipeline object.
        """
        env_dict = config[keys.GlobalKeys.ENV]

        # Dataset, experiment
        # Using the artifact store ID makes sense
        # It is used currently to make all pipelines have the same base
        # context in ML metadata store.
        # artifact_store = ArtifactStore(
        #     env_dict[keys.EnvironmentKeys.ARTIFACT_STORE])
        # pipeline_name = env_dict[keys.EnvironmentKeys.EXPERIMENT_NAME]
        #
        # metadata_store: ZenMLMetadataStore = ZenMLMetadataStore.from_config(
        #     env_dict[keys.EnvironmentKeys.METADATA_STORE])
        # metadata_connection_config = metadata_store.get_tfx_metadata_config()

        from zenml.core.pipelines.base_pipeline import BasePipeline
        zen_pipeline: BasePipeline = BasePipeline.from_config(config)

        # Get component list
        component_list = zen_pipeline.get_tfx_component_list(config)

        # Get pipeline metadata
        pipeline_name = zen_pipeline.pipeline_name
        metadata_connection_config = \
            zen_pipeline.metadata_store.get_tfx_metadata_config()
        artifact_store = zen_pipeline.artifact_store

        # Pipeline settings
        pipeline_root = os.path.join(
            artifact_store.path, artifact_store.unique_id)
        pipeline_log = os.path.join(pipeline_root, 'logs', pipeline_name)

        # Execution
        execution: ProcessingLocalBackend = \
            zen_pipeline.backends_dict[ProcessingLocalBackend.BACKEND_KEY]
        beam_args = execution.get_beam_args(pipeline_name, pipeline_root)

        tfx_pipeline = pipeline.Pipeline(
            components=component_list,
            beam_pipeline_args=beam_args,
            metadata_connection_config=metadata_connection_config,
            pipeline_name=zen_pipeline.artifact_store.unique_id,  # for caching
            pipeline_root=pipeline_root,
            log_root=pipeline_log,
            enable_cache=zen_pipeline.enable_cache)

        # Ensure that the run_id is ZenML pipeline_name
        tfx_pipeline.pipeline_info.run_id = zen_pipeline.pipeline_name
        return tfx_pipeline

    def run(self, config: Dict[Text, Any]):
        """
        This run function essentially calls an underlying TFX orchestrator run.
        However it is meant as a higher level abstraction with some
        opinionated decisions taken.

        Args:
            config: a ZenML config dict
        """
        tfx_pipeline = self.get_tfx_pipeline(config)
        ZenMLLocalDagRunner().run(tfx_pipeline)
