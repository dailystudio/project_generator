#
# Copyright (C) 2015 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import logging
import math
import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Tuple, Callable
from xml.dom import minidom
from xml.dom.minidom import Element, Node, NamedNodeMap

from com.android.ide.common.vectordrawable import Svg2Vector, SvgColor
from com.android.ide.common.vectordrawable.svg_tree import SvgTree  # Assuming SvgTree is in svg_tree.py

logger = logging.getLogger(__name__)

INDENT_UNIT = "  "
CONTINUATION_INDENT = INDENT_UNIT + INDENT_UNIT
TRANSFORM_TAG = "transform"

MATRIX_ATTRIBUTE = "matrix"
TRANSLATE_ATTRIBUTE = "translate"
ROTATE_ATTRIBUTE = "rotate"
SCALE_ATTRIBUTE = "scale"
SKEWX_ATTRIBUTE = "skewX"
SKEWY_ATTRIBUTE = "skewY"


class VisitResult:  # Using class instead of enum for simplicity with type hints
    CONTINUE = 0
    SKIP_CHILDREN = 1
    ABORT = 2


class Visitor(ABC):  # Defined as an abstract class for clarity
    @abstractmethod
    def visit(self, node: "SvgNode") -> int:  # Using forward reference for type hint
        """
        Called by the SvgNode.accept method for every visited node.

        :param node: the node being visited
        :return: VisitResult.CONTINUE to continue visiting children,
                 VisitResult.SKIP_CHILDREN to skip children and continue visit with the next sibling,
                 VisitResult.ABORT to skip all remaining nodes
        """
        ...


