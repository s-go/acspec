
from six import iteritems

from schematics.models import Model as SchematicsModel
from schematics.models import FieldDescriptor
from schematics.models import metacopy
from schematics.types import StringType, BooleanType, BaseType, IntType
from schematics.types import FloatType, LongType, DateType, DateTimeType
from schematics.types.compound import ListType, DictType, ModelType
from schematics.exceptions import ValidationError

from acspec.dsl import iterspec, get_option

# [
#     'UUIDType', 'IntType', 'EmailType', 'BooleanType', 'DateType',
#     'DecimalType', 'StringType', 'URLType', 'FloatType', 'MD5Type',
#     'NumberType', 'BaseType', 'SHA1Type', 'LongType', 'GeoPointType',
#     'HashType', 'IPv4Type', 'DateTimeType', 'MultilingualStringType'
# ]

TO_SCHEMATICS_TYPE = {
    "string": StringType,
    "integer": IntType,
    "float": FloatType,
    "long": LongType,
    "date": DateType,
    "timestamp": DateType,
    "date_time": DateTimeType,
    "boolean": BooleanType,
    "model": ModelType,
    "list": ListType,
    "dict": DictType,
    "base": BaseType,
}

TO_ACSPEC_TYPE = {
    v: k
    for k, v in iteritems(TO_SCHEMATICS_TYPE)
}


class AcspecContextError(Exception):
    pass


class UnresolvedModelError(Exception):
    pass

class MissingBaseClassMappingError(Exception):
    pass


class BaseModel(SchematicsModel):

    @classmethod
    def append_field(cls, name, field):
        if isinstance(field, BaseType):
            # set owner_model like is done by schematics metaclass
            field.owner_model = cls
            field.name = name
            if hasattr(field, 'field'):
                field.field.owner_model = cls

            cls._fields[name] = field

            field_descriptor = FieldDescriptor(name)

            # as schematics works like this, we need to copy the field
            # to the subclasses
            for subclass in cls._subclasses:
                if name not in subclass._fields:
                    subclass._fields[name] = metacopy(field)
                    subclass._fields[name].owner_model = subclass

            # fix not to break the schematics model accidentially
            # TODO make the renaming transparent
            if name == "fields":
                setattr(cls, "_" + name, field_descriptor)
            else:
                setattr(cls, name, field_descriptor)
        else:
            raise TypeError('field must be of type {}'.format(BaseType))


class DontSerializeWhenNoneModel(BaseModel):

    class Options:
        serialize_when_none = False


TYPE_KEYS = frozenset(["simple", "model", "list", "dict"])


def _type_keys_message(type_keys, data):
    r = []
    node_infos = {}
    for type_key in type_keys:
        if hasattr(data[type_key], 'node_info'):
            node_infos[type_key] = data[type_key].node_info
        r.append(type_key)
    r.sort()
    r = ", ".join(r)
    if node_infos:
        r += " ({})".format([
            "{}: {}:{}".format(
                k, v.start_mark.name, v.start_mark.line
            )
            for k, v in iteritems(node_infos)
        ])
    return r


class TypeInfo(BaseModel):
    simple = StringType(
        choices=list(TO_SCHEMATICS_TYPE.keys()), serialize_when_none=False
    )
    model = StringType(serialize_when_none=False)

    def convert(self, raw_data, **kw):
        if hasattr(raw_data, "node_info"):
            self.node_info = raw_data.node_info
        return super(TypeInfo, self).convert(raw_data, **kw)

    def validate_dict(self, data, value):
        """
            Validates mutual exclusive type keys. It uses the _dict prefix to
            correspend to the least added type.
            Other types to be mutual exclusive with are defined before.
        """
        data_keys = set([e for e in data.keys() if data[e]])
        type_keys = data_keys & TYPE_KEYS
        if len(type_keys) > 1:
            raise ValidationError(u'Cannot have multiple types: {}'.format(
                _type_keys_message(type_keys, data)
            ))
        if not type_keys or not any([t for t in type_keys]):
            raise ValidationError(
                u'Missing one field of {}'.format(", ".join(TYPE_KEYS))
            )
        return value

    def type(self):
        data = self.to_primitive()
        for type_key in TYPE_KEYS:
            if data.get(type_key, None):
                return type_key
        return None

    def requires_context(self):
        info_type = self.type()
        if info_type == "model":
            return True
        elif info_type in ["dict", "list"]:
            return self[info_type].requires_context()
        else:
            return False

    def schematics_field_descriptor(
        self, context=None, nested=False, **kwargs
    ):
        info_type = self.type()

        if info_type == "simple":
            return TO_SCHEMATICS_TYPE[self[info_type]](**kwargs)
        elif info_type in ["dict", "list"]:
            return TO_SCHEMATICS_TYPE[info_type](
                self[info_type].schematics_field_descriptor(context=context),
                **kwargs
            )
        elif info_type == "model":
            if context is None:
                raise AcspecContextError("No context provided to resolve model")
            else:
                model_class = context.get_model_class(self.model)
                if model_class is None:
                    raise AcspecContextError(
                        "Model '{}' not found".format(model_class)
                    )
                return TO_SCHEMATICS_TYPE[self.type()](
                    model_class,
                    **kwargs
                )
        else:
            raise TypeError('Unknown field type {}'.format(info_type))

