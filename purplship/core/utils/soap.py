from typing import TypeVar, Type, Optional, cast
from pysoap.envelope import Header, Body, Envelope, Fault
from purplship.core.utils.xml import Element
from purplship.core.settings import Settings
from purplship.core.models import Message

T = TypeVar("T")


class GenerateDSAbstract:
    def build(self, *args):
        pass


def build(tp: Type[T], node: Element = None) -> Optional[T]:
    if node is None:
        return None

    instance = tp()
    cast(GenerateDSAbstract, instance).build(node)
    return instance


def create_envelope(
    body_content: Element,
    header_content: Element = None,
    header_prefix: str = None,
    body_prefix: str = None,
    header_tag_name: str = None,
    body_tag_name: str = None,
    envelope_prefix: str = "tns",
) -> Envelope:
    header = None
    if header_content is not None:
        header_content.ns_prefix_ = header_prefix or header_content.ns_prefix_
        header_content.original_tagname_ = (
            header_tag_name or header_content.original_tagname_
        )
        header = Header()
        header.add_anytypeobjs_(header_content)

    body_content.ns_prefix_ = body_prefix or body_content.ns_prefix_
    body_content.original_tagname_ = body_tag_name or body_content.original_tagname_
    body = Body()
    body.add_anytypeobjs_(body_content)

    envelope = Envelope(Header=header, Body=body)
    envelope.ns_prefix_ = envelope_prefix
    envelope.Body.ns_prefix_ = envelope.ns_prefix_
    if envelope.Header is not None:
        envelope.Header.ns_prefix_ = envelope.ns_prefix_
    return envelope


def clean_namespaces(
    envelope_str: str,
    envelope_prefix: str,
    body_child_name: str,
    header_child_name: str = "UnspecifiedTag",
    header_child_prefix: str = "",
    body_child_prefix: str = "",
):
    return (
        envelope_str.replace(
            "<%s%s" % (envelope_prefix, header_child_name),
            "<%s%s" % (header_child_prefix, header_child_name),
        )
        .replace(
            "</%s%s" % (envelope_prefix, header_child_name),
            "</%s%s" % (header_child_prefix, header_child_name),
        )
        .replace(
            "<%s%s" % (envelope_prefix, body_child_name),
            "<%s%s" % (body_child_prefix, body_child_name),
        )
        .replace(
            "</%s%s" % (envelope_prefix, body_child_name),
            "</%s%s" % (body_child_prefix, body_child_name),
        )
    )


def apply_namespaceprefix(item, prefix: str):
    if isinstance(item, list):
        [apply_namespaceprefix(child, prefix) for child in item]
    elif hasattr(item, 'export'):
        item.ns_prefix_ = prefix
        children = [(k, v) for k, v in item.__dict__.items() if '_' not in k and v is not None]
        for name, child in children:
            setattr(item, f'{name}_nsprefix_', prefix)
            apply_namespaceprefix(child, prefix)


def extract_fault(response: Element, settings: Type[Settings]) -> Message:
    faults = [build(Fault, node) for node in response.xpath(".//*[local-name() = $name]", name="Fault")]
    return [
        Message(
            code=fault.faultcode,
            message=fault.faultstring,
            carrier_name=settings.carrier_name,
            carrier_id=settings.carrier_id
        ) for fault in faults
    ]
