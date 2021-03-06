from dataclasses import dataclass
from typing import List, Type, Optional, Iterator, Iterable
from enum import Enum
from purplship.core.utils import decimal
from purplship.core.models import Insurance, COD, Notification, Parcel
from purplship.core.errors import FieldError, FieldErrorCode, MultiParcelNotSupportedError


@dataclass
class PackagePreset:
    width: float = None
    height: float = None
    length: float = None
    weight: float = None
    volume: float = None
    weight_unit: str = "LB"
    dimension_unit: str = "IN"
    packaging_type: str = None


class DocFormat(Enum):
    gif = "GIF"
    jpg = "JPG"
    pdf = "PDF"
    png = "PNG"


class PackagingUnit(Enum):
    envelope = "Small Envelope"
    pak = "Pak"
    tube = "Tube"
    pallet = "Pallet"
    small_box = "Small Box"
    medium_box = "Medium Box"
    your_packaging = "Your Packaging"


class PaymentType(Enum):
    sender = "SENDER"
    recipient = "RECIPIENT"
    third_party = "THIRD_PARTY"
    credit_card = "CARD"


class CreditCardType(Enum):
    visa = "Visa"
    mastercard = "Mastercard"
    american_express = "AmericanExpress"


class WeightUnit(Enum):
    KG = "KG"
    LB = "LB"


class DimensionUnit(Enum):
    CM = "CM"
    IN = "IN"


class Dimension:
    def __init__(self, value: float, unit: DimensionUnit = DimensionUnit.CM):
        self._value = value
        self._unit = unit

    @property
    def value(self):
        return self.__getattribute__(str(self._unit.name))

    @property
    def CM(self):
        if self._unit is None or self._value is None:
            return None
        if self._unit == DimensionUnit.CM:
            return decimal(self._value)
        else:
            return decimal(self._value * 0.393701)

    @property
    def IN(self):
        if self._unit is None or self._value is None:
            return None
        if self._unit == DimensionUnit.IN:
            return decimal(self._value)
        else:
            return decimal(self._value * 2.54)

    @property
    def M(self):
        if self._unit is None or self._value is None:
            return None
        else:
            return decimal(self.CM / 100)


class Volume:
    def __init__(
        self, side1: Dimension = None, side2: Dimension = None, side3: Dimension = None
    ):
        self._side1 = side1
        self._side2 = side2
        self._side3 = side3

    @property
    def value(self):
        if not any([self._side1.value, self._side2.value, self._side3.value]):
            return None

        return decimal(self._side1.M * self._side2.M * self._side3.M)

    @property
    def cubic_meter(self):
        if self.value is None:
            return None
        return decimal(self.value * 250)


class Girth:
    def __init__(
        self, side1: Dimension = None, side2: Dimension = None, side3: Dimension = None
    ):
        self._side1 = side1
        self._side2 = side2
        self._side3 = side3

    @property
    def value(self):
        sides = [self._side1.CM, self._side2.CM, self._side3.CM]
        if not any(sides):
            return None

        sides.sort()
        small_side1, small_side2, _ = sides
        return decimal((small_side1 + small_side2) * 2)


class Weight:
    def __init__(self, value: float, unit: WeightUnit = WeightUnit.KG):
        self._value = value
        self._unit = unit

    @property
    def value(self):
        return self.__getattribute__(str(self._unit.name))

    @property
    def KG(self):
        if self._unit is None or self._value is None:
            return None
        if self._unit == WeightUnit.KG:
            return decimal(self._value)
        elif self._unit == WeightUnit.LB:
            return decimal(self._value * 0.453592)

        return None

    @property
    def LB(self):
        if self._unit is None or self._value is None:
            return None
        if self._unit == WeightUnit.LB:
            return decimal(self._value)
        elif self._unit == WeightUnit.KG:
            return decimal(self._value * 2.204620823516057)

        return None

    @property
    def OZ(self):
        if self._unit is None or self._value is None:
            return None
        if self._unit == WeightUnit.LB:
            return decimal(self._value * 16)
        elif self._unit == WeightUnit.KG:
            return decimal(self._value * 35.274)

        return None


