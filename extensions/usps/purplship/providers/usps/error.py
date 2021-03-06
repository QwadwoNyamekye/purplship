from typing import List
from pyusps.error import Error
from purplship.core.utils.xml import Element
from purplship.core.models import Message
from purplship.providers.usps.utils import Settings


def parse_error_response(response: Element, settings: Settings) -> List[Message]:
    error_nodes: List[Error] = [
        (lambda error: (error, error.build(node)))(Error())[0]
        for node in (
            [response]
            if response.tag == "Error"
            else response.xpath(".//*[local-name() = $name]", name="Error")
        )
    ]
    return [
        Message(
            carrier_name=settings.carrier_name,
            carrier_id=settings.carrier_id,
            code=str(error.Number),
            message=error.Description,
        )
        for error in error_nodes
    ]
