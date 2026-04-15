# -*- coding: utf-8 -*-
import copy
import pytest
from flask import Flask
from unittest.mock import MagicMock

from flask_restx.model import instance, ModelBase, RawModel, Model, SchemaModel
from flask_restx import fields


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


def make_model(name="MyModel", field_dict=None):
    """Return a Model instance with optional fields."""
    if field_dict is None:
        field_dict = {"name": fields.String()}
    return Model(name, field_dict)


# ---------------------------------------------------------------------------
# instance()
# ---------------------------------------------------------------------------

def test_instance_with_type_returns_instance():
    result = instance(fields.String)
    assert isinstance(result, fields.String)


def test_instance_with_object_returns_same():
    obj = fields.String()
    result = instance(obj)
    assert result is obj


# ---------------------------------------------------------------------------
# ModelBase.__init__
# ---------------------------------------------------------------------------

def test_modelbase_init_sets_name():
    m = make_model("Foo")
    assert m.name == "Foo"


def test_modelbase_init_sets_apidoc():
    m = make_model("Bar")
    assert m.__apidoc__ == {"name": "Bar"}


def test_modelbase_init_parents_empty():
    m = make_model("Baz")
    assert m.__parents__ == []


def test_modelbase_init_inherit_callable():
    m = make_model("Test")
    assert callable(m.inherit)


# ---------------------------------------------------------------------------
# ModelBase.instance_inherit (via m.inherit)
# ---------------------------------------------------------------------------

def test_instance_inherit_creates_child_model():
    parent = make_model("Parent", {"id": fields.Integer()})
    child = parent.inherit("Child", {"extra": fields.String()})
    assert child.name == "Child"
    assert isinstance(child, Model)


# ---------------------------------------------------------------------------
# ModelBase.ancestors
# ---------------------------------------------------------------------------

def test_ancestors_no_parents():
    m = make_model("Solo")
    assert m.ancestors == {"Solo"}


def test_ancestors_with_parents():
    grandparent = make_model("Grand", {"a": fields.String()})
    parent = make_model("Parent", {"b": fields.String()})
    parent.__parents__ = [grandparent]
    child = make_model("Child", {"c": fields.String()})
    child.__parents__ = [parent]
    assert child.ancestors == {"Child", "Parent", "Grand"}


# ---------------------------------------------------------------------------
# ModelBase.get_parent
# ---------------------------------------------------------------------------

def test_get_parent_self():
    m = make_model("Self")
    assert m.get_parent("Self") is m


def test_get_parent_finds_in_parents():
    grandparent = make_model("Grand", {"a": fields.String()})
    parent = make_model("Parent", {"b": fields.String()})
    parent.__parents__ = [grandparent]
    child = make_model("Child", {"c": fields.String()})
    child.__parents__ = [parent]
    assert child.get_parent("Grand") is grandparent


def test_get_parent_raises_when_not_found():
    m = make_model("OnlyMe")
    with pytest.raises(ValueError, match="Parent Missing not found"):
        m.get_parent("Missing")


# ---------------------------------------------------------------------------
# ModelBase.__schema__
# ---------------------------------------------------------------------------

def test_schema_no_parents():
    m = make_model("Simple", {"name": fields.String()})
    schema = m.__schema__
    assert "properties" in schema
    assert "type" in schema


def test_schema_with_parents():
    parent = make_model("Parent", {"id": fields.Integer()})
    child = make_model("Child", {"extra": fields.String()})
    child.__parents__ = [parent]
    schema = child.__schema__
    assert "allOf" in schema
    refs = schema["allOf"]
    assert any(r.get("$ref", "").endswith("Parent") for r in refs)


# ---------------------------------------------------------------------------
# ModelBase.inherit (classmethod)
# ---------------------------------------------------------------------------

def test_inherit_classmethod_creates_model():
    base = make_model("Base", {"id": fields.Integer()})
    child = Model.inherit("Child", base, {"extra": fields.String()})
    assert child.name == "Child"
    assert base in child.__parents__


