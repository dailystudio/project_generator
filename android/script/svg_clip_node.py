#
# Copyright (C) 2017 The Android Open Source Project
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
from typing import List, Optional, Tuple, Dict
import io
from xml.dom.minidom import Element
from enum import Enum

from svg_to_vector import Svg2Vector
from svg_tree import SvgTree
from svg_node import *

from com.android.ide.common.vectordrawable.svg_node import SvgNode, SvgGroupNode, Visitor, VisitResult, \
    SvgLeafNode  # Assuming svg_node is in svg_node.py
from com.android.ide.common.vectordrawable.vd_util import parse_color_value

logger = logging.getLogger(__name__)

TAG_CLIP_PATH = "clip-path"
SVG_MASK = "mask"


class SvgClipPathNode(SvgGroupNode):
    """
    Represents a SVG group element that contains a clip-path. SvgClipPathNode's mChildren will
    contain the actual path data of the clip-path. The path of the clip will be constructed in
    write_xml by concatenating mChildren's paths. mAffectedNodes contains any group or leaf
    nodes that are clipped by the path.
    """

    def __init__(self, svg_tree: SvgTree, element: Element, name: Optional[str] = None):
        super().__init__(svg_tree, element, name)
        self.affected_nodes: List[SvgNode] = []

    def deep_copy(self) -> 'SvgClipPathNode':
        new_instance = SvgClipPathNode(self.get_tree(), self.document_element, self.name)
        new_instance.copy_from(self)
        return new_instance

    def copy_from(self, from_node: 'SvgClipPathNode'):
        super().copy_from(from_node)
        for node in from_node.affected_nodes:
            self.add_affected_node(node)

    def add_child(self, child: SvgNode):
        # Pass the presentation map down to the children, who can override the attributes.
        self.children.append(child)
        # The child has its own attributes map. But the parents can still fill some attributes
        # if they don't exist.
        child.fill_empty_attributes(self.vd_attributes_map)

    def add_affected_node(self, child: SvgNode):
        self.affected_nodes.append(child)
        child.fill_empty_attributes(self.vd_attributes_map)

    def flatten(self, transform: Tuple[float, float, float, float, float, float]):
        for n in self.children:
            self.stacked_transform = self.concatenate_transform(transform, self.local_transform)
            n.flatten(self.stacked_transform)

        self.stacked_transform = transform
        for n in self.affected_nodes:
            n.flatten(self.stacked_transform)  # mLocalTransform does not apply to mAffectedNodes.

        self.stacked_transform = self.concatenate_transform(self.stacked_transform, self.local_transform)

        if self.vd_attributes_map.get(Svg2Vector.SVG_STROKE_WIDTH) and self.is_scale_type(self.stacked_transform):
            self.log_warning("Scaling of the stroke width is ignored")

    def validate(self):
        super().validate()
        if self.document_element.tagName == SVG_MASK and not self.is_white_fill():
            # A mask that is not solid white creates a transparency effect that
            # cannot be reproduced by a clip-path.
            self.log_error("Semitransparent mask cannot be represented by a vector drawable")

    def is_white_fill(self) -> bool:
        fill_color = self.vd_attributes_map.get("fill")
        if fill_color is None:
            return False

        fill_color = self.color_svg_to_vd(fill_color, "#000")
        if fill_color is None:
            return False
        return parse_color_value(fill_color) == 0xFFFFFFFF

    def transform_if_needed(self, root_transform: Tuple[float, float, float, float, float, float]):
        for p in self.children + self.affected_nodes:
            p.transform_if_needed(root_transform)

    def write_xml(self, writer: io.StringIO, indent: str):
        writer.write(indent)
        writer.write("<group>")
        writer.write('\n')
        incremented_indent = indent + INDENT_UNIT

        clip_paths: Dict["ClipRule", List[str]] = {}  # Use dict, not EnumMap

        def clip_path_collector(node: SvgNode) -> int:
            if isinstance(node, SvgLeafNode):
                path_data = node.get_path_data()
                if path_data and path_data.strip():
                    clip_rule = (
                        ClipRule.EVEN_ODD
                        if node.vd_attributes_map.get(Svg2Vector.SVG_CLIP_RULE) == "evenOdd"
                        else ClipRule.NON_ZERO
                    )
                    if clip_rule not in clip_paths:
                        clip_paths[clip_rule] = []
                    clip_paths[clip_rule].append(path_data)
            return VisitResult.CONTINUE

        visitor = Visitor()
        visitor.visit = clip_path_collector

        for node in self.children:
            node.accept(visitor)

        for clip_rule, path_data_list in clip_paths.items():
            writer.write(incremented_indent)
            writer.write(f"<{TAG_CLIP_PATH}")
            writer.write('\n')
            writer.write(incremented_indent)
            writer.write(INDENT_UNIT)
            writer.write(INDENT_UNIT)
            writer.write("android:pathData=\"")
            for i, path in enumerate(path_data_list):
                if i > 0 and not path.startswith("M"):
                    # Reset the current position to origin of the coordinate system
                    writer.write("M 0,0")
                writer.write(path)

            writer.write("\"")
            if clip_rule == ClipRule.EVEN_ODD:
                writer.write('\n')
                writer.write(incremented_indent)
                writer.write(INDENT_UNIT)
                writer.write(INDENT_UNIT)
                writer.write("android:fillType=\"evenOdd\"")
            writer.write("/>")
            writer.write('\n')

        for node in self.affected_nodes:
            node.write_xml(writer, incremented_indent)

        writer.write(indent)
        writer.write("</group>")
        writer.write('\n')

    def set_clip_path_node_attributes(self):
        """
        Concatenates the affected nodes transformations to the clipPathNode's so it is
        properly transformed.
        """
        for n in self.affected_nodes:
            self.local_transform = self.concatenate_transform(self.local_transform, n.local_transform)


class ClipRule(Enum):
    NON_ZERO = 0
    EVEN_ODD = 1