class SvgNode(ABC):
    """Parent class for a SVG file's node, can be either group or leaf element."""

    def __init__(self, svg_tree: SvgTree, element: Element, name: Optional[str] = None):
        self.name: Optional[str] = name
        # Keep a reference to the tree in order to dump the error log.
        self.svg_tree: SvgTree = svg_tree
        # Use document element to get the line number for error reporting.
        self.document_element: Element = element

        # Key is the attributes for vector drawable, and the value is the converted from SVG.
        self.vd_attributes_map: Dict[str, str] = {}
        # If local_transform is identity, it is the same as not having any transformation.
        self.local_transform: Tuple[float, float, float, float, float, float] = (
            1.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
        )

        # During the flatten() operation, we need to merge the transformation from top down.
        # This is the stacked transformation. And this will be used for the path data transform().
        self.stacked_transform: Tuple[float, float, float, float, float, float] = (
            1.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
        )
        self.parse_transform()

    def parse_transform(self):
        """While parsing the translate() rotate() ..., update the {@code mLocalTransform}."""
        node_value = self.document_element.getAttribute(TRANSFORM_TAG)
        if node_value:
            logger.debug(f"{TRANSFORM_TAG} {node_value}")
            self.parse_local_transform(node_value)

        # Parse and generate a presentation map.
        attributes = self.document_element.attributes
        for item_index in range(attributes.length):
            n = attributes.item(item_index)
            node_name = n.nodeName
            node_value = n.nodeValue

            if node_name in Svg2Vector.presentation_map:
                self.fill_presentation_attributes_internal(node_name, node_value)

    def parse_local_transform(self, node_value: str):
        # We separate the string into multiple parts and look like this:
        # "translate" "30" "rotate" "4.5e1 5e1 50"
        node_value = node_value.replace(",", " ")
        matrices = re.split(r"[()]", node_value)
        parsed_transform: Optional[Tuple[float, float, float, float, float, float]]
        for i in range(0, len(matrices) - 1, 2):
            parsed_transform = self.parse_one_transform(
                matrices[i].strip(), matrices[i + 1].strip()
            )
            if parsed_transform:
                self.local_transform = self.concatenate_transform(self.local_transform, parsed_transform)

    @staticmethod
    def concatenate_transform(
            t1: Tuple[float, float, float, float, float, float],
            t2: Tuple[float, float, float, float, float, float],
    ) -> Tuple[float, float, float, float, float, float]:
        """Concatenates two affine transformations, t1 and t2,  t1 * t2"""
        return (
            t1[0] * t2[0] + t1[2] * t2[1],
            t1[1] * t2[0] + t1[3] * t2[1],
            t1[0] * t2[2] + t1[2] * t2[3],
            t1[1] * t2[2] + t1[3] * t2[3],
            t1[0] * t2[4] + t1[2] * t2[5] + t1[4],
            t1[1] * t2[4] + t1[3] * t2[5] + t1[5],
        )

    @staticmethod
    def parse_one_transform(type: str, data: str) -> Optional[Tuple[float, float, float, float, float, float]]:
        numbers = SvgNode.get_numbers(data)
        if numbers is None:
            return None

        num_length = len(numbers)
        parsed_transform: Tuple[float, float, float, float, float, float] = (
            1.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
        )  # Identity matrix

        if type.lower() == MATRIX_ATTRIBUTE:
            if numLength != 6:
                return None
            parsed_transform = (
                numbers[0],
                numbers[1],
                numbers[2],
                numbers[3],
                numbers[4],
                numbers[5],
            )
        elif type.lower() == TRANSLATE_ATTRIBUTE:
            if num_length not in (1, 2):
                return None
            # Default translateY is 0
            parsed_transform = (
                1.0,
                0.0,
                0.0,
                1.0,
                numbers[0],
                numbers[1] if num_length == 2 else 0.0,
            )
        elif type.lower() == SCALE_ATTRIBUTE:
            if num_length not in (1, 2):
                return None
            # Default scaleY == scaleX
            scale_x = numbers[0]
            scale_y = numbers[1] if num_length == 2 else numbers[0]
            parsed_transform = (scale_x, 0.0, 0.0, scale_y, 0.0, 0.0)
        elif type.lower() == ROTATE_ATTRIBUTE:
            if num_length not in (1, 3):
                return None
            angle = math.radians(numbers[0])
            center_x = numbers[1] if num_length == 3 else 0.0
            center_y = numbers[2] if num_length == 3 else 0.0

            # Decompose rotate into translate, rotate, and translate back
            translate_to_origin = (1.0, 0.0, 0.0, 1.0, -center_x, -center_y)
            rotate = (math.cos(angle), math.sin(angle), -math.sin(angle), math.cos(angle), 0.0, 0.0)
            translate_back = (1.0, 0.0, 0.0, 1.0, center_x, center_y)

            parsed_transform = SvgNode.concatenate_transform(translate_to_origin, rotate)
            parsed_transform = SvgNode.concatenate_transform(parsed_transform, translate_back)

        elif type.lower() == SKEWX_ATTRIBUTE:
            if num_length != 1:
                return None
            # Note that Swing is pass the shear value directly to the matrix as m01 or m10,
            # while SVG is using tan(a) in the matrix and a is in radians.
            parsed_transform = (1.0, 0.0, math.tan(math.radians(numbers[0])), 1.0, 0.0, 0.0)
        elif type.lower() == SKEWY_ATTRIBUTE:
            if num_length != 1:
                return None
            parsed_transform = (1.0, math.tan(math.radians(numbers[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            return None

        return parsed_transform

    @staticmethod
    def get_numbers(data: str) -> Optional[List[float]]:
        numbers = data.split()
        if not numbers:
            return None

        results = []
        for number in numbers:
            try:
                results.append(float(number))
            except ValueError:
                return None
        return results

    def get_tree(self) -> SvgTree:
        return self.svg_tree

    def get_name(self) -> Optional[str]:
        return self.name

    def get_document_element(self) -> Element:
        return self.document_element

    @abstractmethod
    def dump_node(self, indent: str):
        """Dumps the current node's debug info."""
        ...

    @abstractmethod
    def write_xml(self, writer: io.StringIO, indent: str):
        """
        Writes content of the node into the VectorDrawable's XML file.

        :param writer: the writer to write the group XML element to
        :param indent: whitespace used for indenting output XML
        """
        ...

    def accept(self, visitor: Visitor) -> int:
        """
        Calls the Visitor.visit method for this node and its descendants.
        """
        return visitor.visit(self)

    @abstractmethod
    def is_group_node(self) -> bool:
        """Returns true the node is a group node."""
        ...

    @abstractmethod
    def transform_if_needed(self, final_transform: Tuple[float, float, float, float, float, float]):
        """Transforms the current Node with the transformation matrix."""
        ...

    def fill_presentation_attributes_internal(self, name: str, value: str):
        if name in (Svg2Vector.SVG_FILL_RULE, Svg2Vector.SVG_CLIP_RULE):
            if value == "nonzero":
                value = "nonZero"
            elif value == "evenodd":
                value = "evenOdd"
        logger.debug(f">>>> PROP {name} = {value}")
        if value.startswith("url("):
            if name not in (Svg2Vector.SVG_FILL, Svg2Vector.SVG_STROKE):
                self.log_error(f"Unsupported URL value: {value}")
                return

        if name == Svg2Vector.SVG_STROKE_WIDTH and value == "0":
            self.vd_attributes_map.pop(Svg2Vector.SVG_STROKE, None)  # Use pop to avoid KeyError

        self.vd_attributes_map[name] = value

    def fill_presentation_attributes(self, name: str, value: str):
        self.fill_presentation_attributes_internal(name, value)

    def fill_empty_attributes(self, parent_attributes_map: Dict[str, str]):
        # Go through the parents' attributes, if the child misses any, then fill it.
        for name, value in parent_attributes_map.items():
            if name not in self.vd_attributes_map:
                self.vd_attributes_map[name] = value

    @abstractmethod
    def flatten(self, transform: Tuple[float, float, float, float, float, float]):
        ...

    def validate(self):
        """Checks validity of the node and logs any issues associated with it.
        Subclasses may override.
        """
        pass

    def get_attribute_value(self, attribute: str) -> str:
        """Returns a string containing the value of the given attribute.
        Returns an empty string if the attribute does not exist.
        """
        return self.document_element.getAttribute(attribute)

    @abstractmethod
    def deep_copy(self) -> "SvgNode":
        ...

    def copy_from(self: "SvgNode", from_node: "SvgNode"):
        self.fill_empty_attributes(from_node.vd_attributes_map)
        self.local_transform = from_node.local_transform

    def color_svg_to_vd(self, svg_color: str, error_fallback_color: str) -> Optional[str]:
        """
        Converts an SVG color value to "#RRGGBB" or "#RGB" format used by
        vector drawables.  The input color value can be "none" and RGB value,
        e.g. "rgb(255, 0, 0)", or a color name defined in
        https://www.w3.org/TR/SVG11/types.html#ColorKeywords.

        :param svg_color: the SVG color value to convert
        :param error_fallback_color: the value returned if the supplied SVG color value has
        invalid or unsupported format
        :return: the converted value, or None if the given value cannot be
        interpreted as color
        """
        try:
            return SvgColor.color_svg_to_vd(svg_color)
        except ValueError:
            self.log_error(f"Unsupported color format \"{svg_color}\"")
            return error_fallback_color

    def log_error(self, message: str):
        self.svg_tree.log_error(message, self.document_element)

    def log_warning(self, message: str):
        self.svg_tree.log_warning(message, self.document_element)


class ClipRule(Enum):
    NON_ZERO = 0
    EVEN_ODD = 1