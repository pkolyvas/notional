"""Base classes for working with the Notion API."""

import logging
from abc import ABC
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel, TypeAdapter

# https://github.com/pydantic/pydantic/issues/6381
from pydantic._internal._model_construction import ModelMetaclass

logger = logging.getLogger(__name__)


_T = TypeVar("_T")


class SerializationMode(str, Enum):
    """Serialization mode for Notional objects."""

    JSON = "json"
    PYTHON = "python"
    API = PYTHON


class ComposableObjectMeta(ModelMetaclass):
    """Presents a metaclass that composes objects using simple values.

    This is primarily to allow easy definition of data objects without disrupting the
    `BaseModel` constructor.  e.g. rather than requiring a caller to understand how
    nested data works in the data objects, they can compose objects from simple values.

    Compare the following code for declaring a Paragraph:

    ```python
    # using nested data objects:
    text = "hello world"
    nested = TextObject._NestedData(content=text)
    rtf = text.TextObject(text=nested, plain_text=text)
    content = blocks.Paragraph._NestedData(text=[rtf])
    para = blocks.Paragraph(paragraph=content)

    # using a composable object:
    para = blocks.Paragraph["hello world"]
    ```

    Classes that support composition in this way must define and implement the internal
    `__compose__` method.  This method takes an arbitrary number of parameters, based
    on the needs of the implementation.  It is up to the implementing class to ensure
    that the parameters are specified correctly.
    """

    def __getitem__(cls: type[_T], params: Any) -> _T:
        """Return the requested class by composing using the given parameters.

        If the requested class does not expose the `__compose__` method, this will raise
        an exception.
        """

        compose: Callable[[Dict[str, Any]], _T] = getattr(cls, "__compose__", None)

        if compose is None:
            raise NotImplementedError(f"{cls} does not support object composition")

        # __getitem__ only accepts a single parameter...  if the caller provides
        # multiple params, they will be converted and passed as a tuple.  this method
        # also accepts a list for readability when composing from ORM properties

        if params and type(params) in (list, tuple):
            return compose(*params)

        return compose(params)


class NotionObject(BaseModel, ABC, metaclass=ComposableObjectMeta):
    """The base for all Notion API objects.

    As a general convention, data fields in lower case are defined by the Notion API.
    Properties in Title Case are provided for convenience (e.g. computed fields).
    """

    def update(self, **data):
        """Refresh the internal attributes with new data."""

        # Ref: https://github.com/pydantic/pydantic/discussions/3139

        # model_data = self.model_dump()
        # model_data.update(data)

        partial_model = self.model_validate(data)
        partial_data = partial_model.model_dump(exclude_defaults=True)

        for name, value in partial_data.items():
            logger.debug("set object data -- %s => %s", name, value)
            setattr(self, name, value)

        return self

    def serialize(self, mode=SerializationMode.API):
        """Convert to a suitable representation for the Notion API."""

        # TODO read-only fields should not be sent to the API
        # https://github.com/jheddings/notional/issues/9

        if mode == SerializationMode.PYTHON:
            return self.model_dump(mode="json", exclude_none=True, by_alias=True)

        if mode == SerializationMode.JSON:
            return self.model_dump_json(indent=None, exclude_none=True, by_alias=True)

        raise NotImplementedError(f"unsupported serialization mode: {mode}")

    @classmethod
    def deserialize(cls, data: Union[str, bytes, dict, list]):
        """Parse the given object as a Notion API object."""

        # make a list of all subclasses and their subclasses
        types = cls._find_all_possible_types()

        if len(types) > 1:
            adapter = TypeAdapter(Union[*types])
        elif len(types) > 0:
            adapter = TypeAdapter(types[0])
        else:
            raise RuntimeError(f"no available types for {cls}")

        if isinstance(data, (str, bytes)):
            return adapter.validate_json(data)

        return adapter.validate_python(data)

    @classmethod
    def _find_all_possible_types(cls):
        all_types = []

        if ABC not in cls.__bases__:
            all_types.append(cls)

        for subclass in cls.__subclasses__():
            more_types = subclass._find_all_possible_types()
            all_types.extend(more_types)

        return all_types