class Package:
    def __init__(self, parcel: Parcel, template: PackagePreset = None):
        self.parcel = parcel
        self.preset = template or PackagePreset()

    @property
    def dimension_unit(self):
        dimensions = [self.parcel.height, self.parcel.width, self.parcel.length]
        unit = (
            (self.parcel.dimension_unit or self.preset.dimension_unit)
            if any(dimensions)
            else self.preset.dimension_unit
        )

        return DimensionUnit[unit]

    @property
    def weight_unit(self):
        unit = (
            self.preset.weight_unit
            if self.parcel.weight is None
            else (self.parcel.weight_unit or self.preset.weight_unit)
        )

        return WeightUnit[unit]

    @property
    def packaging_type(self):
        return self.parcel.packaging_type or self.preset.packaging_type

    @property
    def weight(self):
        return Weight(self.parcel.weight or self.preset.weight, self.weight_unit)

    @property
    def width(self):
        return Dimension(self.preset.width or self.parcel.width, self.dimension_unit)

    @property
    def height(self):
        return Dimension(
            self.preset.height or self.parcel.height, self.dimension_unit
        )

    @property
    def length(self):
        return Dimension(
            self.preset.length or self.parcel.length, self.dimension_unit
        )

    @property
    def girth(self):
        return Girth(self.width, self.length, self.height)

    @property
    def volume(self):
        return Volume(self.width, self.length, self.height)

    @property
    def thickness(self):
        return Dimension(self.preset.thickness, self.dimension_unit)


class Packages(Iterable[Package]):
    def __init__(self, parcels: List[Parcel], presets: Type[Enum] = None, required: List[str] = None):
        def compute_preset(parcel) -> Optional[PackagePreset]:
            if (presets is None) | (presets is not None and parcel.package_preset not in presets.__members__):
                return None

            return presets[parcel.package_preset].value

        self._items = [Package(parcel, compute_preset(parcel)) for parcel in parcels]

        if required is not None:
            errors = {}
            for index, package in enumerate(self._items):
                for field in required:
                    prop = getattr(package, field)

                    if prop is None or (hasattr(prop, 'value') and prop.value is None):
                        errors.update({f"parcel[{index}].{field}": FieldErrorCode.required})

            if any(errors.items()):
                raise FieldError(errors)

    def __getitem__(self, index: int) -> Package:
        return self._items[index]

    def __len__(self):
        return len(self._items)

    def __iter__(self) -> Iterator[Package]:
        return iter(self._items)

    @property
    def single(self) -> Package:
        if len(self._items) > 1:
            raise MultiParcelNotSupportedError()
        return self._items[0]

    @property
    def weight(self) -> Weight:
        return Weight(
            unit=WeightUnit.LB,
            value=sum(pkg.weight.LB for pkg in self._items if pkg.weight.value is not None) or None
        )


class Options:
    def __init__(self, payload: dict):
        self._payload = payload

    @property
    def has_content(self):
        return any(o for o in self._payload if o in Options.Code.__members__)

    @property
    def cash_on_delivery(self):
        if Options.Code.cash_on_delivery.name in self._payload:
            return COD(**self._payload[Options.Code.cash_on_delivery.name])
        return None

    @property
    def currency(self):
        return self._payload.get(Options.Code.currency.name)

    @property
    def insurance(self):
        if Options.Code.insurance.name in self._payload:
            return Insurance(**self._payload[Options.Code.insurance.name])
        return None

    @property
    def notification(self):
        if Options.Code.notification.name in self._payload:
            return Notification(**self._payload[Options.Code.notification.name])
        return None

    @property
    def printing(self):
        return self._payload.get(Options.Code.printing.name)

    class Code(Enum):  # TODO:: Need to be documented
        cash_on_delivery = "COD"
        currency = "currency"
        insurance = "insurance"
        notification = "notification"
        printing = "printing"


class Phone:
    def __init__(self, phone_number: str = None):
        self.number = phone_number
        self.parts = phone_number.split(" ") if phone_number is not None else []

    @property
    def country_code(self):
        return next((part for part in self.parts), None)

    @property
    def area_code(self):
        return next(
            (part[1] for part in [self.parts] if len(part) > 1),
            None
        )

    @property
    def phone(self):
        return next(
            (part[2] for part in [self.parts] if len(part) > 2),
            None
        )


class PrinterType(Enum):
    regular = "Regular"  # Regular
    thermal = "Thermal"  # Thermal


