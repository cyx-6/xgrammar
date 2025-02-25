import json
import sys
import time
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Type, Union

import pytest
from pydantic import BaseModel, Field, TypeAdapter, WithJsonSchema, create_model
from transformers import AutoTokenizer

import xgrammar as xgr
from xgrammar.testing import _generate_range_regex, _is_grammar_accept_string, _json_schema_to_ebnf


def check_schema_with_grammar(
    schema: Dict[str, Any],
    expected_grammar_ebnf: str,
    any_whitespace: bool = True,
    indent: Optional[int] = None,
    separators: Optional[Tuple[str, str]] = None,
    strict_mode: bool = True,
):
    schema_str = json.dumps(schema)
    json_schema_ebnf = _json_schema_to_ebnf(
        schema_str,
        any_whitespace=any_whitespace,
        indent=indent,
        separators=separators,
        strict_mode=strict_mode,
    )
    assert json_schema_ebnf == expected_grammar_ebnf


def check_schema_with_instance(
    schema: Dict[str, Any],
    instance: Union[str, BaseModel, Any],
    is_accepted: bool = True,
    any_whitespace: bool = True,
    indent: Optional[int] = None,
    separators: Optional[Tuple[str, str]] = None,
    strict_mode: bool = True,
):
    json_schema_grammar = xgr.Grammar.from_json_schema(
        json.dumps(schema),
        any_whitespace=any_whitespace,
        indent=indent,
        separators=separators,
        strict_mode=strict_mode,
    )

    # instance: pydantic model, json string, or any other object (dumped to json string)
    if isinstance(instance, BaseModel):
        instance = json.dumps(
            instance.model_dump(mode="json", round_trip=True), indent=indent, separators=separators
        )
    elif not isinstance(instance, str):
        instance = json.dumps(instance, indent=indent, separators=separators)

    if is_accepted:
        assert _is_grammar_accept_string(json_schema_grammar, instance)
    else:
        assert not _is_grammar_accept_string(json_schema_grammar, instance)


def test_basic():
    class MainModel(BaseModel):
        integer_field: int
        number_field: float
        boolean_field: bool
        any_array_field: List
        array_field: List[str]
        tuple_field: Tuple[str, int, List[str]]
        object_field: Dict[str, int]
        nested_object_field: Dict[str, Dict[str, int]]

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
root_prop_3 ::= "[" "" basic_any (", " basic_any)* "" "]"
root_prop_4 ::= "[" "" basic_string (", " basic_string)* "" "]"
root_prop_5_item_2 ::= "[" "" basic_string (", " basic_string)* "" "]"
root_prop_5 ::= "[" "" basic_string ", " basic_integer ", " root_prop_5_item_2 "" "]"
root_prop_6 ::= "{" "" basic_string ": " basic_integer (", " basic_string ": " basic_integer)* "" "}"
root_prop_7_addl ::= "{" "" basic_string ": " basic_integer (", " basic_string ": " basic_integer)* "" "}"
root_prop_7 ::= "{" "" basic_string ": " root_prop_7_addl (", " basic_string ": " root_prop_7_addl)* "" "}"
root ::= "{" "" "\"integer_field\"" ": " basic_integer ", " "\"number_field\"" ": " basic_number ", " "\"boolean_field\"" ": " basic_boolean ", " "\"any_array_field\"" ": " root_prop_3 ", " "\"array_field\"" ": " root_prop_4 ", " "\"tuple_field\"" ": " root_prop_5 ", " "\"object_field\"" ": " root_prop_6 ", " "\"nested_object_field\"" ": " root_prop_7 "" "}"
"""

    schema = MainModel.model_json_schema()
    check_schema_with_grammar(schema, ebnf_grammar, any_whitespace=False)

    instance = MainModel(
        integer_field=42,
        number_field=3.14e5,
        boolean_field=True,
        any_array_field=[3.14, "foo", None, True],
        array_field=["foo", "bar"],
        tuple_field=("foo", 42, ["bar", "baz"]),
        object_field={"foo": 42, "bar": 43},
        nested_object_field={"foo": {"bar": 42}},
    )
    check_schema_with_instance(schema, instance, any_whitespace=False)

    instance_empty = MainModel(
        integer_field=42,
        number_field=3.14e5,
        boolean_field=True,
        any_array_field=[],
        array_field=[],
        tuple_field=("foo", 42, []),
        object_field={},
        nested_object_field={},
    )

    schema = MainModel.model_json_schema()
    check_schema_with_instance(schema, instance_empty, is_accepted=False, any_whitespace=False)


def test_indent():
    class MainModel(BaseModel):
        array_field: List[str]
        tuple_field: Tuple[str, int, List[str]]
        object_field: Dict[str, int]

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
root_prop_0 ::= "[" "\n    " basic_string (",\n    " basic_string)* "\n  " "]"
root_prop_1_item_2 ::= "[" "\n      " basic_string (",\n      " basic_string)* "\n    " "]"
root_prop_1 ::= "[" "\n    " basic_string ",\n    " basic_integer ",\n    " root_prop_1_item_2 "\n  " "]"
root_prop_2 ::= "{" "\n    " basic_string ": " basic_integer (",\n    " basic_string ": " basic_integer)* "\n  " "}"
root ::= "{" "\n  " "\"array_field\"" ": " root_prop_0 ",\n  " "\"tuple_field\"" ": " root_prop_1 ",\n  " "\"object_field\"" ": " root_prop_2 "\n" "}"
"""

    instance = MainModel(
        array_field=["foo", "bar"],
        tuple_field=("foo", 42, ["bar", "baz"]),
        object_field={"foo": 42, "bar": 43},
    )

    schema = MainModel.model_json_schema()
    check_schema_with_grammar(schema, ebnf_grammar, any_whitespace=False, indent=2)
    check_schema_with_instance(schema, instance, any_whitespace=False, indent=2)
    check_schema_with_instance(
        schema, instance, any_whitespace=False, indent=None, separators=(",", ":")
    )