class AdaptiveObject(NotionObject, ABC):
    """Objects that may change type based on content.

    Subclasses of `AdaptiveObject` must register each subclass with the appropriate
    keywords.  This allows the `AdaptiveObject` to determine the correct type when
    deserializing from the Notion API.  To register a subclass as an adaptive type,
    call the `_register_adaptive_type` method with the appropriate keywords.  This
    is typically done in the `__init_subclass__` method of the parent class.

    This approach allows Notional to define new object types without requiring each
    object to enumerate all possible types.  For example, the `TextObject` may be
    represented as a `RichTextObject` or a `MentionObject` depending on the contents.

    Rather than using a discriminated union, Notional will use the `__notional_typemap__`
    to determine the concrete type of the object.  This allows the API to define new
    types without requiring changes to the Notional codebase.
    """

    # modified from the methods described in these discussions:
    # - https://github.com/pydantic/pydantic/discussions/3091
    # - https://github.com/pydantic/pydantic/discussions/5785

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """Initialize the subclass fields with the given keyword arguments."""
        super().__pydantic_init_subclass__(**kwargs)

        for name, value in kwargs.items():
            cls._update_field_schema(name, default=value)

        # rebuild the internal model with the updated field info
        # https://github.com/pydantic/pydantic/issues/6966

        cls.model_rebuild(force=True)

    @classmethod
    def _update_field_schema(cls, name, frozen=True, default=...):
        """Update the field definition for the given name.

        Note that this will only update the field definition; it will not update the
        internal model.  This is primarily used to update the default value for a field.
        """

        field = cls.model_fields.get(name)

        if not field:
            raise ValueError(f"unknown field: {name}")

        logger.debug("updating field info -- %s.%s => %s", cls.__name__, name, default)

        if default is not Ellipsis:
            field.default = default
            field.validate_default = False

        if frozen:
            field.frozen = True
            # field.annotation = Literal[default]

    @classmethod
    def _register_adaptive_type(cls, name, value):
        """Register the current class as an adaptive type."""

        if not hasattr(cls, "__notional_typemap__"):
            logger.debug("initializing typemap for %s", cls)
            cls.__notional_typemap__ = {}

        typemap = cls.__notional_typemap__.get(name)

        if typemap is None:
            typemap = {}

        if value in typemap:
            raise ValueError(f"Duplicate subtype for class - {name} [{value}] => {cls}")

        if value is not None:
            typemap[value] = cls

        logger.debug("registered new subtype: %s [%s] => %s", name, value, cls)

        cls.__notional_typemap__[name] = typemap

    @classmethod
    def _resolve_adaptive_type(cls, obj: Union[dict, "AdaptiveObject"]):
        """Instantiate the correct object based on the AdaptiveObject's typemap."""

        # if the object is already an instance of the requested class, return it
        if isinstance(obj, cls):
            return obj

        # XXX are there other cases we should handle?
        if not isinstance(obj, dict):
            raise ValueError("Invalid object")

        # this will only happen if subclasses forget to register adaptive types
        if not hasattr(cls, "__notional_typemap__"):
            raise TypeError(f"Missing typemap in {cls}")

        # check the typemap for an existing type discriminator
        for name, typemap in cls.__notional_typemap__.items():
            value = obj.get(name)

            if value is None:
                continue

            sub = typemap.get(value)

            if sub is None:
                raise TypeError(f"Unsupported sub-type: {name}={value}")

            logger.debug(
                "initializing adaptive object %s:%s => %s",
                cls.__name__,
                name,
                sub.__name__,
            )

            return sub.model_validate(obj)

        return super().model_validate(obj)


class DataObject(NotionObject, ABC):
    """A top-level Notion data object."""

    object: str
    id: Optional[UUID] = None

    # def __init_subclass__(cls, object: Optional[str] = None, **kwargs):
    #    """Initialize subtypes of this DataObject."""
    #    super().__init_subclass__(**kwargs)
    #    cls._register_adaptive_type("object", object)


class TypedObject(NotionObject, ABC):
    """A type-referenced object.

    Many objects in the Notion API follow a standard pattern with a 'type' property
    followed by additional data.  These objects must specify a `type` attribute to
    ensure that the correct object is created.

    For example, this contains a nested 'detail' object:

        data = {
            type: "detail",
            ...
            detail: {
                ...
            }
        }

    Calling the object provides direct access to the data stored in `{type}`.
    """

    type: str

    # def __init_subclass__(cls, type: Optional[str] = None, **kwargs):
    #    """Register subtypes of this TypedObject."""
    #    super().__init_subclass__(**kwargs)
    #    cls._register_adaptive_type("type", type)

    def __call__(self, field: Optional[str] = None) -> Any:
        """Return the nested data object contained by this `TypedObject`.

        If a field is provided, the contents of that field in the nested data will be
        returned.  Otherwise, the full contents of the NestedData will be returned.
        """

        type = getattr(self, "type", None)

        if type is None:
            raise AttributeError("type not specified")

        nested = getattr(self, type)

        if field is not None:
            nested = getattr(nested, field)

        return nested