class Currency(Enum):
    EUR = "Euro"
    AED = "UAE Dirham"
    USD = "US Dollar"
    XCD = "East Caribbean Dollar"
    AMD = "Dran"
    ANG = "Netherlands Antilles Guilder"
    AOA = "Kwanza"
    ARS = "Argentine Peso"
    AUD = "Australian Dollar"
    AWG = "Aruba Guilder"
    AZN = "Manat"
    BAM = "Convertible Marks"
    BBD = "Barbadian Dollar"
    BDT = "Taka"
    XOF = "CFA Franc West Africa"
    BGN = "Bulgarian Lev"
    BHD = "Bahraini Dinar"
    BIF = "Burundese Franc"
    BMD = "Bermudian Dollar"
    BND = "Brunei Dollar"
    BOB = "Boliviano"
    BRL = "Real"
    BSD = "Bahamian Dollar"
    BTN = "Ngultrum"
    BWP = "Pula"
    BYN = "Belarussian Ruble"
    BZD = "Belize Dollar"
    CAD = "Canadian Dollar"
    CDF = "Franc Congolais"
    XAF = "CFA Franc Central Africa"
    CHF = "Swiss Franc"
    NZD = "New Zealand Dollar"
    CLP = "New Chile Peso"
    CNY = "Yuan (Ren Min Bi)"
    COP = "Colombian Peso"
    CRC = "Costa Rican Colon"
    CUC = "Peso Convertible"
    CVE = "Cape Verde Escudo"
    CZK = "Czech Koruna"
    DJF = "Djibouti Franc"
    DKK = "Danish Krone"
    DOP = "Dominican Republic Peso"
    DZD = "Algerian Dinar"
    EGP = "Egyptian Pound"
    ERN = "Nakfa"
    ETB = "Birr"
    FJD = "Fijian Dollar"
    GBP = "Pound Sterling"
    GEL = "Georgian Lari"
    GHS = "Cedi"
    GMD = "Dalasi"
    GNF = "Guinea Franc"
    GTQ = "Quetzal"
    GYD = "Guyanan Dollar"
    HKD = "Hong Kong Dollar"
    HNL = "Lempira"
    HRK = "Croatian Kuna"
    HTG = "Gourde"
    HUF = "Forint"
    IDR = "Rupiah"
    ILS = "New Israeli Shekel"
    INR = "Indian Rupee"
    IRR = "Iranian Rial"
    ISK = "Icelandic Krona"
    JMD = "Jamaican Dollar"
    JOD = "Jordanian Dinar"
    JPY = "Yen"
    KES = "Kenyan Shilling"
    KGS = "Som"
    KHR = "Khmer Rial"
    KMF = "Comoros Franc"
    KPW = "North Korean Won"
    KRW = "Won"
    KWD = "Kuwaiti Dinar"
    KYD = "Cayman Islands Dollar"
    KZT = "Tenge"
    LAK = "Kip"
    LKR = "Sri Lankan Rupee"
    LRD = "Liberian Dollar"
    LSL = "Loti"
    LYD = "Libyan Dinar"
    MAD = "Moroccan Dirham"
    MDL = "Leu"
    MGA = "Ariary"
    MKD = "Denar"
    MMK = "Kyat"
    MNT = "Tugrik"
    MOP = "Pataca"
    MRO = "Ouguiya"
    MUR = "Mauritius Rupee"
    MVR = "Rufiyaa"
    MWK = "Kwacha"
    MXN = "Mexican Nuevo Peso"
    MYR = "Ringgit"
    MZN = "Mozambique Metical"
    NAD = "Namibian Dollar"
    XPF = "CFP Franc"
    NGN = "Naira"
    NIO = "Cordoba Oro"
    NOK = "Norwegian Krone"
    NPR = "Nepalese Rupee"
    OMR = "Omani Rial"
    PEN = "Nuevo Sol"
    PGK = "Kina"
    PHP = "Phillipines Peso"
    PKR = "Pakistani Rupee"
    PLN = "Zloty"
    PYG = "Guarani"
    QAR = "Qatar Rial"
    RON = "Leu"
    RSD = "Serbia, Dinars"
    RUB = "Russian Ruble"
    RWF = "Rwanda Franc"
    SAR = "Saudi Riyal"
    SBD = "Solomon Islands Dollar"
    SCR = "Seychelles Rupee"
    SDG = "Sudanese Pound"
    SEK = "Swedish Krona"
    SGD = "Singapore Dollar"
    SHP = "St. Helena Pound"
    SLL = "Leone"
    SOS = "Somali Shilling"
    SRD = "Suriname Dollar"
    SSP = "South Sudanese pound"
    STD = "Dobra"
    SYP = "Syrian Pound"
    SZL = "Lilangeni"
    THB = "Baht"
    TJS = "Somoni"
    TND = "Tunisian Dinar"
    TOP = "Pa'anga"
    TRY = "New Turkish Lira"
    TTD = "Trinidad and Tobago Dollar"
    TWD = "New Taiwan Dollar"
    TZS = "Tanzanian Shilling"
    UAH = "Hryvna"
    UYU = "Peso Uruguayo"
    UZS = "Sum"
    VEF = "Bolivar Fuerte"
    VND = "Dong"
    VUV = "Vanuatu Vatu"
    WST = "Tala"
    YER = "Yemeni Riyal"
    ZAR = "South African Rand"
    ZMW = "Kwacha"