def test_non_strict():
    class Foo(BaseModel):
        pass

    class MainModel(BaseModel):
        tuple_field: Tuple[str, Tuple[int, int]]
        foo_field: Foo
        list_field: List[str]
        object_field: Dict[str, Any]

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= ("[" "" basic_any (", " basic_any)* "" "]") | "[" "]"
basic_object ::= ("{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}") | "{" "}"
root_prop_0_item_1 ::= "[" "\n      " basic_integer ",\n      " basic_integer (",\n      " basic_any)* "\n    " "]"
root_prop_0 ::= "[" "\n    " basic_string ",\n    " root_prop_0_item_1 (",\n    " basic_any)* "\n  " "]"
defs_Foo ::= ("{" "\n    " basic_string ": " basic_any (",\n    " basic_string ": " basic_any)* "\n  " "}") | "{" "}"
root_prop_1 ::= defs_Foo
root_prop_2 ::= ("[" "\n    " basic_string (",\n    " basic_string)* "\n  " "]") | "[" "]"
root ::= "{" "\n  " "\"tuple_field\"" ": " root_prop_0 ",\n  " "\"foo_field\"" ": " root_prop_1 ",\n  " "\"list_field\"" ": " root_prop_2 ",\n  " "\"object_field\"" ": " basic_object (",\n  " basic_string ": " basic_any)* "\n" "}"
"""

    instance_json = r"""{
  "tuple_field": [
    "foo",
    [
      12,
      13,
      "ext"
    ],
    "extra"
  ],
  "foo_field": {
    "tmp": "str"
  },
  "list_field": [],
  "object_field": {},
  "extra": "field"
}"""

    schema = MainModel.model_json_schema()
    check_schema_with_grammar(
        schema, ebnf_grammar, any_whitespace=False, indent=2, strict_mode=False
    )
    check_schema_with_instance(
        schema, instance_json, any_whitespace=False, indent=2, strict_mode=False
    )


def test_enum_const():
    class Field(Enum):
        FOO = "foo"
        BAR = "bar"

    class MainModel(BaseModel):
        bars: Literal["a"]
        str_values: Literal['a\n\r"']
        foo: Literal["a", "b", "c"]
        values: Literal[1, "a", True]
        field: Field

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
root_prop_0 ::= "\"a\""
root_prop_1 ::= "\"a\\n\\r\\\"\""
root_prop_2 ::= ("\"a\"") | ("\"b\"") | ("\"c\"")
root_prop_3 ::= ("1") | ("\"a\"") | ("true")
defs_Field ::= ("\"foo\"") | ("\"bar\"")
root_prop_4 ::= defs_Field
root ::= "{" "" "\"bars\"" ": " root_prop_0 ", " "\"str_values\"" ": " root_prop_1 ", " "\"foo\"" ": " root_prop_2 ", " "\"values\"" ": " root_prop_3 ", " "\"field\"" ": " root_prop_4 "" "}"
"""

    schema = MainModel.model_json_schema()
    instance = MainModel(foo="a", values=1, bars="a", str_values='a\n\r"', field=Field.FOO)
    check_schema_with_grammar(schema, ebnf_grammar, any_whitespace=False)
    check_schema_with_instance(schema, instance, any_whitespace=False)


def test_optional():
    class MainModel(BaseModel):
        num: int = 0
        opt_bool: Optional[bool] = None
        size: Optional[float]
        name: str = ""

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
root_prop_1 ::= basic_boolean | basic_null
root_prop_2 ::= basic_number | basic_null
root ::= "{" "" ("\"num\"" ": " basic_integer ", ")? ("\"opt_bool\"" ": " root_prop_1 ", ")? "\"size\"" ": " root_prop_2 (", " "\"name\"" ": " basic_string)? "" "}"
"""

    schema = MainModel.model_json_schema()
    check_schema_with_grammar(schema, ebnf_grammar, any_whitespace=False)

    instance = MainModel(num=42, opt_bool=True, size=3.14, name="foo")
    check_schema_with_instance(schema, instance, any_whitespace=False)

    instance = MainModel(size=None)
    check_schema_with_instance(schema, instance, any_whitespace=False)

    check_schema_with_instance(schema, '{"size": null}', any_whitespace=False)
    check_schema_with_instance(schema, '{"size": null, "name": "foo"}', any_whitespace=False)
    check_schema_with_instance(
        schema, '{"num": 1, "size": null, "name": "foo"}', any_whitespace=False
    )


def test_all_optional():
    class MainModel(BaseModel):
        size: int = 0
        state: bool = False
        num: float = 0

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
root_part_1 ::= "" | ", " "\"num\"" ": " basic_number ""
root_part_0 ::= root_part_1 | ", " "\"state\"" ": " basic_boolean root_part_1
root ::= "{" "" (("\"size\"" ": " basic_integer root_part_0) | ("\"state\"" ": " basic_boolean root_part_1) | ("\"num\"" ": " basic_number "")) "" "}"
"""

    schema = MainModel.model_json_schema()
    check_schema_with_grammar(schema, ebnf_grammar, any_whitespace=False)

    instance = MainModel(size=42, state=True, num=3.14)
    check_schema_with_instance(schema, instance, any_whitespace=False)

    check_schema_with_instance(schema, '{"state": false}', any_whitespace=False)
    check_schema_with_instance(schema, '{"size": 1, "num": 1.5}', any_whitespace=False)

    ebnf_grammar_non_strict = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= ("[" "" basic_any (", " basic_any)* "" "]") | "[" "]"
basic_object ::= ("{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}") | "{" "}"
root_part_2 ::= (", " basic_string ": " basic_any)*
root_part_1 ::= root_part_2 | ", " "\"num\"" ": " basic_number root_part_2
root_part_0 ::= root_part_1 | ", " "\"state\"" ": " basic_boolean root_part_1
root ::= ("{" "" (("\"size\"" ": " basic_integer root_part_0) | ("\"state\"" ": " basic_boolean root_part_1) | ("\"num\"" ": " basic_number root_part_2) | basic_string ": " basic_any root_part_2) "" "}") | "{" "}"
"""

    check_schema_with_grammar(
        schema, ebnf_grammar_non_strict, any_whitespace=False, strict_mode=False
    )

    check_schema_with_instance(
        schema, '{"size": 1, "num": 1.5, "other": false}', any_whitespace=False, strict_mode=False
    )
    check_schema_with_instance(schema, '{"other": false}', any_whitespace=False, strict_mode=False)


def test_empty():
    class MainModel(BaseModel):
        pass

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
root ::= "{" "}"
"""

    schema = MainModel.model_json_schema()
    check_schema_with_grammar(schema, ebnf_grammar, any_whitespace=False)

    instance = MainModel()
    check_schema_with_instance(schema, instance, any_whitespace=False)

    check_schema_with_instance(schema, '{"tmp": 123}', any_whitespace=False, strict_mode=False)


