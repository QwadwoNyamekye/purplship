from typing import Tuple, List
from purplship.core.models import PickupCancellationRequest, Message, ConfirmationDetails
from purplship.core.utils import Serializable, Element
from purplship.carriers.canadapost.error import parse_error_response
from purplship.carriers.canadapost.utils import Settings


def parse_cancel_pickup_response(response: Element, settings: Settings) -> Tuple[ConfirmationDetails, List[Message]]:
    errors = parse_error_response(response, settings)
    cancellation = ConfirmationDetails(
        carrier=settings.carrier,
        carrier_name=settings.carrier_name,
        success=True
    ) if len(errors) == 0 else None

    return cancellation, errors


def cancel_pickup_request(payload: PickupCancellationRequest, _) -> Serializable[str]:
    return Serializable(payload.confirmation_number)