class Country(Enum):
    AD = "ANDORRA"
    AE = "UNITED ARAB EMIRATES"
    AF = "AFGHANISTAN"
    AG = "ANTIGUA"
    AI = "ANGUILLA"
    AL = "ALBANIA"
    AM = "ARMENIA"
    AN = "NETHERLANDS ANTILLES"
    AO = "ANGOLA"
    AR = "ARGENTINA"
    AS = "AMERICAN SAMOA"
    AT = "AUSTRIA"
    AU = "AUSTRALIA"
    AW = "ARUBA"
    AZ = "AZERBAIJAN"
    BA = "BOSNIA AND HERZEGOVINA"
    BB = "BARBADOS"
    BD = "BANGLADESH"
    BE = "BELGIUM"
    BF = "BURKINA FASO"
    BG = "BULGARIA"
    BH = "BAHRAIN"
    BI = "BURUNDI"
    BJ = "BENIN"
    BM = "BERMUDA"
    BN = "BRUNEI"
    BO = "BOLIVIA"
    BR = "BRAZIL"
    BS = "BAHAMAS"
    BT = "BHUTAN"
    BW = "BOTSWANA"
    BY = "BELARUS"
    BZ = "BELIZE"
    CA = "CANADA"
    CD = "CONGO, THE DEMOCRATIC REPUBLIC OF"
    CF = "CENTRAL AFRICAN REPUBLIC"
    CG = "CONGO"
    CH = "SWITZERLAND"
    CI = "COTE D IVOIRE"
    CK = "COOK ISLANDS"
    CL = "CHILE"
    CM = "CAMEROON"
    CN = "CHINA, PEOPLES REPUBLIC"
    CO = "COLOMBIA"
    CR = "COSTA RICA"
    CU = "CUBA"
    CV = "CAPE VERDE"
    CY = "CYPRUS"
    CZ = "CZECH REPUBLIC, THE"
    DE = "GERMANY"
    DJ = "DJIBOUTI"
    DK = "DENMARK"
    DM = "DOMINICA"
    DO = "DOMINICAN REPUBLIC"
    DZ = "ALGERIA"
    EC = "ECUADOR"
    EE = "ESTONIA"
    EG = "EGYPT"
    ER = "ERITREA"
    ES = "SPAIN"
    ET = "ETHIOPIA"
    FI = "FINLAND"
    FJ = "FIJI"
    FK = "FALKLAND ISLANDS"
    FM = "MICRONESIA, FEDERATED STATES OF"
    FO = "FAROE ISLANDS"
    FR = "FRANCE"
    GA = "GABON"
    GB = "UNITED KINGDOM"
    GD = "GRENADA"
    GE = "GEORGIA"
    GF = "FRENCH GUYANA"
    GG = "GUERNSEY"
    GH = "GHANA"
    GI = "GIBRALTAR"
    GL = "GREENLAND"
    GM = "GAMBIA"
    GN = "GUINEA REPUBLIC"
    GP = "GUADELOUPE"
    GQ = "GUINEA-EQUATORIAL"
    GR = "GREECE"
    GT = "GUATEMALA"
    GU = "GUAM"
    GW = "GUINEA-BISSAU"
    GY = "GUYANA (BRITISH)"
    HK = "HONG KONG"
    HN = "HONDURAS"
    HR = "CROATIA"
    HT = "HAITI"
    HU = "HUNGARY"
    IC = "CANARY ISLANDS, THE"
    ID = "INDONESIA"
    IE = "IRELAND, REPUBLIC OF"
    IL = "ISRAEL"
    IN = "INDIA"
    IQ = "IRAQ"
    IR = "IRAN (ISLAMIC REPUBLIC OF)"
    IS = "ICELAND"
    IT = "ITALY"
    JE = "JERSEY"
    JM = "JAMAICA"
    JO = "JORDAN"
    JP = "JAPAN"
    KE = "KENYA"
    KG = "KYRGYZSTAN"
    KH = "CAMBODIA"
    KI = "KIRIBATI"
    KM = "COMOROS"
    KN = "ST. KITTS"
    KP = "KOREA, THE D.P.R OF (NORTH K.)"
    KR = "KOREA, REPUBLIC OF (SOUTH K.)"
    KV = "KOSOVO"
    KW = "KUWAIT"
    KY = "CAYMAN ISLANDS"
    KZ = "KAZAKHSTAN"
    LA = "LAO PEOPLES DEMOCRATIC REPUBLIC"
    LB = "LEBANON"
    LC = "ST. LUCIA"
    LI = "LIECHTENSTEIN"
    LK = "SRI LANKA"
    LR = "LIBERIA"
    LS = "LESOTHO"
    LT = "LITHUANIA"
    LU = "LUXEMBOURG"
    LV = "LATVIA"
    LY = "LIBYA"
    MA = "MOROCCO"
    MC = "MONACO"
    MD = "MOLDOVA, REPUBLIC OF"
    ME = "MONTENEGRO, REPUBLIC OF"
    MG = "MADAGASCAR"
    MH = "MARSHALL ISLANDS"
    MK = "MACEDONIA, REPUBLIC OF"
    ML = "MALI"
    MM = "MYANMAR"
    MN = "MONGOLIA"
    MO = "MACAU"
    MP = "COMMONWEALTH NO. MARIANA ISLANDS"
    MQ = "MARTINIQUE"
    MR = "MAURITANIA"
    MS = "MONTSERRAT"
    MT = "MALTA"
    MU = "MAURITIUS"
    MV = "MALDIVES"
    MW = "MALAWI"
    MX = "MEXICO"
    MY = "MALAYSIA"
    MZ = "MOZAMBIQUE"
    NA = "NAMIBIA"
    NC = "NEW CALEDONIA"
    NE = "NIGER"
    NG = "NIGERIA"
    NI = "NICARAGUA"
    NL = "NETHERLANDS, THE"
    NO = "NORWAY"
    NP = "NEPAL"
    NR = "NAURU, REPUBLIC OF"
    NU = "NIUE"
    NZ = "NEW ZEALAND"
    OM = "OMAN"
    PA = "PANAMA"
    PE = "PERU"
    PF = "TAHITI"
    PG = "PAPUA NEW GUINEA"
    PH = "PHILIPPINES, THE"
    PK = "PAKISTAN"
    PL = "POLAND"
    PR = "PUERTO RICO"
    PT = "PORTUGAL"
    PW = "PALAU"
    PY = "PARAGUAY"
    QA = "QATAR"
    RE = "REUNION, ISLAND OF"
    RO = "ROMANIA"
    RS = "SERBIA, REPUBLIC OF"
    RU = "RUSSIAN FEDERATION, THE"
    RW = "RWANDA"
    SA = "SAUDI ARABIA"
    SB = "SOLOMON ISLANDS"
    SC = "SEYCHELLES"
    SD = "SUDAN"
    SE = "SWEDEN"
    SG = "SINGAPORE"
    SH = "SAINT HELENA"
    SI = "SLOVENIA"
    SK = "SLOVAKIA"
    SL = "SIERRA LEONE"
    SM = "SAN MARINO"
    SN = "SENEGAL"
    SO = "SOMALIA"
    SR = "SURINAME"
    SS = "SOUTH SUDAN"
    ST = "SAO TOME AND PRINCIPE"
    SV = "EL SALVADOR"
    SY = "SYRIA"
    SZ = "SWAZILAND"
    TC = "TURKS AND CAICOS ISLANDS"
    TD = "CHAD"
    TG = "TOGO"
    TH = "THAILAND"
    TJ = "TAJIKISTAN"
    TL = "TIMOR LESTE"
    TN = "TUNISIA"
    TO = "TONGA"
    TR = "TURKEY"
    TT = "TRINIDAD AND TOBAGO"
    TV = "TUVALU"
    TW = "TAIWAN"
    TZ = "TANZANIA"
    UA = "UKRAINE"
    UG = "UGANDA"
    US = "UNITED STATES OF AMERICA"
    UY = "URUGUAY"
    UZ = "UZBEKISTAN"
    VA = "VATICAN CITY STATE"
    VC = "ST. VINCENT"
    VE = "VENEZUELA"
    VG = "VIRGIN ISLANDS (BRITISH)"
    VI = "VIRGIN ISLANDS (US)"
    VN = "VIETNAM"
    VU = "VANUATU"
    WS = "SAMOA"
    XB = "BONAIRE"
    XC = "CURACAO"
    XE = "ST. EUSTATIUS"
    XM = "ST. MAARTEN"
    XN = "NEVIS"
    XS = "SOMALILAND, REP OF (NORTH SOMALIA)"
    XY = "ST. BARTHELEMY"
    YE = "YEMEN, REPUBLIC OF"
    YT = "MAYOTTE"
    ZA = "SOUTH AFRICA"
    ZM = "ZAMBIA"
    ZW = "ZIMBABWE"