def test_reference():
    class Foo(BaseModel):
        count: int
        size: Optional[float] = None

    class Bar(BaseModel):
        apple: str = "x"
        banana: str = "y"

    class MainModel(BaseModel):
        foo: Foo
        bars: List[Bar]

    instance = MainModel(
        foo=Foo(count=42, size=3.14), bars=[Bar(apple="a", banana="b"), Bar(apple="c", banana="d")]
    )

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
defs_Foo_prop_1 ::= basic_number | basic_null
defs_Foo ::= "{" "" "\"count\"" ": " basic_integer (", " "\"size\"" ": " defs_Foo_prop_1)? "" "}"
root_prop_0 ::= defs_Foo
defs_Bar_part_0 ::= "" | ", " "\"banana\"" ": " basic_string ""
defs_Bar ::= "{" "" (("\"apple\"" ": " basic_string defs_Bar_part_0) | ("\"banana\"" ": " basic_string "")) "" "}"
root_prop_1_items ::= defs_Bar
root_prop_1 ::= "[" "" root_prop_1_items (", " root_prop_1_items)* "" "]"
root ::= "{" "" "\"foo\"" ": " root_prop_0 ", " "\"bars\"" ": " root_prop_1 "" "}"
"""

    schema = MainModel.model_json_schema()
    check_schema_with_grammar(schema, ebnf_grammar, any_whitespace=False)
    check_schema_with_instance(schema, instance, any_whitespace=False)


def test_reference_schema():
    # Test simple reference with $defs
    schema = {
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/nested"}},
        "required": ["value"],
        "$defs": {
            "nested": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name", "age"],
            }
        },
    }

    instance = {"value": {"name": "John", "age": 30}}
    instance_rejected = {"value": {"name": "John"}}

    check_schema_with_instance(schema, instance, any_whitespace=False)
    check_schema_with_instance(schema, instance_rejected, is_accepted=False, any_whitespace=False)

    # Test simple reference with definitions
    schema_def = {
        "type": "object",
        "properties": {"value": {"$ref": "#/definitions/nested"}},
        "required": ["value"],
        "definitions": {
            "nested": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name", "age"],
            }
        },
    }

    check_schema_with_instance(schema_def, instance, any_whitespace=False)
    check_schema_with_instance(
        schema_def, instance_rejected, is_accepted=False, any_whitespace=False
    )

    # Test multi-level reference path
    schema_multi = {
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/level1/level2/nested"}},
        "required": ["value"],
        "$defs": {
            "level1": {
                "level2": {
                    "nested": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                        "required": ["name", "age"],
                    }
                }
            }
        },
    }

    check_schema_with_instance(schema_multi, instance, any_whitespace=False)
    check_schema_with_instance(
        schema_multi, instance_rejected, is_accepted=False, any_whitespace=False
    )

    # Test nested reference
    schema_nested = {
        "type": "object",
        "properties": {"value": {"$ref": "#/definitions/node_a"}},
        "required": ["value"],
        "definitions": {
            "node_a": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "child": {"$ref": "#/definitions/node_b"},
                },
                "required": ["name"],
            },
            "node_b": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            },
        },
    }

    instance_nested = {"value": {"name": "first", "child": {"id": 1}}}
    instance_nested_rejected = {"value": {"name": "first", "child": {}}}

    check_schema_with_instance(schema_nested, instance_nested, any_whitespace=False)
    check_schema_with_instance(
        schema_nested, instance_nested_rejected, is_accepted=False, any_whitespace=False
    )

    # Test schema with self-recursion through $defs
    schema_self_recursive = {
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/node"}},
        "required": ["value"],
        "$defs": {
            "node": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "next": {"$ref": "#/$defs/node"}},
                "required": ["id"],
            }
        },
    }

    instance_self_recursive = {"value": {"id": 1, "next": {"id": 2, "next": {"id": 3}}}}
    instance_self_recursive_1 = {"value": {"id": 1}}
    instance_self_recursive_rejected = {"value": {"id": 1, "next": {"next": {"id": 3}}}}

    check_schema_with_instance(schema_self_recursive, instance_self_recursive, any_whitespace=False)
    check_schema_with_instance(
        schema_self_recursive, instance_self_recursive_1, any_whitespace=False
    )
    check_schema_with_instance(
        schema_self_recursive,
        instance_self_recursive_rejected,
        is_accepted=False,
        any_whitespace=False,
    )

    # Test schema with circular references between multiple schemas
    schema_circular = {
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/schema_a"}},
        "required": ["value"],
        "$defs": {
            "schema_a": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "next": {"$ref": "#/$defs/schema_b"}},
                "required": ["name", "next"],
            },
            "schema_b": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "child": {"$ref": "#/$defs/schema_a"}},
                "required": ["id"],
            },
        },
    }

    instance_circular = {
        "value": {
            "name": "first",
            "next": {"id": 1, "child": {"name": "second", "next": {"id": 2}}},
        }
    }
    instance_circular_complex = {
        # fmt: off
        "value": {"name": "root", "next": {
            "id": 1, "child": {"name": "level1", "next": {
                "id": 2, "child": {"name": "level2", "next": {
                    "id": 3, "child": {"name": "level3", "next": {
                        "id": 4, "child": {"name": "level4", "next": {"id": 5}}
                    }}
                }}
            }}
        }}
        # fmt: on
    }
    instance_circular_rejected = {
        "value": {"name": "first", "next": {"child": {"name": "second", "next": {"id": 2}}}}
    }

    check_schema_with_instance(schema_circular, instance_circular, any_whitespace=False)
    check_schema_with_instance(schema_circular, instance_circular_complex, any_whitespace=False)
    check_schema_with_instance(
        schema_circular, instance_circular_rejected, is_accepted=False, any_whitespace=False
    )

    # Test self-referential schema
    schema_recursive = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "children": {"type": "array", "items": {"$ref": "#"}},
        },
        "required": ["name"],
    }

    instance_recursive = {
        "name": "root",
        "children": [{"name": "child1", "children": [{"name": "grandchild1"}]}, {"name": "child2"}],
    }
    instance_recursive_rejected = {"children": [{"name": "child1"}]}

    check_schema_with_instance(schema_recursive, instance_recursive, any_whitespace=False)
    check_schema_with_instance(
        schema_recursive, instance_recursive_rejected, is_accepted=False, any_whitespace=False
    )


def test_union():
    class Cat(BaseModel):
        name: str
        color: str

    class Dog(BaseModel):
        name: str
        breed: str

    ta = TypeAdapter(Union[Cat, Dog])

    model_schema = ta.json_schema()

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
defs_Cat ::= "{" "" "\"name\"" ": " basic_string ", " "\"color\"" ": " basic_string "" "}"
root_case_0 ::= defs_Cat
defs_Dog ::= "{" "" "\"name\"" ": " basic_string ", " "\"breed\"" ": " basic_string "" "}"
root_case_1 ::= defs_Dog
root ::= root_case_0 | root_case_1
"""

    check_schema_with_grammar(model_schema, ebnf_grammar, any_whitespace=False)

    check_schema_with_instance(model_schema, Cat(name="kitty", color="black"), any_whitespace=False)
    check_schema_with_instance(
        model_schema, Dog(name="doggy", breed="bulldog"), any_whitespace=False
    )
    check_schema_with_instance(
        model_schema, '{"name": "kitty", "test": "black"}', False, any_whitespace=False
    )


