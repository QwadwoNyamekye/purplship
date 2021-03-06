import time
from functools import reduce
from typing import List, Tuple, cast, Iterable
from pydhl.dct_req_global_2_0 import (
    DCTRequest,
    DCTTo,
    DCTFrom,
    GetQuoteType,
    BkgDetailsType,
    PiecesType,
    MetaData,
    PieceType,
    QtdShpType,
    QtdShpExChrgType,
)
from pydhl.dct_requestdatatypes_global import DCTDutiable
from pydhl.dct_response_global_2_0 import QtdShpType as ResponseQtdShpType
from purplship.core.utils import export, Serializable, Element, decimal, to_date
from purplship.core.units import Packages, Options, Package, WeightUnit, DimensionUnit
from purplship.core.models import RateDetails, Message, ChargeDetails, RateRequest
from purplship.providers.dhl.units import (
    Product,
    ProductCode,
    DCTPackageType,
    PackagePresets,
    SpecialServiceCode,
    NetworkType,
)
from purplship.providers.dhl.utils import Settings
from purplship.providers.dhl.error import parse_error_response


def parse_dct_response(
    response: Element, settings: Settings
) -> Tuple[List[RateDetails], List[Message]]:
    qtdshp_list = response.xpath(".//*[local-name() = $name]", name="QtdShp")
    quotes: List[RateDetails] = [
        _extract_quote(qtdshp_node, settings) for qtdshp_node in qtdshp_list
    ]
    return (
        [quote for quote in quotes if quote is not None],
        parse_error_response(response, settings)
    )


def _extract_quote(qtdshp_node: Element, settings: Settings) -> RateDetails:
    qtdshp = ResponseQtdShpType()
    qtdshp.build(qtdshp_node)
    if qtdshp.ShippingCharge is None or qtdshp.ShippingCharge == 0:
        return None

    ExtraCharges = list(
        map(
            lambda s: ChargeDetails(
                name=s.LocalServiceTypeName, amount=decimal(s.ChargeValue or 0)
            ),
            qtdshp.QtdShpExChrg,
        )
    )
    Discount_ = reduce(
        lambda d, ec: d + ec.amount if "Discount" in ec.name else d, ExtraCharges, 0.0
    )
    DutiesAndTaxes_ = reduce(
        lambda d, ec: d + ec.amount if "TAXES PAID" in ec.name else d, ExtraCharges, 0.0
    )
    delivery_date = to_date(qtdshp.DeliveryDate[0].DlvyDateTime, "%Y-%m-%d %H:%M:%S")
    pricing_date = to_date(qtdshp.PricingDate)
    transit = (
        (delivery_date - pricing_date).days if all([delivery_date, pricing_date]) else None
    )
    service_name = next(
        (p.name for p in Product if p.value in qtdshp.LocalProductName),
        qtdshp.LocalProductName,
    )
    return RateDetails(
        carrier_name=settings.carrier_name,
        carrier_id=settings.carrier_id,
        currency=qtdshp.CurrencyCode,
        transit_days=transit,
        service=service_name,
        base_charge=decimal(qtdshp.WeightCharge),
        total_charge=decimal(qtdshp.ShippingCharge),
        duties_and_taxes=decimal(DutiesAndTaxes_),
        discount=decimal(Discount_),
        extra_charges=list(
            map(
                lambda s: ChargeDetails(
                    name=s.LocalServiceTypeName,
                    amount=decimal(s.ChargeValue),
                    currency=qtdshp.CurrencyCode
                ),
                qtdshp.QtdShpExChrg,
            )
        ),
    )


def dct_request(payload: RateRequest, settings: Settings) -> Serializable[DCTRequest]:
    packages = Packages(payload.parcels, PackagePresets, required=["weight"])
    options = Options(payload.options)
    is_international = payload.shipper.country_code != payload.recipient.country_code
    is_document = all([parcel.is_document for parcel in payload.parcels])
    is_dutiable = not is_document
    products = [
        ProductCode[svc].value
        for svc in payload.services
        if svc in ProductCode.__members__
    ]
    special_services = [
        SpecialServiceCode[s].value
        for s in payload.options.keys()
        if s in SpecialServiceCode.__members__
    ]
    if is_international and is_dutiable:
        special_services.append(SpecialServiceCode.dhl_paperless_trade.value)
    if len(products) == 0:
        if is_international:
            products = [
                (ProductCode.dhl_express_worldwide_doc if is_document else ProductCode.dhl_express_worldwide_nondoc).value
            ]
        else:
            products = [
                (ProductCode.dhl_express_easy_doc if is_document else ProductCode.dhl_express_easy_nondoc).value
            ]

    request = DCTRequest(
        GetQuote=GetQuoteType(
            Request=settings.Request(
                MetaData=MetaData(SoftwareName="3PV", SoftwareVersion=1.0)
            ),
            From=DCTFrom(
                CountryCode=payload.shipper.country_code,
                Postalcode=payload.shipper.postal_code,
                City=payload.shipper.city,
                Suburb=payload.shipper.state_code,
            ),
            To=DCTTo(
                CountryCode=payload.recipient.country_code,
                Postalcode=payload.recipient.postal_code,
                City=payload.recipient.city,
                Suburb=payload.recipient.state_code,
            ),
            BkgDetails=BkgDetailsType(
                PaymentCountryCode=payload.shipper.country_code,
                NetworkTypeCode=NetworkType.both_time_and_day_definite.value,
                WeightUnit=WeightUnit.LB.value,
                DimensionUnit=DimensionUnit.IN.value,
                ReadyTime=time.strftime("PT%HH%MM"),
                Date=time.strftime("%Y-%m-%d"),
                IsDutiable=("Y" if is_dutiable else "N"),
                Pieces=PiecesType(
                    Piece=[
                        PieceType(
                            PieceID=package.parcel.id or f"{index}",
                            PackageTypeCode=DCTPackageType[
                                package.packaging_type or "your_packaging"
                            ].value,
                            Depth=package.length.IN,
                            Width=package.width.IN,
                            Height=package.height.IN,
                            Weight=package.weight.LB,
                        )
                        for index, package in enumerate(cast(Iterable[Package], packages), 1)
                    ]
                ),
                NumberOfPieces=len(packages),
                ShipmentWeight=packages.weight.LB,
                Volume=None,
                PaymentAccountNumber=settings.account_number,
                InsuredCurrency=options.currency if options.insurance is not None else None,
                InsuredValue=options.insurance.amount if options.insurance is not None else None,
                PaymentType=None,
                AcctPickupCloseTime=None,
                QtdShp=[
                    QtdShpType(
                        GlobalProductCode=product,
                        LocalProductCode=product,
                        QtdShpExChrg=[
                            QtdShpExChrgType(SpecialServiceType=service)
                            for service in special_services
                        ],
                    )
                    for product in products
                ],
            ),
            Dutiable=DCTDutiable(
                DeclaredValue=payload.options.get('value', 1.0),
                DeclaredCurrency=options.currency,
            ) if is_international and is_dutiable else None,
        ),
    )
    return Serializable(request, _request_serializer)


def _request_serializer(request: DCTRequest) -> str:
    namespacedef_ = (
        'xmlns:p="http://www.dhl.com" xmlns:p1="http://www.dhl.com/datatypes" xmlns:p2="http://www.dhl.com/DCTRequestdatatypes" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.dhl.com DCT-req.xsd "'
    )
    return export(
        request,
        name_="p:DCTRequest",
        namespacedef_=namespacedef_,
    ).replace('schemaVersion="2."', 'schemaVersion="2.0"')
