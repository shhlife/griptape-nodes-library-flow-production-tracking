import logging
import time
from collections.abc import Generator

from base.base_griptape_cloud_node import BaseGriptapeCloudNode
from griptape_cloud_client.api.assistant_runs.create_assistant_run import sync as create_assistant_run
from griptape_cloud_client.api.assistant_runs.get_assistant_run import sync as get_assistant_run
from griptape_cloud_client.api.assistants.list_assistants import sync as list_assistants
from griptape_cloud_client.api.events.list_assistant_events import sync as list_events
from griptape_cloud_client.models.assistant_detail import AssistantDetail
from griptape_cloud_client.models.assistant_event_detail import AssistantEventDetail
from griptape_cloud_client.models.create_assistant_run_request_content import (
    CreateAssistantRunRequestContent,
)
from griptape_cloud_client.models.create_assistant_run_response_content import (
    CreateAssistantRunResponseContent,
)
from griptape_cloud_client.models.get_assistant_run_response_content import (
    GetAssistantRunResponseContent,
)
from griptape_cloud_client.models.list_assistant_events_response_content import ListAssistantEventsResponseContent
from griptape_cloud_client.models.list_assistants_response_content import ListAssistantsResponseContent
from griptape_nodes.exe_types.node_types import DataNode

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class BaseAssistantNode(BaseGriptapeCloudNode, DataNode):
    @classmethod
    def _assistant_to_name_and_id(cls, assistant: AssistantDetail) -> str:
        return f"{assistant.name} ({assistant.assistant_id})"

    def _list_assistants(self) -> ListAssistantsResponseContent:
        try:
            response = list_assistants(
                client=self.client,
                page=1,
                page_size=100,
            )
            if isinstance(response, ListAssistantsResponseContent):
                return response
            msg = f"Unexpected response type: {type(response)}"
            logger.error(msg)
            raise TypeError(msg)  # noqa: TRY301
        except Exception as e:
            logger.error("Error listing assistants: %s", e)
            raise

    def _get_assistant_run(self, assistant_run_id: str) -> GetAssistantRunResponseContent:
        try:
            response = get_assistant_run(assistant_run_id=assistant_run_id, client=self.client)
            if isinstance(response, GetAssistantRunResponseContent):
                return response
            msg = f"Unexpected response type: {type(response)}"
            logger.error(msg)
            raise TypeError(msg)  # noqa: TRY301
        except Exception as e:
            logger.error("Error getting assistant run: %s", e)
            raise

    def _create_assistant_run(self, assistant_id: str, args: list[str]) -> CreateAssistantRunResponseContent:
        try:
            response = create_assistant_run(
                assistant_id=assistant_id,
                body=CreateAssistantRunRequestContent(
                    args=args,
                ),
                client=self.client,
            )
            if isinstance(response, CreateAssistantRunResponseContent):
                return response
            msg = f"Unexpected response type: {type(response)}"
            logger.error(msg)
            raise TypeError(msg)  # noqa: TRY301
        except Exception as e:
            logger.error("Error creating assistant run: %s", e)
            raise

    def _list_assistant_run_events(
        self, assistant_run_id: str, offset: float | None = None
    ) -> ListAssistantEventsResponseContent:
        try:
            response = list_events(
                assistant_run_id=assistant_run_id,
                offset=str(offset) if offset is not None else None,
                client=self.client,
            )
            if isinstance(response, ListAssistantEventsResponseContent):
                return response
            msg = f"Unexpected response type: {type(response)}"
            logger.error(msg)
            raise TypeError(msg)  # noqa: TRY301
        except Exception as e:
            logger.error("Error listing events: %s", e)
            raise

    def _poll_assistant_run_events(self, assistant_run_id: str) -> Generator[list[AssistantEventDetail], None, None]:
        run_completed = False
        offset: float | None = None

        while not run_completed:
            list_events_response = self._list_assistant_run_events(assistant_run_id=assistant_run_id, offset=offset)
            offset = list_events_response.next_offset
            for event in list_events_response.events:
                if event.type_ == "FinishStructureRunEvent" and event.origin == "ASSISTANT":
                    run_completed = True
            yield list_events_response.events
            time.sleep(0.5)
