from typing import Tuple, List
from pydhl.modify_pickup_global_req_3_0 import ModifyPURequest, MetaData
from pydhl.modify_pickup_global_res_3_0 import ModifyPUResponse
from pydhl.pickupdatatypes_global_3_0 import (
    Requestor,
    Place,
    RequestorContact,
    Pickup,
    WeightSeg,
)
from purplship.core.utils import (
    export,
    Serializable,
    Element,
    format_time,
    format_date,
    decimal,
)
from purplship.core.models import (
    Message,
    PickupDetails,
    ChargeDetails,
    PickupUpdateRequest,
)
from purplship.core.units import WeightUnit, Weight
from purplship.providers.dhl.units import CountryRegion, WeightUnit as DHLWeightUnit
from purplship.providers.dhl.utils import Settings, reformat_time
from purplship.providers.dhl.error import parse_error_response


def parse_modify_pickup_response(
    response, settings: Settings
) -> Tuple[PickupDetails, List[Message]]:
    successful = (
        len(response.xpath(".//*[local-name() = $name]", name="ConfirmationNumber")) > 0
    )
    pickup = _extract_pickup(response, settings) if successful else None
    return pickup, parse_error_response(response, settings)


def _extract_pickup(response: Element, settings: Settings) -> PickupDetails:
    pickup = ModifyPUResponse()
    pickup.build(response)
    pickup_charge = (
        ChargeDetails(
            name="Pickup Charge",
            amount=decimal(pickup.PickupCharge),
            currency=pickup.CurrencyCode,
        )
        if pickup.PickupCharge is not None
        else None
    )
    return PickupDetails(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        confirmation_number=str(pickup.ConfirmationNumber[0]),
        pickup_date=format_date(pickup.NextPickupDate)
        if pickup.NextPickupDate is not None
        else None,
        pickup_charge=pickup_charge,
        ready_time=format_time(pickup.ReadyByTime),
        closing_time=format_time(pickup.CallInTime),
    )


def modify_pickup_request(
    payload: PickupUpdateRequest, settings: Settings
) -> Serializable[ModifyPURequest]:
    weight_unit = DHLWeightUnit.LB
    weight = sum(
        [
            Weight(parcel.weight, WeightUnit[weight_unit.name]).LB
            for parcel in payload.parcels
        ]
    )
    request = ModifyPURequest(
        Request=settings.Request(
            MetaData=MetaData(SoftwareName="XMLPI", SoftwareVersion=1.0)
        ),
        schemaVersion=3.0,
        RegionCode=CountryRegion[payload.address.country_code].value
        if payload.address.country_code
        else "AM",
        ConfirmationNumber=payload.confirmation_number,
        Requestor=Requestor(
            AccountNumber=settings.account_number,
            AccountType="D",
            RequestorContact=RequestorContact(
                PersonName=payload.address.person_name,
                Phone=payload.address.phone_number,
                PhoneExtension=None,
            ),
            CompanyName=payload.address.company_name,
        ),
        Place=Place(
            City=payload.address.city,
            StateCode=payload.address.state_code,
            PostalCode=payload.address.postal_code,
            CompanyName=payload.address.company_name,
            CountryCode=payload.address.country_code,
            PackageLocation=payload.package_location,
            LocationType="R" if payload.address.residential else "B",
            Address1=payload.address.address_line1,
            Address2=payload.address.address_line2,
        ),
        PickupContact=RequestorContact(
            PersonName=payload.address.person_name, Phone=payload.address.phone_number
        ),
        Pickup=Pickup(
            Pieces=len(payload.parcels),
            PickupDate=payload.date,
            ReadyByTime=f'{payload.ready_time}:00',
            CloseTime=f'{payload.closing_time}:00',
            SpecialInstructions=[payload.instruction],
            RemotePickupFlag="Y",
            weight=WeightSeg(Weight=weight, WeightUnit=weight_unit.value),
        ),
        OriginSvcArea=None,
    )
    return Serializable(request, _request_serializer)


def _request_serializer(request: ModifyPURequest) -> str:
    xml_str = export(
        request,
        name_="req:ModifyPURequest",
        namespacedef_='xmlns:req="http://www.dhl.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.dhl.com modify-pickup-Global-req.xsd"',
    ).replace("dhlPickup:", "")

    xml_str = reformat_time("CloseTime", reformat_time("ReadyByTime", xml_str))
    return xml_str