TypeInfo.append_field("list", ModelType(TypeInfo, serialize_when_none=False))
TypeInfo.append_field("dict", ModelType(TypeInfo, serialize_when_none=False))


class MetaFieldDescriptor(BaseModel):

    type = ModelType(TypeInfo, required=True)

    # Invalidate field when value is None or is not supplied. Default: False.
    required = BooleanType()
    # When no data is provided default to this value. May be a callable.
    # Default: None.
    default = BaseType()
    # The name of this field defaults to the class attribute used in the model.
    # However if the field has another name in foreign data set this argument.
    # Serialized data will use this value for the key name too.
    serialized_name = StringType()
    # A name or list of named fields for which foreign data sets are searched
    # to provide a value for the given field. This only effects inbound data.
    deserialize_from = ListType(StringType())
    # A list of valid choices. This is the last step of the validator chain.
    choices = ListType(BaseType())
    # A list of callables. Each callable receives the value after it has been
    # converted into a rich python type. Default: []
    # validators = ListType(StringType())
    # Dictates if the field should appear in the serialized data even if the
    # value is None. Default: True
    serialize_when_none = BooleanType()
    # Override the error messages with a dict. You can also do this by
    # subclassing the Type and defining a MESSAGES dict attribute on the class.
    # A metaclass will merge all the MESSAGES and override the resulting dict
    # with instance level messages and assign to self.messages.
    messages = DictType(StringType())

    def schematics_field_descriptor(self, context=None):
        return self.type.schematics_field_descriptor(
            context=context,
            **self._kwargs()
        )

    def requires_context(self):
        return self.type.requires_context()

    def _kwargs(self):
        return {
            k: v
            for k, v in iteritems(self.to_primitive())
            if k not in ["type"]
        }


class ResolveableModel(object):

    def __init__(self, model_class, contextual_type_specs):
        self.model_class = model_class
        self.contextual_type_specs = contextual_type_specs
        self.resolved = False

    def resolve(self, context):
        for name, type_spec in iteritems(self.contextual_type_specs):
            self.model_class.append_field(
                name,
                type_spec.schematics_field_descriptor(context=context)
            )
        self.resolved = True
        return self.model_class


DEFAULT_MAPPINGS = {
    "dont_serialize_when_none": DontSerializeWhenNoneModel
}


def _find_base_classes(name, spec, class_mapping=None):
    if class_mapping is None:
        class_mapping = {}
    for k, v in iteritems(DEFAULT_MAPPINGS):
        if k not in class_mapping:
            class_mapping[k] = v

    r = []
    for base in get_option(spec, 'bases', []):
        if base in class_mapping:
            r.append(class_mapping[base])
        else:
            raise MissingBaseClassMappingError(
                "Please provide a class_mapping for {}".format(base)
            )

    # TODO: how to provide additional mappings for a model name?
    # Note: the next lines conflict if models inherit from each other
    # if name in class_mapping:
    #     r.append(class_mapping[name])

    if not any([isinstance(base, BaseModel) for base in r]):
        r.append(BaseModel)

    return tuple(r)


def ResolveableModelFactory(name, spec, class_mapping=None):
    bases = _find_base_classes(name, spec, class_mapping)

    model_class = type(str(name), bases, {})
    contextual_type_specs = {}

    for k, v in iterspec(spec):
        type_spec = MetaFieldDescriptor(v, strict=False)
        type_spec.validate()
        if type_spec.requires_context():
            contextual_type_specs[k] = type_spec
        else:
            model_class.append_field(
                k,
                type_spec.schematics_field_descriptor()
            )

    return ResolveableModel(model_class, contextual_type_specs)


# def ModelFactory(name, spec, class_mapping=None, context=None):
#     bases = _find_base_classes(name, spec, class_mapping)
#
#     model_class = type(name, bases, {})
#
#     for k, v in iterspec(spec):
#         type_spec = MetaFieldDescriptor(v, strict=False)
#         type_spec.validate()
#         if type_spec.requires_context():
#             if context is None:
#                 raise AcspecContextError(
#                     "No context provided to resolve model"
#                 )
#
#         model_class.append_field(
#             k,
#             type_spec.schematics_field_descriptor(context=context)
#         )
#
#     return model_class