# ---------------------------------------------------------------------------
# ModelBase.validate
# ---------------------------------------------------------------------------

def test_validate_valid_data_no_error(app):
    m = Model("Val", {"name": fields.String(required=True)})
    with app.app_context():
        m.validate({"name": "Alice"})  # should not raise


def test_validate_invalid_data_raises(app):
    from flask_restx.errors import abort as real_abort
    m = Model("Val", {"name": fields.String(required=True)})
    with app.app_context():
        with pytest.raises(Exception):
            m.validate({})  # missing required field


def test_validate_with_none_resolver(app):
    m = Model("Val2", {"age": fields.Integer()})
    with app.app_context():
        m.validate({"age": 5}, resolver=None)  # should not raise


# ---------------------------------------------------------------------------
# ModelBase.format_error
# ---------------------------------------------------------------------------

def test_format_error_required_field():
    m = make_model("FE")
    error = MagicMock()
    error.path = []
    error.validator = "required"
    error.message = "u'username' is a required property"
    key, msg = m.format_error(error)
    assert key == "username"
    assert msg == error.message


def test_format_error_non_required_field():
    m = make_model("FE2")
    error = MagicMock()
    error.path = ["address", "city"]
    error.validator = "type"
    error.message = "42 is not of type 'string'"
    key, msg = m.format_error(error)
    assert key == "address.city"
    assert msg == error.message


# ---------------------------------------------------------------------------
# ModelBase.__unicode__ / __str__
# ---------------------------------------------------------------------------

def test_unicode_returns_formatted_string():
    m = Model("MyModel", {"a": fields.String(), "b": fields.Integer()})
    result = str(m)
    assert result.startswith("Model(MyModel,{")


# ---------------------------------------------------------------------------
# RawModel.__init__
# ---------------------------------------------------------------------------

def test_rawmodel_init_mask_none():
    m = Model("NoMask", {"x": fields.String()})
    assert m.__mask__ is None


def test_rawmodel_init_strict_false():
    m = Model("NoStrict", {"x": fields.String()})
    assert m.__strict__ is False


def test_rawmodel_init_strict_true():
    m = Model("Strict", {"x": fields.String()}, strict=True)
    assert m.__strict__ is True


def test_rawmodel_init_mask_string():
    m = Model("WithMask", {"x": fields.String()}, mask="{x}")
    from flask_restx.mask import Mask
    assert isinstance(m.__mask__, Mask)


def test_rawmodel_init_clone_callable():
    m = Model("ClonableM", {"x": fields.String()})
    assert callable(m.clone)


# ---------------------------------------------------------------------------
# RawModel.instance_clone (via m.clone)
# ---------------------------------------------------------------------------

def test_instance_clone_creates_new_model():
    m = Model("Original", {"x": fields.String()})
    cloned = m.clone("Cloned")
    assert cloned.name == "Cloned"
    assert isinstance(cloned, Model)


# ---------------------------------------------------------------------------
# RawModel._schema
# ---------------------------------------------------------------------------

def test_raw_model_schema_has_properties():
    m = Model("Sch", {"name": fields.String()})
    schema = m._schema
    assert "properties" in schema
    assert "name" in schema["properties"]


def test_raw_model_schema_required_fields():
    m = Model("Req", {"name": fields.String(required=True)})
    schema = m._schema
    assert "required" in schema
    assert "name" in schema["required"]


def test_raw_model_schema_strict():
    m = Model("Strict", {"name": fields.String()}, strict=True)
    schema = m._schema
    assert schema.get("additionalProperties") is False


def test_raw_model_schema_with_mask():
    m = Model("Masked", {"name": fields.String()}, mask="{name}")
    schema = m._schema
    assert "x-mask" in schema


def test_raw_model_schema_discriminator():
    m = Model("Disc", {"kind": fields.String(discriminator=True)})
    schema = m._schema
    assert schema.get("discriminator") == "kind"