class CountryCurrency(Enum):
    AD = "EUR"
    AE = "AED"
    AF = "USD"
    AG = "XCD"
    AI = "XCD"
    AL = "EUR"
    AM = "AMD"
    AN = "ANG"
    AO = "AOA"
    AR = "ARS"
    AS = "USD"
    AT = "EUR"
    AU = "AUD"
    AW = "AWG"
    AZ = "AZN"
    BA = "BAM"
    BB = "BBD"
    BD = "BDT"
    BE = "EUR"
    BF = "XOF"
    BG = "BGN"
    BH = "BHD"
    BI = "BIF"
    BJ = "XOF"
    BM = "BMD"
    BN = "BND"
    BO = "BOB"
    BR = "BRL"
    BS = "BSD"
    BT = "BTN"
    BW = "BWP"
    BY = "BYN"
    BZ = "BZD"
    CA = "CAD"
    CD = "CDF"
    CF = "XAF"
    CG = "XAF"
    CH = "CHF"
    CI = "XOF"
    CK = "NZD"
    CL = "CLP"
    CM = "XAF"
    CN = "CNY"
    CO = "COP"
    CR = "CRC"
    CU = "CUC"
    CV = "CVE"
    CY = "EUR"
    CZ = "CZK"
    DE = "EUR"
    DJ = "DJF"
    DK = "DKK"
    DM = "XCD"
    DO = "DOP"
    DZ = "DZD"
    EC = "USD"
    EE = "EUR"
    EG = "EGP"
    ER = "ERN"
    ES = "EUR"
    ET = "ETB"
    FI = "EUR"
    FJ = "FJD"
    FK = "GBP"
    FM = "USD"
    FO = "DKK"
    FR = "EUR"
    GA = "XAF"
    GB = "GBP"
    GD = "XCD"
    GE = "GEL"
    GF = "EUR"
    GG = "GBP"
    GH = "GHS"
    GI = "GBP"
    GL = "DKK"
    GM = "GMD"
    GN = "GNF"
    GP = "EUR"
    GQ = "XAF"
    GR = "EUR"
    GT = "GTQ"
    GU = "USD"
    GW = "XOF"
    GY = "GYD"
    HK = "HKD"
    HN = "HNL"
    HR = "HRK"
    HT = "HTG"
    HU = "HUF"
    IC = "EUR"
    ID = "IDR"
    IE = "EUR"
    IL = "ILS"
    IN = "INR"
    IQ = "USD"
    IR = "IRR"
    IS = "ISK"
    IT = "EUR"
    JE = "GBP"
    JM = "JMD"
    JO = "JOD"
    JP = "JPY"
    KE = "KES"
    KG = "KGS"
    KH = "KHR"
    KI = "AUD"
    KM = "KMF"
    KN = "XCD"
    KP = "KPW"
    KR = "KRW"
    KV = "EUR"
    KW = "KWD"
    KY = "KYD"
    KZ = "KZT"
    LA = "LAK"
    LB = "USD"
    LC = "XCD"
    LI = "CHF"
    LK = "LKR"
    LR = "LRD"
    LS = "LSL"
    LT = "EUR"
    LU = "EUR"
    LV = "EUR"
    LY = "LYD"
    MA = "MAD"
    MC = "EUR"
    MD = "MDL"
    ME = "EUR"
    MG = "MGA"
    MH = "USD"
    MK = "MKD"
    ML = "XOF"
    MM = "MMK"
    MN = "MNT"
    MO = "MOP"
    MP = "USD"
    MQ = "EUR"
    MR = "MRO"
    MS = "XCD"
    MT = "EUR"
    MU = "MUR"
    MV = "MVR"
    MW = "MWK"
    MX = "MXN"
    MY = "MYR"
    MZ = "MZN"
    NA = "NAD"
    NC = "XPF"
    NE = "XOF"
    NG = "NGN"
    NI = "NIO"
    NL = "EUR"
    NO = "NOK"
    NP = "NPR"
    NR = "AUD"
    NU = "NZD"
    NZ = "NZD"
    OM = "OMR"
    PA = "USD"
    PE = "PEN"
    PF = "XPF"
    PG = "PGK"
    PH = "PHP"
    PK = "PKR"
    PL = "PLN"
    PR = "USD"
    PT = "EUR"
    PW = "USD"
    PY = "PYG"
    QA = "QAR"
    RE = "EUR"
    RO = "RON"
    RS = "RSD"
    RU = "RUB"
    RW = "RWF"
    SA = "SAR"
    SB = "SBD"
    SC = "SCR"
    SD = "SDG"
    SE = "SEK"
    SG = "SGD"
    SH = "SHP"
    SI = "EUR"
    SK = "EUR"
    SL = "SLL"
    SM = "EUR"
    SN = "XOF"
    SO = "SOS"
    SR = "SRD"
    SS = "SSP"
    ST = "STD"
    SV = "USD"
    SY = "SYP"
    SZ = "SZL"
    TC = "USD"
    TD = "XAF"
    TG = "XOF"
    TH = "THB"
    TJ = "TJS"
    TL = "USD"
    TN = "TND"
    TO = "TOP"
    TR = "TRY"
    TT = "TTD"
    TV = "AUD"
    TW = "TWD"
    TZ = "TZS"
    UA = "UAH"
    UG = "USD"
    US = "USD"
    UY = "UYU"
    UZ = "UZS"
    VA = "EUR"
    VC = "XCD"
    VE = "VEF"
    VG = "USD"
    VI = "USD"
    VN = "VND"
    VU = "VUV"
    WS = "WST"
    XB = "EUR"
    XC = "EUR"
    XE = "ANG"
    XM = "EUR"
    XN = "XCD"
    XS = "USD"
    XY = "ANG"
    YE = "YER"
    YT = "EUR"
    ZA = "ZAR"
    ZM = "ZMW"
    ZW = "USD"


