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
import os
from typing import List, Dict, Set, Tuple, Optional, Any
from xml.dom import minidom
from xml.dom.minidom import Node, Document, NamedNodeMap
from com.android.ide.common.vectordrawable.svg_node import SvgNode, SvgGroupNode  # Assuming svg_node.py
from com.android.ide.common.vectordrawable.vd_util import VdUtil, get_coordinate_format
import io
from enum import Enum
from collections import OrderedDict
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)

HEAD = "<vector xmlns:android=\"http://schemas.android.com/apk/res/android\""
AAPT_BOUND = "xmlns:aapt=\"http://schemas.android.com/aapt\""

SVG_WIDTH = "width"
SVG_HEIGHT = "height"
SVG_VIEW_BOX = "viewBox"


@dataclass(order=True)
class LogMessage:
    level: "SvgLogLevel"
    line: int
    message: str

    def get_formatted_message(self) -> str:
        return f"{self.level.name}{'' if self.line == 0 else f' @ line {self.line}'}: {self.message}"


class SvgLogLevel(Enum):
    ERROR = 1
    WARNING = 2


class SvgTree:
    def __init__(self):
        self.w: float = -1.0
        self.h: float = -1.0
        self.root_transform: Tuple[float, float, float, float, float, float] = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        self.viewbox: Optional[List[float]] = None
        self.scale_factor: float = 1.0

        self.root: Optional[SvgGroupNode] = None
        self.filename: str = ""

        self.log_messages: List[LogMessage] = []

        self.has_leaf_node: bool = False
        self.has_gradient: bool = False

        # Map of SvgNode's id to the SvgNode.
        self.id_map: Dict[str, SvgNode] = {}

        # IDs of ignored SVG nodes.
        self.ignored_ids: Set[str] = set()

        # Set of SvgGroupNodes that contain use elements.
        self.pending_use_group_set: Set[SvgGroupNode] = set()

        # Key is SvgNode that references a clipPath. Value is SvgGroupNode that is the parent of that SvgNode.
        self.clip_path_affected_nodes: Dict[SvgNode, Tuple[SvgGroupNode, str]] = OrderedDict()

        # Key is String that is the id of a style class. Value is set of SvgNodes referencing that class.
        self.style_affected_nodes: Dict[str, Set[SvgNode]] = {}

        # Key is String that is the id of a style class. Value is a String that contains attribute information.
        self.style_class_attribute_map: Dict[str, str] = {}

    def get_width(self) -> float:
        return self.w

    def get_height(self) -> float:
        return self.h

    def get_scale_factor(self) -> float:
        return self.scale_factor

    def set_has_leaf_node(self, has_leaf_node: bool):
        self.has_leaf_node = has_leaf_node

    def set_has_gradient(self, has_gradient: bool):
        self.has_gradient = has_gradient

    def get_view_box(self) -> Optional[List[float]]:
        return self.viewbox

    def get_has_leaf_node(self) -> bool:
        return self.has_leaf_node

    def get_has_gradient(self) -> bool:
        return self.has_gradient

    def get_view_port_width(self) -> float:
        return -1.0 if self.viewbox is None else self.viewbox[2]

    def get_view_port_height(self) -> float:
        return -1.0 if self.viewbox is None else self.viewbox[3]

    def flatten(self):
        """From the root, top down, pass the transformation (TODO: attributes) down the children."""
        if self.root:
            self.root.flatten((1, 0, 0, 1, 0, 0))

    def validate(self):
        """Validates all nodes and logs any encountered issues."""
        if self.root:
            self.root.validate()
        if not self.log_messages and not self.get_has_leaf_node():
            self.log_error("No vector content found", None)

    def get_start_line(node: Node) -> int:
        """Returns 1-based line number"""
        # Simulate getLineNumber() from Java's PositionXmlParser
        # minidom doesn't inherently track line numbers, so we have to do a bit of work.
        # This is a simple (but potentially slow) implementation for demonstration purposes.
        return node.sourceline

    def parse(self, f: str, parse_errors: List[str]) -> Document:
        self.filename = os.path.basename(f)
        try:
            with open(f, 'rb') as file:
                # Read file content and close the file
                content = file.read()

            # Manually track line numbers (Simple example, not fully robust).
            lines = content.decode('utf-8').splitlines(keepends=True)
            line_map = {}
            current_line = 1
            acc_pos = 0
            for line in lines:
                line_map[acc_pos] = current_line
                acc_pos += len(line)
                current_line += 1

            def get_line_number(node):
                if node.nodeType == Node.TEXT_NODE:
                    pos = node.start_tag_end_pos if hasattr(node, 'start_tag_end_pos') else node.position
                else:
                    pos = node.position if hasattr(node, "position") else None  # Get node's starting pos

                if pos is not None:
                    # Find the closest saved line start position.
                    starts = sorted(line_map.keys())
                    line_start = next((start for start in reversed(starts) if start <= pos), 0)
                    return line_map.get(line_start, 1)  # Default to 1 if not found
                return 1

            doc = minidom.parseString(content)

            # Attach line numbers to each node.
            def set_line_numbers(node):
                node.sourceline = get_line_number(node)
                for child in node.childNodes:
                    set_line_numbers(child)

            set_line_numbers(doc)

            return doc

        except Exception as e:
            parse_errors.append(str(e))
            return minidom.parseString("<svg/>")  # Return an empty SVG document on error

    def normalize(self):
        # mRootTransform is always setup, now just need to apply the viewbox info into.
        if self.viewbox:
            tx = -self.viewbox[0]
            ty = -self.viewbox[1]
            self.root_transform = (1, 0, 0, 1, tx, ty)  # row-major matrix
            self.transform(self.root_transform)
            logger.debug(f"matrix={self.root_transform}")

    def transform(self, root_transform: Tuple[float, float, float, float, float, float]):
        if self.root:
            self.root.transform_if_needed(root_transform)

    def dump(self):
        logger.debug(f"file: {self.filename}")
        if self.root:
            self.root.dump_node("")

    def set_root(self, root: SvgGroupNode):
        self.root = root

    def get_root(self) -> Optional[SvgGroupNode]:
        return self.root

    def log_error(self, message: str, node: Optional[Node]):
        self.log_error_line(message, node, SvgLogLevel.ERROR)

    def log_warning(self, message: str, node: Optional[Node]):
        self.log_error_line(message, node, SvgLogLevel.WARNING)

    def log_error_line(self, message: str, node: Optional[Node], level: SvgLogLevel):
        assert message
        line = 0 if node is None else self.get_start_line(node)
        self.log_messages.append(LogMessage(level, line, message))

    def get_error_message(self) -> str:
        """Returns the error message that combines all logged errors and warnings.
            If there were no errors, returns an empty string.
        """

        if not self.log_messages:
            return ""

        self.log_messages.sort()  # Sort by severity and line number

        result = []

        for message in self.log_messages:
            if result:
                result.append('\n')
            result.append(message.get_formatted_message())

        return "".join(result)

    class SizeType(Enum):
        PIXEL = 1
        PERCENTAGE = 2

    def parse_dimension(self, n_node: Node):
        attributes = n_node.attributes
        width_type = self.SizeType.PIXEL
        height_type = self.SizeType.PIXEL

        for i in range(attributes.length):
            n = attributes.item(i)
            name = n.nodeName.strip()
            value = n.nodeValue.strip()
            sub_string_size = len(value)
            current_type = self.SizeType.PIXEL
            unit = value[-2:]

            if unit.isalpha() and unit in ("em", "ex", "px", "in", "cm", "mm", "pt", "pc"):
                sub_string_size -= 2
            elif value.endswith("%"):
                sub_string_size -= 1
                current_type = self.SizeType.PERCENTAGE

            if name == SVG_WIDTH:
                self.w = float(value[:sub_string_size])
                width_type = current_type
            elif name == SVG_HEIGHT:
                self.h = float(value[:sub_string_size])
                height_type = current_type
            elif name == SVG_VIEW_BOX:
                self.viewbox = [float(x) for x in value.split(" ")]

        # If there is no viewbox, then set it up according to w, h.
        # From now on, viewport should be read from viewbox, and size should be from w and h.
        # w and h can be set to percentage too, in this case, set it to the viewbox size.
        if self.viewbox is None and self.w > 0 and self.h > 0:
            self.viewbox = [0.0, 0.0, self.w, self.h]
        elif (self.w < 0 or self.h < 0) and self.viewbox:
            self.w = self.viewbox[2]
            self.h = self.viewbox[3]

        if width_type == self.SizeType.PERCENTAGE and self.w > 0 and self.viewbox:
            self.w = self.viewbox[2] * self.w / 100
        if height_type == self.SizeType.PERCENTAGE and self.h > 0 and self.viewbox:
            self.h = self.viewbox[3] * self.h / 100

    def parse_x_value(self, value: str) -> float:
        """Parses X coordinate or width."""
        return self.parse_coordinate_or_length(value, self.get_view_port_width())

    def parse_y_value(self, value: str) -> float:
        """Parses Y coordinate or height."""
        return self.parse_coordinate_or_length(value, self.get_view_port_height())

    def parse_coordinate_or_length(self, value: str, percentage_base: float) -> float:
        if value.endswith("%"):
            return float(value[:-1]) / 100 * percentage_base
        else:
            return float(value)

    def add_id_to_map(self, id: str, svg_node: SvgNode):
        self.id_map[id] = svg_node

    def get_svg_node_from_id(self, id: str) -> Optional[SvgNode]:
        return self.id_map.get(id)

    def add_to_pending_use_set(self, use_group: SvgGroupNode):
        self.pending_use_group_set.add(use_group)

    def get_pending_use_set(self) -> Set[SvgGroupNode]:
        return self.pending_use_group_set

    def add_ignored_id(self, id: str):
        self.ignored_ids.add(id)

    def is_id_ignored(self, id: str) -> bool:
        return id in self.ignored_ids

    def add_clip_path_affected_node(self, child: SvgNode, current_group: SvgGroupNode, clip_path_name: str):
        self.clip_path_affected_nodes[child] = (current_group, clip_path_name)

    def get_clip_path_affected_nodes_set(self):
        return self.clip_path_affected_nodes.items()

    def add_affected_node_to_style_class(self, class_name: str, child: SvgNode):
        if class_name in self.style_affected_nodes:
            self.style_affected_nodes[class_name].add(child)
        else:
            style_nodes_set = set()
            style_nodes_set.add(child)
            self.style_affected_nodes[class_name] = style_nodes_set

    def add_style_class_to_tree(self, class_name: str, attributes: str):
        self.style_class_attribute_map[class_name] = attributes

    def get_style_class_attr(self, classname: str) -> Optional[str]:
        return self.style_class_attribute_map.get(classname)

    def get_style_affected_nodes(self):
        return self.style_affected_nodes.items()

    def find_parent(self, node: SvgNode) -> Optional[SvgGroupNode]:
        """Finds the parent node of the input node.
        Returns the parent node, or None if node is not in the tree.
        """
        return self.root.find_parent(node) if self.root else None

    def get_coordinate_format(self) -> Any:
        """Returns a NumberFormat of sufficient precision to use for
            formatting coordinate values within the viewport.
        """
        viewport_width = self.get_view_port_width()
        viewport_height = self.get_view_port_height()
        return get_coordinate_format(max(viewport_width, viewport_height))

    def write_xml(self, stream: io.IOBase):
        if self.root is None:
            raise ValueError("SvgTree is not fully initialized")

        writer = io.StringIO()
        writer.write(HEAD)
        writer.write('\n')
        if self.get_has_gradient():
            writer.write(SvgNode.CONTINUATION_INDENT)
            writer.write(AAPT_BOUND)
            writer.write('\n')

        viewport_width = self.get_view_port_width()
        viewport_height = self.get_view_port_height()

        writer.write(SvgNode.CONTINUATION_INDENT)
        writer.write("android:width=\"")
        writer.write(VdUtil.format_float_value(self.get_width() * self.get_scale_factor()))
        writer.write("dp\"")
        writer.write('\n')
        writer.write(SvgNode.CONTINUATION_INDENT)