def test_anyof_oneof():
    schema = {
        "type": "object",
        "properties": {"name": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
    }
    schema_accepted_1 = '{"name": "John"}'
    schema_accepted_2 = '{"name": 123}'
    schema_rejected = '{"name": {"a": 1}}'
    check_schema_with_instance(schema, schema_accepted_1, any_whitespace=False)
    check_schema_with_instance(schema, schema_accepted_2, any_whitespace=False)
    check_schema_with_instance(schema, schema_rejected, is_accepted=False, any_whitespace=False)

    schema = {
        "type": "object",
        "properties": {"name": {"oneOf": [{"type": "string"}, {"type": "integer"}]}},
    }

    schema_accepted_1 = '{"name": "John"}'
    schema_accepted_2 = '{"name": 123}'
    schema_rejected = '{"name": {"a": 1}}'
    check_schema_with_instance(schema, schema_accepted_1, any_whitespace=False)
    check_schema_with_instance(schema, schema_accepted_2, any_whitespace=False)
    check_schema_with_instance(schema, schema_rejected, is_accepted=False, any_whitespace=False)


def test_alias():
    class MainModel(BaseModel):
        test: str = Field(..., alias="name")

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
root ::= "{" "" "\"name\"" ": " basic_string "" "}"
"""

    check_schema_with_grammar(MainModel.model_json_schema(), ebnf_grammar, any_whitespace=False)

    instance = MainModel(name="kitty")
    instance_str = json.dumps(instance.model_dump(mode="json", round_trip=True, by_alias=False))
    check_schema_with_instance(
        MainModel.model_json_schema(by_alias=False), instance_str, any_whitespace=False
    )

    instance_str = json.dumps(instance.model_dump(mode="json", round_trip=True, by_alias=True))
    check_schema_with_instance(
        MainModel.model_json_schema(by_alias=True), instance_str, any_whitespace=False
    )

    # property name contains space
    class MainModelSpace(BaseModel):
        test: Literal["abc"] = Field(..., alias="name 1")

    ebnf_grammar_space = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" "" basic_any (", " basic_any)* "" "]"
basic_object ::= "{" "" basic_string ": " basic_any (", " basic_string ": " basic_any)* "" "}"
root_prop_0 ::= "\"abc\""
root ::= "{" "" "\"name 1\"" ": " root_prop_0 "" "}"
"""

    check_schema_with_grammar(
        MainModelSpace.model_json_schema(), ebnf_grammar_space, any_whitespace=False
    )

    instance_space = MainModelSpace(**{"name 1": "abc"})
    instance_space_str = json.dumps(
        instance_space.model_dump(mode="json", round_trip=True, by_alias=True)
    )
    check_schema_with_instance(
        MainModelSpace.model_json_schema(by_alias=True), instance_space_str, any_whitespace=False
    )


def test_restricted_string():
    class MainModel(BaseModel):
        restricted_string: str = Field(..., pattern=r"[a-f]")

    instance = MainModel(restricted_string="a")
    instance_str = json.dumps(instance.model_dump(mode="json"))
    check_schema_with_instance(MainModel.model_json_schema(), instance_str, any_whitespace=False)

    check_schema_with_instance(
        MainModel.model_json_schema(),
        '{"restricted_string": "j"}',
        is_accepted=False,
        any_whitespace=False,
    )


def test_complex_restrictions():
    class RestrictedModel(BaseModel):
        restricted_string: Annotated[str, WithJsonSchema({"type": "string", "pattern": r"[^\"]*"})]
        restricted_value: Annotated[int, Field(strict=True, ge=0, lt=44)]

    # working instance
    instance = RestrictedModel(restricted_string="abd", restricted_value=42)
    instance_str = json.dumps(instance.model_dump(mode="json"))
    check_schema_with_instance(
        RestrictedModel.model_json_schema(), instance_str, any_whitespace=False
    )

    instance_err = RestrictedModel(restricted_string='"', restricted_value=42)
    instance_str = json.dumps(instance_err.model_dump(mode="json"))
    check_schema_with_instance(
        RestrictedModel.model_json_schema(), instance_str, is_accepted=False, any_whitespace=False
    )

    check_schema_with_instance(
        RestrictedModel.model_json_schema(),
        '{"restricted_string": "j", "restricted_value": 45}',
        is_accepted=False,
        any_whitespace=False,
    )


def test_dynamic_model():
    class MainModel(BaseModel):
        restricted_string: Annotated[str, WithJsonSchema({"type": "string", "pattern": r"[a-f]"})]

    additional_fields = {
        "restricted_string_dynamic": (
            Annotated[str, WithJsonSchema({"type": "string", "pattern": r"[a-x]"})],
            ...,
        )
    }

    CompleteModel: Type[BaseModel] = create_model(
        "CompleteModel", __base__=MainModel, **additional_fields
    )
    instance = CompleteModel(restricted_string="a", restricted_string_dynamic="j")
    instance_str = json.dumps(instance.model_dump(mode="json"))
    check_schema_with_instance(
        CompleteModel.model_json_schema(), instance_str, any_whitespace=False
    )


def test_any_whitespace():
    class SimpleModel(BaseModel):
        value: str
        arr: List[int]
        obj: Dict[str, int]

    schema = SimpleModel.model_json_schema()

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= "[" [ \n\t]* basic_any ([ \n\t]* "," [ \n\t]* basic_any)* [ \n\t]* "]"
basic_object ::= "{" [ \n\t]* basic_string [ \n\t]* ":" [ \n\t]* basic_any ([ \n\t]* "," [ \n\t]* basic_string [ \n\t]* ":" [ \n\t]* basic_any)* [ \n\t]* "}"
root_prop_1 ::= "[" [ \n\t]* basic_integer ([ \n\t]* "," [ \n\t]* basic_integer)* [ \n\t]* "]"
root_prop_2 ::= "{" [ \n\t]* basic_string [ \n\t]* ":" [ \n\t]* basic_integer ([ \n\t]* "," [ \n\t]* basic_string [ \n\t]* ":" [ \n\t]* basic_integer)* [ \n\t]* "}"
root ::= "{" [ \n\t]* "\"value\"" [ \n\t]* ":" [ \n\t]* basic_string [ \n\t]* "," [ \n\t]* "\"arr\"" [ \n\t]* ":" [ \n\t]* root_prop_1 [ \n\t]* "," [ \n\t]* "\"obj\"" [ \n\t]* ":" [ \n\t]* root_prop_2 [ \n\t]* "}"
"""

    check_schema_with_grammar(schema, ebnf_grammar, any_whitespace=True, strict_mode=True)

    ebnf_grammar = r"""basic_escape ::= ["\\/bfnrt] | "u" [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9] [A-Fa-f0-9]
basic_string_sub ::= ("\"" | [^"\\\r\n] basic_string_sub | "\\" basic_escape basic_string_sub) (= [ \n\t]* [,}\]:])
basic_any ::= basic_number | basic_string | basic_boolean | basic_null | basic_array | basic_object
basic_integer ::= ("0" | "-"? [1-9] [0-9]*)
basic_number ::= ("0" | "-"? [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
basic_string ::= ["] basic_string_sub
basic_boolean ::= "true" | "false"
basic_null ::= "null"
basic_array ::= ("[" [ \n\t]* basic_any ([ \n\t]* "," [ \n\t]* basic_any)* [ \n\t]* "]") | "[" [ \n\t]* "]"
basic_object ::= ("{" [ \n\t]* basic_string [ \n\t]* ":" [ \n\t]* basic_any ([ \n\t]* "," [ \n\t]* basic_string [ \n\t]* ":" [ \n\t]* basic_any)* [ \n\t]* "}") | "{" [ \n\t]* "}"
root_prop_1 ::= ("[" [ \n\t]* basic_integer ([ \n\t]* "," [ \n\t]* basic_integer)* [ \n\t]* "]") | "[" [ \n\t]* "]"
root_prop_2 ::= ("{" [ \n\t]* basic_string [ \n\t]* ":" [ \n\t]* basic_integer ([ \n\t]* "," [ \n\t]* basic_string [ \n\t]* ":" [ \n\t]* basic_integer)* [ \n\t]* "}") | "{" [ \n\t]* "}"
root ::= "{" [ \n\t]* "\"value\"" [ \n\t]* ":" [ \n\t]* basic_string [ \n\t]* "," [ \n\t]* "\"arr\"" [ \n\t]* ":" [ \n\t]* root_prop_1 [ \n\t]* "," [ \n\t]* "\"obj\"" [ \n\t]* ":" [ \n\t]* root_prop_2 ([ \n\t]* "," [ \n\t]* basic_string [ \n\t]* ":" [ \n\t]* basic_any)* [ \n\t]* "}"
"""

    check_schema_with_grammar(schema, ebnf_grammar, any_whitespace=True, strict_mode=False)

    # Test that different whitespace variations are accepted when any_whitespace=True
    instances = [
        '{"value": "test", "arr": [1, 2], "obj": {"a": 1}}',
        '{ "value" : "test", "arr": [1, 2], "obj": {"a": 1} }',
        '{\n  "value"  :  "test",\n  "arr"  :  [1, 2],\n  "obj"  :  {"a": 1}\n}',
        '{\t"value"\t:\t"test",\t"arr":\t[1,\t2],\t"obj":\t{"a":\t1}\t}',
    ]
    for instance in instances:
        check_schema_with_instance(schema, instance, any_whitespace=True)


def test_array_with_only_items_keyword():
    schema = {
        "items": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        }
    }
    instance_accepted = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]
    instance_rejected = [{"name": "John"}]
    check_schema_with_instance(schema, instance_accepted, any_whitespace=False)
    check_schema_with_instance(schema, instance_rejected, is_accepted=False, any_whitespace=False)

    schema_prefix_items = {
        "prefixItems": [
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name", "age"],
            },
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name", "age"],
            },
        ]
    }

    check_schema_with_instance(schema_prefix_items, instance_accepted, any_whitespace=False)
    check_schema_with_instance(
        schema_prefix_items, instance_rejected, is_accepted=False, any_whitespace=False
    )

    schema_unevaluated_items = {
        "unevaluatedItems": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        }
    }

    check_schema_with_instance(schema_unevaluated_items, instance_accepted, any_whitespace=False)
    check_schema_with_instance(
        schema_unevaluated_items, instance_rejected, is_accepted=False, any_whitespace=False
    )


def test_object_with_only_properties_keyword():
    schema = {
        "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        "required": ["name", "age"],
    }
    instance_accepted = {"name": "John", "age": 30}
    instance_rejected = {"name": "John"}
    check_schema_with_instance(schema, instance_accepted, any_whitespace=False)
    check_schema_with_instance(schema, instance_rejected, is_accepted=False, any_whitespace=False)

    schema_additional_properties = {"additionalProperties": {"type": "string"}}
    instance_accepted = {"name": "John"}
    instance_rejected = {"name": "John", "age": 30}

    check_schema_with_instance(
        schema_additional_properties, instance_accepted, any_whitespace=False
    )
    check_schema_with_instance(
        schema_additional_properties, instance_rejected, is_accepted=False, any_whitespace=False
    )

    schema_unevaluated_properties = {"unevaluatedProperties": {"type": "string"}}

    check_schema_with_instance(
        schema_unevaluated_properties, instance_accepted, any_whitespace=False
    )
    check_schema_with_instance(
        schema_unevaluated_properties, instance_rejected, is_accepted=False, any_whitespace=False
    )


def test_generate_range_regex():
    # Basic range tests
    assert _generate_range_regex(12, 16) == r"^((1[2-6]))$"
    assert _generate_range_regex(1, 10) == r"^(([1-9]|10))$"
    assert (
        _generate_range_regex(2134, 3459)
        == r"^((2[2-9]\d{2}|2[2-9]\d{2}|21[4-9]\d{1}|213[5-9]|2134|3[0-3]\d{2}|3[0-3]\d{2}|34[0-4]\d{1}|345[0-8]|3459))$"
    )

    # Negative to positive range
    assert _generate_range_regex(-5, 10) == r"^(-([1-5])|0|([1-9]|10))$"

    # Pure negative range
    assert _generate_range_regex(-15, -10) == r"^(-(1[0-5]))$"

    # Large ranges
    assert (
        _generate_range_regex(-1999, -100)
        == r"^(-([1-9]\d{2}|1[0-8]\d{2}|19[0-8]\d{1}|199[0-8]|1999))$"
    )
    assert _generate_range_regex(1, 9999) == r"^(([1-9]|[1-9]\d{1}|[1-9]\d{2}|[1-9]\d{3}))$"

    # Unbounded ranges (None cases)
    assert _generate_range_regex(None, None) == r"^-?\d+$"
    assert _generate_range_regex(5, None) == r"^([5-9]|[1-9]\d*)$"
    assert _generate_range_regex(None, 0) == r"^(-[1-9]\d*|0)$"

    # Medium range
    assert (
        _generate_range_regex(78, 1278)
        == r"^(([8-9]\d{1}|79|78|[1-9]\d{2}|1[0-1]\d{2}|12[0-6]\d{1}|127[0-7]|1278))$"
    )

    # Symmetric range around zero
    assert (
        _generate_range_regex(-100, 100) == r"^(-([1-9]|[1-9]\d{1}|100)|0|([1-9]|[1-9]\d{1}|100))$"
    )

    # Upper bound negative
    assert _generate_range_regex(None, -123) == r"^(-123|-1[0-1]\d{1}|-12[0-2]|-[1-9]\d{3,})$"

    # Invalid range test (end < start)
    assert _generate_range_regex(10, 5) == r"^()$"
    assert _generate_range_regex(0, -1) == r"^()$"
    assert _generate_range_regex(100, -100) == r"^()$"

    # Additional edge cases
    # Single number
    assert _generate_range_regex(5, 5) == r"^((5))$"

    # Zero-inclusive ranges
    assert _generate_range_regex(-10, 0) == r"^(-([1-9]|10)|0)$"
    assert _generate_range_regex(0, 10) == r"^(0|([1-9]|10))$"


email_instances_accepted = [
    (r"simple@example.com", True),
    (r"very.common@example.com", True),
    (r"FirstName.LastName@EasierReading.org", True),
    (r"x@example.com", True),
    (r"long.email-address-with-hyphens@and.subdomains.example.com", True),
    (r"user.name+tag+sorting@example.com", True),
    (r"name/surname@example.com", True),
    (r"admin@example", True),
    (r"example@s.example", True),
    (r'" "@example.org', True),
    (r'"john..doe"@example.org', True),
    (r"mailhost!username@example.org", True),
    (r'"very.(),:;<>[]\".VERY.\"very@\\ \"very\".unusual"@strange.example.com', True),
    (r"user%example.com@example.org", True),
    (r"user-@example.org", True),
    (r"abc.example.com", False),
    (r"a@b@c@example.com", False),
    (r'a"b(c)d,e:f;g<h>i[j\k]l@example.com', False),
    (r'just"not"right@example.com', False),
    (r'this is"not\allowed@example.com', False),
    (r"this\ still\"not\\allowed@example.com", False),
    (r"i.like.underscores@but_they_are_not_allowed_in_this_part", False),
]


@pytest.mark.parametrize("instance, accepted", email_instances_accepted)
def test_email_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "email"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


date_instances_accepted = [
    (r"0000-01-01", True),
    (r"9999-12-31", True),
    (r"10-01-01", False),
    (r"2025-00-01", False),
    (r"2025-13-01", False),
    (r"2025-01-00", False),
    (r"2025-01-32", False),
]


@pytest.mark.parametrize("instance, accepted", date_instances_accepted)
def test_date_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "date"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


time_instances_accepted = [
    (r"00:00:00Z", True),
    (r"23:59:60Z", True),
    (r"12:34:56Z", True),
    (r"12:34:56+07:08", True),
    (r"12:34:56-07:08", True),
    (r"12:34:56.7Z", True),
    (r"12:34:56.7+08:09", True),
    (r"12:34:56.7-08:09", True),
    (r"00:00:00", False),
    (r"23:59:60", False),
    (r"12:34:56.7", False),
    (r"12:34:56.7890", False),
    (r"24:00:00", False),
    (r"00:60:00", False),
    (r"00:00:61", False),
    (r"00:00:00.", False),
    (r"12:34:56+07:", False),
    (r"12:34:56-07:", False),
    (r"12:34:56.7+-08:09", False),
]


@pytest.mark.parametrize("instance, accepted", time_instances_accepted)
def test_time_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "time"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


duration_instances_accepted = [
    (r"P0Y", True),
    (r"P12M", True),
    (r"P345D", True),
    (r"P6789W", True),
    (r"P01234D", True),
    (r"PT9H", True),
    (r"PT87M", True),
    (r"PT654S", True),
    (r"P1Y23M456D", True),
    (r"P23M456D", True),
    (r"P1Y0M456D", True),
    (r"P1Y23M", True),
    (r"PT9H87M654S", True),
    (r"PT87M654S", True),
    (r"PT9H0M654S", True),
    (r"PT9H87M", True),
    (r"P1Y23M456DT9H87M654S", True),
    (r"P", False),
    (r"PD", False),
    (r"P1", False),
    (r"PT", False),
    (r"P1Y456D", False),
    (r"PT9H654S", False),
]


@pytest.mark.parametrize("instance, accepted", duration_instances_accepted)
def test_duration_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "duration"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


ipv6_instances_accepted = [
    (r"0123:4567:890a:bced:fABC:DEF0:1234:5678", True),
    (r"::6666:6666:6666:6666:6666:6666", True),
    (r"::6666:6666:6666:6666:6666", True),
    (r"::6666:6666:6666:6666", True),
    (r"::6666:6666:6666", True),
    (r"::6666:6666", True),
    (r"::6666", True),
    (r"::", True),
    (r"8888:8888:8888:8888:8888:8888::", True),
    (r"8888:8888:8888:8888:8888::", True),
    (r"8888:8888:8888:8888::", True),
    (r"8888:8888:8888::", True),
    (r"8888:8888::", True),
    (r"8888::", True),
    (r"1111::2222", True),
    (r"1111:1111::2222", True),
    (r"1111::2222:2222", True),
    (r"1111:1111:1111::2222", True),
    (r"1111:1111::2222:2222", True),
    (r"1111::2222:2222:2222", True),
    (r"1111:1111:1111:1111::2222", True),
    (r"1111:1111:1111::2222:2222", True),
    (r"1111:1111::2222:2222:2222", True),
    (r"1111::2222:2222:2222:2222", True),
    (r"1111:1111:1111:1111:1111::2222", True),
    (r"1111:1111:1111:1111::2222:2222", True),
    (r"1111:1111:1111::2222:2222:2222", True),
    (r"1111:1111::2222:2222:2222:2222", True),
    (r"1111::2222:2222:2222:2222:2222", True),
    (r"1111:1111:1111:1111:1111:1111::2222", True),
    (r"1111:1111:1111:1111:1111::2222:2222", True),
    (r"1111:1111:1111:1111::2222:2222:2222", True),
    (r"1111:1111:1111::2222:2222:2222:2222", True),
    (r"1111:1111::2222:2222:2222:2222:2222", True),
    (r"1111::2222:2222:2222:2222:2222:2222", True),
    (r"0123:4567:890a:bced:fABC:DEF0:012.034.056.078", True),
    (r"::111.111.222.222", True),
    (r":", False),
    (r":::", False),
    (r"::5555:5555:5555:5555:5555:5555:5555:5555", False),
    (r"5555::5555:5555:5555:5555:5555:5555:5555", False),
    (r"5555:5555::5555:5555:5555:5555:5555:5555", False),
    (r"5555:5555:5555::5555:5555:5555:5555:5555", False),
    (r"5555:5555:5555:5555::5555:5555:5555:5555", False),
    (r"5555:5555:5555:5555:5555::5555:5555:5555", False),
    (r"5555:5555:5555:5555:5555:5555::5555:5555", False),
    (r"5555:5555:5555:5555:5555:5555:5555::5555", False),
    (r"5555:5555:5555:5555:5555:5555:5555:5555::", False),
]


@pytest.mark.parametrize("instance, accepted", ipv6_instances_accepted)
def test_ipv6_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "ipv6"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


ipv4_instances_accepted = [
    # (r"0.0.0.0", True),
    (r"00.00.00.00", True),
    (r"000.000.000.000", True),
    (r"255.255.255.255", True),
    (r"1", False),
    (r"1.", False),
    (r"1.1", False),
    (r"1.1.", False),
    (r"1.1.1", False),
    (r"1.1.1.", False),
    (r"0001.0001.0001.0001", False),
    (r"256.256.256.256", False),
]


@pytest.mark.parametrize("instance, accepted", ipv4_instances_accepted)
def test_ipv4_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "ipv4"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


hostname_instances_accepted = [
    (r"0", True),
    (r"9", True),
    (r"a", True),
    (r"z", True),
    (r"www.github.com", True),
    (r"w-w-w.g-i-t-h-u-b.c-o-m", True),
    (r"ww-w.gi-th-ub.co-m", True),
    (r"w--ww.git---hub.co----m", True),
    (r".", False),
    (r"-", False),
    (r"-.", False),
    (r".-", False),
    (r"_", False),
    (r"a.", False),
    (r"-b", False),
    (r"c-", False),
    (r"d.-", False),
    (r"e-.", False),
    (r"-f.", False),
    (r"g-.h", False),
    (r"-i.j", False),
]


@pytest.mark.parametrize("instance, accepted", hostname_instances_accepted)
def test_hostname_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "hostname"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


uuid_instances_accepted = [
    (r"00000000-0000-0000-0000-000000000000", True),
    (r"FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF", True),
    (r"01234567-89AB-CDEF-abcd-ef0123456789", True),
    (r"-", False),
    (r"----", False),
    (r"AAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA", False),
    (r"BBBBBBBB-BBB-BBBB-BBBB-BBBBBBBBBBBB", False),
    (r"CCCCCCCC-CCCC-CCC-CCCC-CCCCCCCCCCCC", False),
    (r"DDDDDDDD-DDDD-DDDD-DDD-DDDDDDDDDDDD", False),
    (r"EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEE", False),
    (r"AAAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA", False),
    (r"BBBBBBBB-BBBBB-BBBB-BBBB-BBBBBBBBBBBB", False),
    (r"CCCCCCCC-CCCC-CCCCC-CCCC-CCCCCCCCCCCC", False),
    (r"DDDDDDDD-DDDD-DDDD-DDDDD-DDDDDDDDDDDD", False),
    (r"EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEEEE", False),
]


@pytest.mark.parametrize("instance, accepted", uuid_instances_accepted)
def test_uuid_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "uuid"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


uri_instances_accepted = [
    (r"aaa:?azAZ09-._~%Ff!$&'()*+,;=:@#azAZ09-._~%Aa!$&'()*+,;=:@", True),
    (r"z+.-:", True),
    (r"abc:", True),
    (r"abc:a", True),
    (r"abc:/", True),
    (r"abc:/a", True),
    (r"abc://", True),
    (r"abc://///////", True),
    (r"abc://azAZ09-._~%Ff!$&'()*+,;=:@", True),
    (r"abc://:", True),
    (r"abc://:0123", True),
    (r"abc://azAZ09-._~%Ff!$&'()*+,;=", True),
    (r"xyz:/a", True),
    (r"xyz:/azAZ09-._~%Ff!$&'()*+,;=:@", True),
    (r"aaa:?[#]", False),
    (r"abc://@@", False),
    (r"abc://::", False),
    (r"abc:/[]", False),
]


@pytest.mark.parametrize("instance, accepted", uri_instances_accepted)
def test_uri_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "uri"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


uri_reference_instances_accepted = [
    (r"?azAZ09-._~%Ff!$&'()*+,;=:@#azAZ09-._~%Aa!$&'()*+,;=:@", True),
    (r"", True),
    (r"a", True),
    (r"/", True),
    (r"/a", True),
    (r"//", True),
    (r"/////////", True),
    (r"//azAZ09-._~%Ff!$&'()*+,;=:@", True),
    (r"//:", True),
    (r"//:0123", True),
    (r"//azAZ09-._~%Ff!$&'()*+,;=", True),
    (r"/a", True),
    (r"/azAZ09-._~%Ff!$&'()*+,;=:@", True),
    (r"?[#]", False),
    (r"//@@", False),
    (r"//::", False),
    (r"/[]", False),
    (r":", False),
]


@pytest.mark.parametrize("instance, accepted", uri_reference_instances_accepted)
def test_uri_reference_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "uri-reference"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


uri_template_instances_accepted = [
    (r"", True),
    (r"!#$&()*+,-./09:;=?@AZ[]_az~%Ff", True),
    (r"{+a}{#a}{.a}{/a}{;a}{?a}{&a}{=a}{,a}{!a}{@a}{|a}", True),
    (r"{%Ff}", True),
    (r"{i.j.k}", True),
    (r"{a_b_c:1234}", True),
    (r"{x_y_z*}", True),
    (r'"', False),
    (r"'", False),
    (r"%", False),
    (r"<", False),
    (r">", False),
    (r"\\", False),
    (r"^", False),
    (r"`", False),
    (r"{", False),
    (r"|", False),
    (r"}", False),
    (r"{n.}", False),
    (r"{m:100001}", False),
    (r"%1", False),
    (r"%Gg", False),
]


@pytest.mark.parametrize("instance, accepted", uri_template_instances_accepted)
def test_uri_template_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "uri-template"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


json_pointer_instances_accepted = [
    (r"/", True),
    (r"//", True),
    (r"/a/bc/def/ghij", True),
    (r"/~0/~1/", True),
    (r"abc", False),
    (r"/~", False),
    (r"/~2", False),
]


@pytest.mark.parametrize("instance, accepted", json_pointer_instances_accepted)
def test_json_pointer_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "json-pointer"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


relative_json_pointer_instances_accepted = [
    (r"0/", True),
    (r"123/a/bc/def/ghij", True),
    (r"45/~0/~1/", True),
    (r"6789#", True),
    (r"#", False),
    (r"abc", False),
    (r"/", False),
    (r"9/~2", False),
]


@pytest.mark.parametrize("instance, accepted", relative_json_pointer_instances_accepted)
def test_relative_json_pointer_format(instance: str, accepted: bool):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": "relative-json-pointer"})

    schema = MainModel.model_json_schema()
    check_schema_with_instance(
        schema, MainModel(name=instance), is_accepted=accepted, any_whitespace=False
    )


string_format_instances = [
    (r"long.email-address-with-hyphens@and.subdomains.example.com", "email"),
    (r'"very.(),:;<>[]\".VERY.\"very@\\ \"very\".unusual"@strange.example.com', "email"),
    (r"128.255.000.222", "ipv4"),
    (r"abcd:ABCD::0123:5678:000.111.222.123", "ipv6"),
    (r"P1Y23M456DT9H87M654S", "duration"),
    (r"2025-01-01T12:34:56.7+08:09", "date-time"),
    (r"123--abc.efgh---789-xyz.rst-uvw", "hostname"),
    (r"01234567-89AB-CDEF-abcd-ef0123456789", "uuid"),
    (
        r"http://azAZ09-._~%Ff!$&'()*+,;=:@xyz:987/-/./+/*?aA0-._~%Ff!$&'()@#zZ9-._~%Aa!$&,;=:",
        "uri",
    ),
    (
        r"//azAZ09-._~%Ff!$&'()*+,;=:@xyz:987/-/./+/*?aA0-._~%Ff!$&'()@#zZ9-._~%Aa!$&,;=:",
        "uri-reference",
    ),
    (r"!#$&()*+,-./{+abc}{#def}{.ghi}{/jkl}{;mno:2468}", "uri-template"),
    (r"/a/bc/def/ghij/~0~1//", "json-pointer"),
    (r"1234/a/bc/def/ghij/~0~1//", "relative-json-pointer"),
]


@pytest.mark.parametrize("value, format", string_format_instances)
def test_mask_generation_format(value: str, format: str):
    class MainModel(BaseModel):
        name: str = Field(json_schema_extra={"format": format})

    instance = json.dumps(MainModel(name=value).model_dump(mode="json"))

    tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3.1-8B-Instruct")
    tokenizer_info = xgr.TokenizerInfo.from_huggingface(tokenizer)
    grammar_compiler = xgr.GrammarCompiler(tokenizer_info, cache_enabled=False)

    time_start = time.monotonic_ns()
    ebnf = _json_schema_to_ebnf(
        json.dumps(MainModel.model_json_schema()),
        any_whitespace=None,
        indent=None,
        separators=None,
        strict_mode=True,
    )
    matcher_compiled_grammar = grammar_compiler.compile_grammar(ebnf)
    time_end = time.monotonic_ns()
    print(f"Time for preprocessing: {(time_end - time_start) / 1e3} us")
    matcher = xgr.GrammarMatcher(matcher_compiled_grammar)
    token_bitmask = xgr.allocate_token_bitmask(1, tokenizer_info.vocab_size)

    for c in instance.encode("utf-8"):
        time_start = time.monotonic_ns()
        matcher.fill_next_token_bitmask(token_bitmask)
        time_end = time.monotonic_ns()
        delta = (time_end - time_start) / 1e3
        if delta > 1000:
            print(f"Time for fill_next_token_bitmask: {delta} us on char {bytes([c])}")
        accepted = matcher._debug_accept_string(bytes([c]))
        assert accepted

    time_start = time.monotonic_ns()
    matcher.fill_next_token_bitmask(token_bitmask)
    time_end = time.monotonic_ns()
    print(f"Time for fill_next_token_bitmask: {(time_end - time_start) / 1e3} us")

    assert matcher.accept_token(tokenizer.eos_token_id)
    assert matcher.is_terminated()


if __name__ == "__main__":
    pytest.main(sys.argv)