class CountryState(Enum):
    AE = Enum("State", {
        "AB": "Abu Dhabi",
        "AJ": "Ajman",
        "DU": "Dubai",
        "FU": "Fujairah",
        "RA": "Ras al-Khaimah",
        "SH": "Sharjah",
        "UM": "Umm al-Qaiwain",
    })
    CA = Enum("State", {
        "AB": "Alberta",
        "BC": "British Columbia",
        "MB": "Manitoba",
        "NB": "New Brunswick",
        "NL": "Newfoundland",
        "NT": "Northwest Territories",
        "NS": "Nova Scotia",
        "NU": "Nunavut",
        "ON": "Ontario",
        "PE": "Prince Edward Island",
        "QC": "Quebec",
        "SK": "Saskatchewan",
        "YT": "Yukon",
    })
    CN = Enum("State", {
        "anhui": "Anhui",
        "hainan": "Hainan",
        "jiangxi": "Jiangxi",
        "shanghai": "Shanghai",
        "beijing": "Beijing",
        "hebei": "Hebei",
        "jilin": "Jilin",
        "shanxi": "Shanxi",
        "chongqing": "Chongqing",
        "heilongjiang": "Heilongjiang",
        "liaoning": "Liaoning",
        "sichuan": "Sichuan",
        "fujian": "Fujian",
        "henan": "Henan",
        "nei_mongol": "Nei Mongol",
        "tianjin": "Tianjin",
        "gansu": "Gansu",
        "hubei": "Hubei",
        "qinghai": "Qinghai",
        "xinjiang": "Xinjiang",
        "guangdong": "Guangdong",
        "hunan": "Hunan",
        "shaanxi": "Shaanxi",
        "yunnan": "Yunnan",
        "guizhou": "Guizhou",
        "jiangsu": "Jiangsu",
        "shandong": "Shandong",
        "zhejiang": "Zhejiang",
    })
    IN = Enum("State", {
        "AN": "Andaman & Nicobar (U.T)",
        "AP": "Andhra Pradesh",
        "AR": "Arunachal Pradesh",
        "AS": "Assam",
        "BR": "Bihar",
        "CG": "Chattisgarh",
        "CH": "Chandigarh (U.T.)",
        "DD": "Daman & Diu (U.T.)",
        "DL": "Delhi (U.T.)",
        "DN": "Dadra and Nagar Haveli (U.T.)",
        "GA": "Goa",
        "GJ": "Gujarat",
        "HP": "Himachal Pradesh",
        "HR": "Haryana",
        "JH": "Jharkhand",
        "JK": "Jammu & Kashmir",
        "KA": "Karnataka",
        "KL": "Kerala",
        "LD": "Lakshadweep (U.T)",
        "MH": "Maharashtra",
        "ML": "Meghalaya",
        "MN": "Manipur",
        "MP": "Madhya Pradesh",
        "MZ": "Mizoram",
        "NL": "Nagaland",
        "OR": "Orissa",
        "PB": "Punjab",
        "PY": "Puducherry (U.T.)",
        "RJ": "Rajasthan",
        "SK": "Sikkim",
        "TN": "Tamil Nadu",
        "TR": "Tripura",
        "UA": "Uttaranchal",
        "UP": "Uttar Pradesh",
        "WB": "West Bengal",
    })
    MX = Enum("State", {
        "AG": "Aguascalientes",
        "BC": "Baja California",
        "BS": "Baja California Sur",
        "CM": "Campeche",
        "CS": "Chiapas",
        "CH": "Chihuahua",
        "CO": "Coahuila",
        "CL": "Colima",
        "DF": "Ciudad de México",
        "DG": "Durango",
        "GT": "Guanajuato",
        "GR": "Guerrero",
        "HG": "Hidalgo",
        "JA": "Jalisco",
        "EM": "Estado de México",
        "MI": "Michoacán",
        "MO": "Morelos",
        "NA": "Nayarit",
        "NL": "Nuevo León",
        "OA": "Oaxaca",
        "PU": "Puebla",
        "QE": "Querétaro",
        "QR": "Quintana Roo",
        "SL": "San Luis Potosí",
        "SI": "Sinaloa",
        "SO": "Sonora",
        "TB": "Tabasco",
        "TM": "Tamaulipas",
        "TL": "Tlaxcala",
        "VE": "Veracruz",
        "YU": "Yucatán",
        "ZA": "Zacatecas",
    })
    US = Enum("State", {
        "AL": "Alabama",
        "AK": "Alaska",
        "AZ": "Arizona",
        "AR": "Arkansas",
        "CA": "California",
        "CO": "Colorado",
        "CT": "Connecticut",
        "DE": "Delaware",
        "DC": "District of Columbia",
        "FL": "Florida",
        "GA": "Georgia",
        "HI": "Hawaii",
        "ID": "Idaho",
        "IL": "Illinois",
        "IN": "Indiana",
        "IA": "Iowa",
        "KS": "Kansas",
        "KY": "Kentucky",
        "LA": "Louisiana",
        "ME": "Maine",
        "MD": "Maryland",
        "MA": "Massachusetts",
        "MI": "Michigan",
        "MN": "Minnesota",
        "MS": "Mississippi",
        "MO": "Missouri",
        "MT": "Montana",
        "NE": "Nebraska",
        "NV": "Nevada",
        "NH": "New Hampshire",
        "NJ": "New Jersey",
        "NM": "New Mexico",
        "NY": "New York",
        "NC": "North Carolina",
        "ND": "North Dakota",
        "OH": "Ohio",
        "OK": "Oklahoma",
        "OR": "Oregon",
        "PA": "Pennsylvania",
        "RI": "Rhode Island",
        "SC": "South Carolina",
        "SD": "South Dakota",
        "TN": "Tennessee",
        "TX": "Texas",
        "UT": "Utah",
        "VT": "Vermont",
        "VA": "Virginia",
        "WA": "Washington State",
        "WV": "West Virginia",
        "WI": "Wisconsin",
        "WY": "Wyoming",
        "PR": "Puerto Rico",
    })
