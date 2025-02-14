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
from typing import Optional, Dict, List, Tuple, Any
import io
from xml.dom.minidom import Element

from svg_to_vector import Svg2Vector

from svg_tree import SvgTree
from svg_node import *

from com.android.ide.common.vectordrawable.path_parser import PathParser, ParseMode
from com.android.ide.common.vectordrawable.vd_path import VdPath
from com.android.ide.common.vectordrawable.vd_util import format_float_value, \
    get_coordinate_format  # Assuming vd_util.py
from com.android.ide.common.vectordrawable.svg_gradient_node import \
    SvgGradientNode  # Assuming SvgGradientNode is in a separate module


logger = logging.getLogger(__name__)


class SvgLeafNode(SvgNode):
    """Represents an SVG file's leaf element."""

    def __init__(self, svg_tree: SvgTree, element: Element, node_name: Optional[str] = None):
        super().__init__(svg_tree, element, node_name)
        self.path_data: Optional[str] = None
        self.fill_gradient_node: Optional[SvgGradientNode] = None
        self.stroke_gradient_node: Optional[SvgGradientNode] = None

    def deep_copy(self) -> 'SvgLeafNode':
        new_node = SvgLeafNode(self.get_tree(), self.document_element, self.get_name())
        new_node.copy_from(self)
        return new_node

    def copy_from(self, from_node: 'SvgLeafNode'):
        super().copy_from(from_node)
        self.path_data = from_node.path_data
        self.fill_gradient_node = from_node.fill_gradient_node
        self.stroke_gradient_node = from_node.stroke_gradient_node

    def write_attribute_values(self, writer: io.StringIO, indent: str):
        """Writes attributes of this node."""

        # There could be some redundant opacity information in the attributes' map,
        # like opacity vs fill-opacity / stroke-opacity.
        self.parse_path_opacity()

        for name, svg_value in self.vd_attributes_map.items():
            attribute = Svg2Vector.presentation_map.get(name)
            if not attribute:
                continue

            svg_value = svg_value.strip()
            vd_value = self.color_svg_to_vd(svg_value, "#000000")

            if vd_value is None:
                if svg_value.endswith("px"):
                    vd_value = svg_value[:-2].strip()
                elif svg_value.startswith("url(#") and svg_value.endswith(")"):
                    vd_value = svg_value[5:-1]
                    if name == Svg2Vector.SVG_FILL:
                        node = self.get_tree().get_svg_node_from_id(vd_value)
                        if node is None:
                            continue
                        self.fill_gradient_node = node.deep_copy()
                        self.fill_gradient_node.set_svg_leaf_node(self)
                        self.fill_gradient_node.set_gradient_usage(SvgGradientNode.GradientUsage.FILL)
                    elif name == Svg2Vector.SVG_STROKE:
                        node = self.get_tree().get_svg_node_from_id(vd_value)
                        if node is None:
                            continue
                        self.stroke_gradient_node = node.deep_copy()
                        self.stroke_gradient_node.set_svg_leaf_node(self)
                        self.stroke_gradient_node.set_gradient_usage(SvgGradientNode.GradientUsage.STROKE)
                    continue  # Skip writing url value.

                else:
                    vd_value = svg_value

            writer.write('\n')
            writer.write(indent)
            writer.write(CONTINUATION_INDENT)
            writer.write(attribute)
            writer.write("=\"")
            writer.write(vd_value)
            writer.write("\"")

    def parse_path_opacity(self):
        """Parses the SVG path's opacity attribute into fill and stroke."""
        opacity = self.get_opacity_value_from_map(Svg2Vector.SVG_OPACITY)
        fill_opacity = self.get_opacity_value_from_map(Svg2Vector.SVG_FILL_OPACITY)
        stroke_opacity = self.get_opacity_value_from_map(Svg2Vector.SVG_STROKE_OPACITY)
        self.put_opacity_value_to_map(Svg2Vector.SVG_FILL_OPACITY, fill_opacity * opacity)
        self.put_opacity_value_to_map(Svg2Vector.SVG_STROKE_OPACITY, stroke_opacity * opacity)
        self.vd_attributes_map.pop(Svg2Vector.SVG_OPACITY, None)

    def get_opacity_value_from_map(self, attribute_name: str) -> float:
        """
        A utility function to get the opacity value as a floating point number.

        :param attribute_name: the name of the opacity attribute
        :return: the clamped opacity value, or 1 if not found
        """
        # Default opacity is 1.
        result = 1.0
        opacity = self.vd_attributes_map.get(attribute_name)
        if opacity is not None:
            try:
                if opacity.endswith("%"):
                    result = float(opacity[:-1]) / 100.0
                else:
                    result = float(opacity)
            except ValueError:
                pass  # Ignore here, an invalid value is replaced by the default value 1.
        return min(max(result, 0.0), 1.0)

    def put_opacity_value_to_map(self, attribute_name: str, opacity: float):
        attribute_value = format_float_value(opacity)
        if attribute_value == "1":
            self.vd_attributes_map.pop(attribute_name, None)
        else:
            self.vd_attributes_map[attribute_name] = attribute_value

    def dump_node(self, indent: str):
        logger.debug(indent + (self.path_data if self.path_data else " null pathData ") +
                     (self.name if self.name else " null name "))

    def set_path_data(self, path_data: str):
        self.path_data = path_data

    def get_path_data(self) -> Optional[str]:
        return self.path_data

    def is_group_node(self) -> bool:
        return False

    def has_gradient(self) -> bool:
        return self.fill_gradient_node is not None or self.stroke_gradient_node is not None

    def transform_if_needed(self, root_transform: Tuple[float, float, float, float, float, float]):
        if not self.path_data:
            return

        nodes = PathParser.parse_path(self.path_data, ParseMode.SVG)
        final_transform = self.concatenate_transform(root_transform, self.stacked_transform)
        needs_convert_relative_move_after_close = VdPath.Node.has_rel_move_after_close(nodes)
        if final_transform != (1.0, 0.0, 0.0, 1.0, 0.0, 0.0) or needs_convert_relative_move_after_close:
            VdPath.Node.transform(final_transform, nodes)

        coordinate_format = self.svg_tree.get_coordinate_format()
        self.path_data = VdPath.Node.node_list_to_string(nodes, coordinate_format)

    def flatten(self, transform: Tuple[float, float, float, float, float, float]):
        self.stacked_transform = self.concatenate_transform(transform, self.local_transform)

        if "non-scaling-stroke" != self.vd_attributes_map.get("vector-effect") and \
                (self.is_scale_type(self.stacked_transform)):

            stroke_width = self.vd_attributes_map.get(Svg2Vector.SVG_STROKE_WIDTH)
            if stroke_width:
                try:
                    # Unlike SVG, vector drawable is not capable of applying transformations
                    # to stroke outline. To compensate for that we apply scaling transformation
                    # to the stroke width, which produces accurate results for uniform and
                    # approximate results for non-uniform scaling transformation.
                    width = float(stroke_width)
                    a11, a21, a12, a22, _, _ = self.stacked_transform  # Unpack for clarity.
                    determinant = a11 * a22 - a21 * a12  # a11 * a22 - a12 * a21

                    if determinant != 0:
                        width *= math.sqrt(abs(determinant))
                        self.vd_attributes_map[Svg2Vector.SVG_STROKE_WIDTH] = format_float_value(width)

                    if self.is_general_scale_type(self.stacked_transform):
                        self.log_warning("Scaling of stroke width is an approximation")
                except ValueError:
                    pass

    def is_scale_type(self, transform: Tuple[float, float, float, float, float, float]) -> bool:
        """ Checks if the transform matrix only contains scaling and translation. """
        return not (transform[1] or transform[2])  # a12 or a21 in matrix.

    def is_general_scale_type(self, transform: Tuple[float, float, float, float, float, float]) -> bool:
        return transform[0] != transform[3]  # a11 != a22 in matrix

    def write_xml(self, writer: io.StringIO, indent: str):
        # First, decide whether or not we can skip this path, since it has no visible effect.
        if self.path_data is None or not self.path_data.strip():
            return  # No path to draw.

        fill_color = self.vd_attributes_map.get(Svg2Vector.SVG_FILL)
        stroke_color = self.vd_attributes_map.get(Svg2Vector.SVG_STROKE)
        logger.debug(f"fill color {fill_color}")
        empty_fill = fill_color == "none" or fill_color == "#00000000"
        empty_stroke = stroke_color is None or stroke_color == "none"
        if empty_fill and empty_stroke:
            return  # Nothing to draw.

        # Second, write the color info handling the default values.
        writer.write(indent)
        writer.write("<path")
        writer.write('\n')
        if fill_color is None and self.fill_gradient_node is None:
            logger.debug("Adding default fill color")
            writer.write(indent)
            writer.write(CONTINUATION_INDENT)
            writer.write("android:fillColor=\"#FF000000\"")
            writer.write('\n')

        if (not empty_stroke
                and Svg2Vector.SVG_STROKE_WIDTH not in self.vd_attributes_map
                and self.stroke_gradient_node is None):
            logger.debug("Adding default stroke width")
            writer.write(indent)
            writer.write(CONTINUATION_INDENT)
            writer.write("android:strokeWidth=\"1\"")
            writer.write('\n')

        # Last, write the path data and all associated attributes.
        writer.write(indent)
        writer.write(CONTINUATION_INDENT)
        writer.write(f"android:pathData=\"{self.path_data}\"")
        self.write_attribute_values(writer, indent)
        if not self.has_gradient():
            writer.write('/')

        writer.write('>')
        writer.write('\n')

        if self.fill_gradient_node:
            self.fill_gradient_node.write_xml(writer, indent + INDENT_UNIT)

        if self.stroke_gradient_node:
            self.stroke_gradient_node.write_xml(writer, indent + INDENT_UNIT)

        if self.has_gradient():
            writer.write(indent)
            writer.write("</path>")
            writer.write('\n')