# ---------------------------------------------------------------------------
# RawModel.resolved
# ---------------------------------------------------------------------------

def test_resolved_no_parents():
    m = Model("Res", {"x": fields.String()})
    resolved = m.resolved
    assert "x" in resolved


def test_resolved_merges_parent_fields():
    parent = Model("Par", {"id": fields.Integer()})
    child = Model("Chi", {"name": fields.String()})
    child.__parents__ = [parent]
    resolved = child.resolved
    assert "id" in resolved
    assert "name" in resolved


def test_resolved_raises_on_multiple_discriminators():
    m = Model("Multi", {
        "kind1": fields.String(discriminator=True),
        "kind2": fields.String(discriminator=True),
    })
    with pytest.raises(ValueError, match="There can only be one discriminator"):
        _ = m.resolved


def test_resolved_single_discriminator_sets_default():
    m = Model("SingleDisc", {"kind": fields.String(discriminator=True)})
    resolved = m.resolved
    assert resolved["kind"].default == "SingleDisc"


# ---------------------------------------------------------------------------
# RawModel.extend
# ---------------------------------------------------------------------------

def test_extend_deprecation_warning():
    m = Model("Ext", {"x": fields.String()})
    with pytest.warns(DeprecationWarning):
        extended = m.extend("Extended", {"y": fields.Integer()})
    assert extended.name == "Extended"


def test_extend_with_list_fields():
    m = Model("ExtList", {"x": fields.String()})
    with pytest.warns(DeprecationWarning):
        extra = Model("Extra", {"y": fields.Integer()})
        extended = m.extend("Extended", [extra])
    assert extended.name == "Extended"


# ---------------------------------------------------------------------------
# RawModel.clone (classmethod)
# ---------------------------------------------------------------------------

def test_clone_classmethod():
    base = Model("Base", {"x": fields.String()})
    cloned = Model.clone("Cloned", base)
    assert cloned.name == "Cloned"
    assert "x" in cloned


def test_clone_merges_multiple_parents():
    a = Model("A", {"x": fields.String()})
    b = Model("B", {"y": fields.Integer()})
    cloned = Model.clone("AB", a, b)
    assert "x" in cloned
    assert "y" in cloned


# ---------------------------------------------------------------------------
# RawModel.__deepcopy__
# ---------------------------------------------------------------------------

def test_deepcopy_creates_independent_copy():
    m = Model("Original", {"x": fields.String()})
    m_copy = copy.deepcopy(m)
    assert m_copy.name == m.name
    assert m_copy is not m


def test_deepcopy_preserves_mask():
    m = Model("Masked", {"x": fields.String()}, mask="{x}")
    m_copy = copy.deepcopy(m)
    assert m_copy.__mask__ is not None


def test_deepcopy_preserves_strict():
    m = Model("Strict", {"x": fields.String()}, strict=True)
    m_copy = copy.deepcopy(m)
    assert m_copy.__strict__ is True


def test_deepcopy_preserves_parents():
    parent = Model("Parent", {"id": fields.Integer()})
    child = Model("Child", {"name": fields.String()})
    child.__parents__ = [parent]
    child_copy = copy.deepcopy(child)
    assert child_copy.__parents__ == [parent]


# ---------------------------------------------------------------------------
# SchemaModel.__init__
# ---------------------------------------------------------------------------

def test_schema_model_init_with_schema():
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    m = SchemaModel("SM", schema)
    assert m.name == "SM"
    assert m._schema == schema


def test_schema_model_init_default_schema():
    m = SchemaModel("SM2")
    assert m._schema == {}


# ---------------------------------------------------------------------------
# SchemaModel.__unicode__ / __str__
# ---------------------------------------------------------------------------

def test_schema_model_unicode():
    schema = {"type": "object"}
    m = SchemaModel("SM3", schema)
    result = str(m)
    assert "SchemaModel(SM3," in result
    assert "object" in result
