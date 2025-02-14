#
# Copyright (C) 2015 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
import os
import re
from xml.dom import minidom
from xml.dom.minidom import Node
import math
from typing import Dict, Set, List, Tuple, Optional

# Assuming SvgTree and related classes are in a separate module named 'svg_tree'
# In a real implementation, you'd have a separate file svg_tree.py
from com.android.ide.common.vectordrawable.svg_tree import SvgGroupNode, SvgLeafNode, SvgClipPathNode, \
    SvgGradientNode
from com.android.ide.common.vectordrawable.path_builder import PathBuilder

from svg_tree import SvgTree
from svg_node import SvgNode

logger = logging.getLogger(__name__)

SVG_DEFS = "defs"
SVG_USE = "use"
SVG_HREF = "href"
SVG_XLINK_HREF = "xlink:href"

SVG_POLYGON = "polygon"
SVG_POLYLINE = "polyline"
SVG_RECT = "rect"
SVG_CIRCLE = "circle"
SVG_LINE = "line"
SVG_PATH = "path"
SVG_ELLIPSE = "ellipse"
SVG_GROUP = "g"
SVG_STYLE = "style"
SVG_DISPLAY = "display"
SVG_CLIP_PATH_ELEMENT = "clipPath"

SVG_D = "d"
SVG_STROKE = "stroke"
SVG_STROKE_OPACITY = "stroke-opacity"
SVG_STROKE_LINEJOIN = "stroke-linejoin"
SVG_STROKE_LINECAP = "stroke-linecap"
SVG_STROKE_WIDTH = "stroke-width"
SVG_FILL = "fill"
SVG_FILL_OPACITY = "fill-opacity"
SVG_FILL_RULE = "fill-rule"
SVG_OPACITY = "opacity"
SVG_CLIP = "clip"
SVG_CLIP_PATH = "clip-path"
SVG_CLIP_RULE = "clip-rule"
SVG_MASK = "mask"
SVG_POINTS = "points"

presentation_map = {
    SVG_CLIP: "android:clip",
    SVG_CLIP_RULE: "",  # Treated individually.
    SVG_FILL: "android:fillColor",
    SVG_FILL_RULE: "android:fillType",
    SVG_FILL_OPACITY: "android:fillAlpha",
    SVG_OPACITY: "",  # Treated individually.
    SVG_STROKE: "android:strokeColor",
    SVG_STROKE_OPACITY: "android:strokeAlpha",
    SVG_STROKE_LINEJOIN: "android:strokeLineJoin",
    SVG_STROKE_LINECAP: "android:strokeLineCap",
    SVG_STROKE_WIDTH: "android:strokeWidth",
}

gradient_map = {
    "x1": "android:startX",
    "y1": "android:startY",
    "x2": "android:endX",
    "y2": "android:endY",
    "cx": "android:centerX",
    "cy": "android:centerY",
    "r": "android:gradientRadius",
    "spreadMethod": "android:tileMode",
    "gradientUnits": "",
    "gradientTransform": "",
    "gradientType": "android:type",
}

# Set of all SVG nodes that we don't support. Categorized by the types.
unsupported_svg_nodes = {
    # Animation elements.
    "animate",
    "animateColor",
    "animateMotion",
    "animateTransform",
    "mpath",
    "set",
    # Container elements.
    "a",
    "glyph",
    "marker",
    "missing-glyph",
    "pattern",
    "switch",
    "symbol",
    # Filter primitive elements.
    "feBlend",
    "feColorMatrix",
    "feComponentTransfer",
    "feComposite",
    "feConvolveMatrix",
    "feDiffuseLighting",
    "feDisplacementMap",
    "feFlood",
    "feFuncA",
    "feFuncB",
    "feFuncG",
    "feFuncR",
    "feGaussianBlur",
    "feImage",
    "feMerge",
    "feMergeNode",
    "feMorphology",
    "feOffset",
    "feSpecularLighting",
    "feTile",
    "feTurbulence",
    # Font elements.
    "font",
    "font-face",
    "font-face-format",
    "font-face-name",
    "font-face-src",
    "font-face-uri",
    "hkern",
    "vkern",
    # Gradient elements.
    "stop",
    # Graphics elements.
    "ellipse",
    "image",
    "text",
    # Light source elements.
    "feDistantLight",
    "fePointLight",
    "feSpotLight",
    # Structural elements.
    "symbol",
    # Text content elements.
    "altGlyph",
    "altGlyphDef",
    "altGlyphItem",
    "glyph",
    "glyphRef",
    "textPath",
    "text",
    "tref",
    "tspan",
    # Text content child elements.
    "altGlyph",
    "textPath",
    "tref",
    "tspan",
    # Uncategorized elements.
    "color-profile",
    "cursor",
    "filter",
    "foreignObject",
    "script",
    "view",
}

SPACE_OR_COMMA = re.compile(r"[\s,]+")


def format_float_value(value: float) -> str:
    """Formats a float value to a string, handling precision."""
    return f"{value:.6f}".rstrip('0').rstrip('.')


def parse(f: str) -> SvgTree:
    svg_tree = SvgTree()
    parse_errors = []
    doc = svg_tree.parse(f, parse_errors)
    for error in parse_errors:
        svg_tree.log_error(error, None)

    # Get <svg> elements.
    svg_nodes = doc.getElementsByTagName("svg")
    if len(svg_nodes) != 1:
        raise ValueError("Not a proper SVG file")

    root_element = svg_nodes[0]
    svg_tree.parse_dimension(root_element)

    if svg_tree.get_view_box() is None:
        svg_tree.log_error("Missing \"viewBox\" in <svg> element", root_element)
        return svg_tree

    root = SvgGroupNode(svg_tree, root_element, "root")
    svg_tree.set_root(root)

    # Parse all the group and path nodes recursively.
    traverse_svg_and_extract(svg_tree, root, root_element)

    # Fill in all the <use> nodes in the svgTree.
    nodes = svg_tree.get_pending_use_set()
    while nodes:
        if not any(extract_use_node(svg_tree, node, node.get_document_element()) for node in list(nodes)):
            # Not able to make progress because of cyclic references.
            report_cycles(svg_tree, nodes)
            break
        nodes = svg_tree.get_pending_use_set()  # Update the set after processing.

    # Add attributes for all the style elements.
    for class_name, affected_nodes in svg_tree.get_style_affected_nodes():
        for n in affected_nodes:
            add_style_to_path(n, svg_tree.get_style_class_attr(class_name))

    # Replaces elements that reference clipPaths and replaces them with clipPathNodes
    # Note that clip path can be embedded within style, so it has to be called after
    # addStyleToPath.
    for entry in svg_tree.get_clip_path_affected_nodes_set():
        node, (group_node, value) = entry
        handle_clip_path(svg_tree, node, group_node, value)

    svg_tree.flatten()
    svg_tree.validate()
    svg_tree.dump()

    return svg_tree


def report_cycles(svg_tree: SvgTree, svg_nodes: Set[SvgGroupNode]):
    edges = {}
    nodes_by_id = {}
    for svg_node in svg_nodes:
        element = svg_node.get_document_element()
        id_attr = element.getAttribute("id")
        if id_attr:
            target_id = element.getAttribute(SVG_HREF)
            if not target_id:
                target_id = element.getAttribute(SVG_XLINK_HREF)
            if target_id:
                edges[id_attr] = get_id_from_reference(target_id)
                nodes_by_id[id_attr] = element

    while edges:
        visited = set()
        entry = next(iter(edges.items()))
        id_node, target_id = entry
        while target_id and id_node not in visited:
            visited.add(id_node)
            id_node = target_id
            target_id = edges.get(id_node)

        if target_id:  # Broken links are reported separately. Ignore them here.
            node = nodes_by_id[id_node]
            cycle = get_cycle_starting_at(id_node, edges, nodes_by_id)
            svg_tree.log_error("Circular dependency of <use> nodes: " + cycle, node)

        edges = {k: v for k, v in edges.items() if k not in visited}


def get_cycle_starting_at(start_id: str, edges: Dict[str, str], nodes_by_id: Dict[str, Node]) -> str:
    buf = [start_id]
    id_node = start_id
    while True:
        id_node = edges[id_node]
        buf.append(" -> " + id_node)
        if id_node == start_id:
            break
        buf.append(f" (line {SvgTree.get_start_line(nodes_by_id[id_node])})")

    return "".join(buf)


def traverse_svg_and_extract(svg_tree: SvgTree, current_group: SvgGroupNode, item: Node):
    child_nodes = item.childNodes

    for i in range(child_nodes.length):
        child_node = child_nodes[i]
        if (child_node.nodeType != Node.ELEMENT_NODE
                or (not child_node.hasChildNodes() and not child_node.hasAttributes())):
            continue  # The node contains no information, just ignore it.

        child_element = child_node
        tag_name = child_element.tagName

        if tag_name in (SVG_PATH, SVG_RECT, SVG_CIRCLE, SVG_ELLIPSE, SVG_POLYGON, SVG_POLYLINE, SVG_LINE):
            child = SvgLeafNode(svg_tree, child_element, tag_name + str(i))
            process_id_name(svg_tree, child)
            current_group.add_child(child)
            extract_all_items_as(svg_tree, child, child_element, current_group)
            svg_tree.set_has_leaf_node(True)

        elif tag_name == SVG_GROUP:
            child_group = SvgGroupNode(svg_tree, child_element, "child" + str(i))
            current_group.add_child(child_group)
            process_id_name(svg_tree, child_group)
            extract_group_node(svg_tree, child_group, current_group)
            traverse_svg_and_extract(svg_tree, child_group, child_element)

        elif tag_name == SVG_USE:
            child_group = SvgGroupNode(svg_tree, child_element, "child" + str(i))
            process_id_name(svg_tree, child_group)
            current_group.add_child(child_group)
            svg_tree.add_to_pending_use_set(child_group)

        elif tag_name == SVG_DEFS:
            child_group = SvgGroupNode(svg_tree, child_element, "child" + str(i))
            traverse_svg_and_extract(svg_tree, child_group, child_element)

        elif tag_name in (SVG_CLIP_PATH_ELEMENT, SVG_MASK):
            clip_path = SvgClipPathNode(svg_tree, child_element, tag_name + str(i))
            process_id_name(svg_tree, clip_path)
            traverse_svg_and_extract(svg_tree, clip_path, child_element)

        elif tag_name == SVG_STYLE:
            extract_style_node(svg_tree, child_element)

        elif tag_name == "linearGradient":
            gradient_node = SvgGradientNode(svg_tree, child_element, tag_name + str(i))
            process_id_name(svg_tree, gradient_node)
            extract_gradient_node(svg_tree, gradient_node)
            gradient_node.fill_presentation_attributes("gradientType", "linear")
            svg_tree.set_has_gradient(True)

        elif tag_name == "radialGradient":
            gradient_node = SvgGradientNode(svg_tree, child_element, tag_name + str(i))
            process_id_name(svg_tree, gradient_node)
            extract_gradient_node(svg_tree, gradient_node)
            gradient_node.fill_presentation_attributes("gradientType", "radial")
            svg_tree.set_has_gradient(True)

        else:
            id_attr = child_element.getAttribute("id")
            if id_attr:
                svg_tree.add_ignored_id(id_attr)

            # For other fancy tags, like <switch>, they can contain children too.
            # Report the unsupported nodes.
            if tag_name in unsupported_svg_nodes:
                svg_tree.log_error("<" + tag_name + "> is not supported", child_element)

            # This is a workaround for the cases using defs to define a full icon size clip
            # path, which is redundant information anyway.
            traverse_svg_and_extract(svg_tree, current_group, child_element)


def extract_gradient_node(svg: SvgTree, gradient_node: SvgGradientNode):
    element = gradient_node.get_document_element()
    attributes = element.attributes
    for j in range(attributes.length):
        n = attributes.item(j)
        name = n.nodeName
        value = n.nodeValue
        if name in gradient_map:
            gradient_node.fill_presentation_attributes(name, value)

    gradient_children = element.childNodes

    # Default SVG gradient offset is the previous largest offset.
    greatest_offset = 0.0
    for i in range(gradient_children.length):
        node = gradient_children[i]
        node_name = node.nodeName
        if node_name == "stop":
            stop_attr = node.attributes
            # Default SVG gradient stop color is black.
            color = "rgb(0,0,0)"
            # Default SVG gradient stop opacity is 1.
            opacity = "1"
            for k in range(stop_attr.length):
                stop_item = stop_attr.item(k)
                name = stop_item.nodeName
                value = stop_item.nodeValue
                try:
                    if name == "offset":
                        # If a gradient's value is not greater than all previous offset
                        # values, then the offset value is adjusted to be equal to
                        # the largest of all previous offset values.
                        greatest_offset = extract_offset(value, greatest_offset)
                    elif name == "stop-color":
                        color = value
                    elif name == "stop-opacity":
                        opacity = value
                    elif name == "style":
                        parts = value.split(";")
                        for attr in parts:
                            split_attribute = attr.split(":")
                            if len(split_attribute) == 2:
                                if attr.startswith("stop-color"):
                                    color = split_attribute[1]
                                elif attr.startswith("stop-opacity"):
                                    opacity = split_attribute[1]
                except ValueError as e:
                    msg = f"Invalid attribute value: {name}=\"{value}\""
                    svg.log_error(msg, node)

            offset = format_float_value(greatest_offset)
            vd_color = gradient_node.color_svg_to_vd(color, "#000000")
            if vd_color:
                color = vd_color
            gradient_node.add_gradient_stop(color, offset, opacity)

def extract_offset(offset: str, greatest_offset: float) -> float:
    x = 0.0
    if offset.endswith("%"):
        x = float(offset[:-1]) / 100
    else:
        x = float(offset)
    # Gradient offset values must be between 0 and 1 or 0% and 100%.
    x = min(1, max(x, 0))
    return max(x, greatest_offset)

def extract_group_node(svg_tree: SvgTree, child_group: SvgGroupNode, current_group: SvgGroupNode):
    attributes = child_group.get_document_element().attributes
    for j in range(attributes.length):
        n = attributes.item(j)
        name = n.nodeName
        value = n.nodeValue
        if name in (SVG_CLIP_PATH, SVG_MASK):
            if value:
                svg_tree.add_clip_path_affected_node(child_group, current_group, value)
        elif name == "class":
            if value:
                svg_tree.add_affected_node_to_style_class("." + value, child_group)

def extract_style_node(svg_tree: SvgTree, current_node: Node):
    a = current_node.childNodes
    style_data = ""
    for j in range(a.length):
        n = a[j]
        if n.nodeType == Node.CDATA_SECTION_NODE or a.length == 1:
            style_data = n.nodeValue

    if style_data:
        # Separate each of the classes.
        class_data = style_data.split("}")
        for a_class_data in class_data:
            # Separate the class name from the attribute values.
            split_class_data = a_class_data.split("\\{")
            if len(split_class_data) < 2:
                # When the class info is empty, then skip.
                continue

            class_name = split_class_data[0].strip()
            style_attr = split_class_data[1].strip()
            # Separate multiple classes if necessary.
            split_class_names = class_name.split(",")
            for split_class_name in split_class_names:
                style_attr_temp = style_attr
                class_name = split_class_name.strip()
                # Concatenate the attributes to existing attributes.
                existing = svg_tree.get_style_class_attr(class_name)
                if existing:
                    style_attr_temp += ';' + existing
                svg_tree.add_style_class_to_tree(class_name, style_attr_temp)

def process_id_name(svg_tree: SvgTree, node: SvgGroupNode):
    id_attr = node.get_attribute_value("id")
    if id_attr:
        svg_tree.add_id_to_map(id_attr, node)

def extract_use_node(svg_tree: SvgTree, use_group_node: SvgGroupNode, current_node: Node) -> bool:
    attributes = current_node.attributes
    x = 0.0
    y = 0.0
    id_value = None
    for j in range(attributes.length):
        n = attributes.item(j)
        name = n.nodeName
        value = n.nodeValue
        if name == SVG_HREF:
            id_value = get_id_from_reference(value)
        elif name == SVG_XLINK_HREF and id_value is None:
            id_value = get_id_from_reference(value)
        elif name == "x":
            x = float(value)
        elif name == "y":
            y = float(value)
        elif name in presentation_map:
            use_group_node.fill_presentation_attributes(name, value)

    use_transform = (1, 0, 0, 1, x, y)  # AffineTransform in row-major order
    defined_node = svg_tree.get_svg_node_from_id(id_value) if id_value else None

    if defined_node is None:
        if id_value is not None and not svg_tree.is_id_ignored(id_value):
            svg_tree.log_error("Referenced id not found", current_node)
    else:
        if defined_node in svg_tree.get_pending_use_set():
            # Cannot process useGroupNode yet, because definedNode it depends upon hasn't been
            # processed.
            return False

        copied_node = defined_node.deep_copy()
        use_group_node.add_child(copied_node)
        for key, value in use_group_node.vd_attributes_map.items():
            copied_node.fill_presentation_attributes(key, value)
        use_group_node.fill_empty_attributes(use_group_node.vd_attributes_map)
        use_group_node.transform_if_needed(use_transform)

    return True

def get_id_from_reference(value: str) -> str:
    return value[1:] if value else ""

def handle_clip_path(svg: SvgTree, child: SvgNode, current_group: Optional[SvgGroupNode], value: Optional[str]):
    if current_group is None or value is None:
        return

    clip_name = get_clip_path_name(value)
    if clip_name is None:
        return

    clip_node = svg.get_svg_node_from_id(clip_name)
    if clip_node is None:
        return

    if not isinstance(clip_node, SvgClipPathNode):
        return

    clip_copy = clip_node.deep_copy()

    current_group.replace_child(child, clip_copy)
    clip_copy.add_affected_node(child)
    clip_copy.set_clip_path_node_attributes()

def get_clip_path_name(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None

    start_pos = s.find('#')
    end_pos = s.find(')', start_pos + 1)
    if end_pos < 0:
        end_pos = len(s)
    return s[start_pos + 1:end_pos].strip()

def extract_all_items_as(svg: SvgTree, child: SvgLeafNode, current_item: Node, current_group: SvgGroupNode):
    parent_node = current_item.parentNode

    has_node_attr = False
    style_content = ""
    style_content_builder = []
    nothing_to_display = False

    while parent_node and parent_node.nodeName == "g":
        # Parse the group's attributes.
        logger.debug("Printing current parent")
        println_common(parent_node)

        attr = parent_node.attributes
        node_attr = attr.getNamedItem(SVG_STYLE)
        # Search for the "display:none", if existed, then skip this item.
        if node_attr:
            style_content_builder.append(node_attr.textContent)
            style_content_builder.append(';')
            style_content = "".join(style_content_builder)
            logger.debug(f"styleContent is :{style_content} at number group ")
            if "display:none" in style_content:
                logger.debug("Found none style, skip the whole group")
                nothing_to_display = True
                break
            else:
                has_node_attr = True

        display_attr = attr.getNamedItem(SVG_DISPLAY)
        if display_attr and display_attr.nodeValue == "none":
            logger.debug("Found display:none style, skip the whole group")
            nothing_to_display = True
            break

        parent_node = parent_node.parentNode

    if nothing_to_display:
        # Skip this current whole item.
        return

    logger.debug("Print current item")
    println_common(current_item)

    if has_node_attr and style_content:
        add_style_to_path(child, style_content)

    if current_item.nodeName == SVG_PATH:
        extract_path_item(svg, child, current_item, current_group)
    elif current_item.nodeName == SVG_RECT:
        extract_rect_item(svg, child, current_item, current_group)
    elif current_item.nodeName == SVG_CIRCLE:
        extract_circle_item(svg, child, current_item, current_group)
    elif current_item.nodeName in (SVG_POLYGON, SVG_POLYLINE):
        extract_poly_item(svg, child, current_item, current_group)
    elif current_item.nodeName == SVG_LINE:
        extract_line_item(svg, child, current_item, current_group)
    elif current_item.nodeName == SVG_ELLIPSE:
        extract_ellipse_item(svg, child, current_item, current_group)

    # Add the type of node as a style class name for child.
    svg.add_affected_node_to_style_class(current_item.nodeName, child)

def println_common(n: Node):
    logger.debug(f' nodeName="{n.nodeName}"')

    val = n.namespaceURI
    if val:
        logger.debug(f' uri="{val}"')

    val = n.prefix
    if val:
        logger.debug(f' pre="{val}"')

    val = n.localName
    if val:
        logger.debug(f' local="{val}"')

    val = n.nodeValue
    if val:
        logger.debug(" nodeValue=")
        if val.strip():
            logger.debug(f'"{n.nodeValue}"')
        else:
            # Whitespace
            logger.debug("[WS]")

def extract_poly_item(svg_tree: SvgTree, child: SvgLeafNode, current_group_node: Node,
                      current_group: SvgGroupNode):
    logger.debug("Polyline or Polygon found" + current_group_node.textContent)
    if current_group_node.nodeType == Node.ELEMENT_NODE:
        attributes = current_group_node.attributes

        for item_index in range(attributes.length):
            n = attributes.item(item_index)
            name = n.nodeName
            value = n.nodeValue
            try:
                if name == SVG_STYLE:
                    add_style_to_path(child, value)
                elif name in presentation_map:
                    child.fill_presentation_attributes(name, value)
                elif name in (SVG_CLIP_PATH, SVG_MASK):
                    svg_tree.add_clip_path_affected_node(child, current_group, value)
                elif name == SVG_POINTS:
                    builder = PathBuilder()
                    split = SPACE_OR_COMMA.split(value)
                    base_x = float(split[0])
                    base_y = float(split[1])
                    builder.absolute_move_to(base_x, base_y)
                    for j in range(2, len(split), 2):
                        x = float(split[j])
                        y = float(split[j + 1])
                        builder.relative_line_to(x - base_x, y - base_y)
                        base_x = x
                        base_y = y
                    if current_group_node.nodeName == SVG_POLYGON:
                        builder.relative_close()
                    child.set_path_data(builder.to_string())
                elif name == "class":
                    svg_tree.add_affected_node_to_style_class(f"{current_group_node.nodeName}.{value}", child)
                    svg_tree.add_affected_node_to_style_class("." + value, child)

            except (ValueError, IndexError) as e:
                svg_tree.log_error(f'Invalid value of "{name}" attribute', n)

def extract_rect_item(svg: SvgTree, child: SvgLeafNode, current_group_node: Node, current_group: SvgGroupNode):
    logger.debug("Rect found" + current_group_node.textContent)

    if current_group_node.nodeType == Node.ELEMENT_NODE:
        x = 0.0
        y = 0.0
        width = float('nan')
        height = float('nan')
        rx = 0.0
        ry = 0.0

        attributes = current_group_node.attributes
        pure_transparent = False
        for j in range(attributes.length):
            n = attributes.item(j)
            name = n.nodeName
            value = n.nodeValue
            try:
                if name == SVG_STYLE:
                    add_style_to_path(child, value)
                    if "opacity:0;" in value:
                        pure_transparent = True
                elif name in presentation_map:
                    child.fill_presentation_attributes(name, value)
                elif name in (SVG_CLIP_PATH, SVG_MASK):
                    svg.add_clip_path_affected_node(child, current_group, value)
                elif name == "x":
                    x = svg.parse_x_value(value)
                elif name == "y":
                    y = svg.parse_y_value(value)
                elif name == "rx":
                    rx = svg.parse_x_value(value)
                elif name == "ry":
                    ry = svg.parse_y_value(value)
                elif name == "width":
                    width = svg.parse_x_value(value)
                elif name == "height":
                    height = svg.parse_y_value(value)
                elif name == "class":
                    svg.add_affected_node_to_style_class("rect." + value, child)
                    svg.add_affected_node_to_style_class("." + value, child)
            except ValueError as e:
                msg = f"Invalid attribute value: {name}=\"{value}\""
                svg.log_error(msg, current_group_node)

        if (not pure_transparent
                and not math.isnan(x)
                and not math.isnan(y)
                and not math.isnan(width)
                and not math.isnan(height)):
            builder = PathBuilder()
            if rx <= 0 and ry <= 0:
                # "M x, y h width v height h -width z"
                builder.absolute_move_to(x, y)
                builder.relative_horizontal_to(width)
                builder.relative_vertical_to(height)
                builder.relative_horizontal_to(-width)
            else:
                # Refer to http://www.w3.org/TR/SVG/shapes.html#RectElement
                assert rx > 0 or ry > 0
                if ry == 0:
                    ry = rx
                elif rx == 0:
                    rx = ry
                if rx > width / 2:
                    rx = width / 2
                if ry > height / 2:
                    ry = height / 2

                builder.absolute_move_to(x + rx, y)
                builder.absolute_line_to(x + width - rx, y)
                builder.absolute_arc_to(rx, ry, False, False, True, x + width, y + ry)
                builder.absolute_line_to(x + width, y + height - ry)

                builder.absolute_arc_to(rx, ry, False, False, True, x + width - rx, y + height)
                builder.absolute_line_to(x + rx, y + height)

                builder.absolute_arc_to(rx, ry, False, False, True, x, y + height - ry)
                builder.absolute_line_to(x, y + ry)
                builder.absolute_arc_to(rx, ry, False, False, True, x + rx, y)

            builder.relative_close()
            child.set_path_data(builder.to_string())

def extract_circle_item(svg: SvgTree, child: SvgLeafNode, current_group_node: Node,
                        current_group: SvgGroupNode):
    logger.debug("circle found" + current_group_node.textContent)

    if current_group_node.nodeType == Node.ELEMENT_NODE:
        cx = 0.0
        cy = 0.0
        radius = 0.0

        a = current_group_node.attributes
        pure_transparent = False
        for j in range(a.length):
            n = a.item(j)

            name = n.nodeName
            value = n.nodeValue
            if name == SVG_STYLE:
                add_style_to_path(child, value)
                if "opacity:0;" in value:
                    pure_transparent = True
            elif name in presentation_map:
                child.fill_presentation_attributes(name, value)
            elif name in (SVG_CLIP_PATH, SVG_MASK):
                svg.add_clip_path_affected_node(child, current_group, value)
            elif name == "cx":
                cx = float(value)
            elif name == "cy":
                cy = float(value)
            elif name == "r":
                radius = float(value)
            elif name == "class":
                svg.add_affected_node_to_style_class("circle." + value, child)
                svg.add_affected_node_to_style_class("." + value, child)

        if not pure_transparent and not math.isnan(cx) and not math.isnan(cy):
            # "M cx cy m -r, 0 a r,r 0 1,1 (r * 2),0 a r,r 0 1,1 -(r * 2),0"
            builder = PathBuilder()
            builder.absolute_move_to(cx, cy)
            builder.relative_move_to(-radius, 0)
            builder.relative_arc_to(radius, radius, False, True, True, 2 * radius, 0)
            builder.relative_arc_to(radius, radius, False, True, True, -2 * radius, 0)
            child.set_path_data(builder.to_string())

def extract_ellipse_item(svg: SvgTree, child: SvgLeafNode, current_group_node: Node,
                         current_group: SvgGroupNode):
    logger.debug("ellipse found" + current_group_node.textContent)

    if current_group_node.nodeType == Node.ELEMENT_NODE:
        cx = 0.0
        cy = 0.0
        rx = 0.0
        ry = 0.0

        a = current_group_node.attributes
        pure_transparent = False
        for j in range(a.length):
            n = a.item(j)
            name = n.nodeName
            value = n.nodeValue
            if name == SVG_STYLE:
                add_style_to_path(child, value)
                if "opacity:0;" in value:
                    pure_transparent = True
            elif name in presentation_map:
                child.fill_presentation_attributes(name, value)
            elif name in (SVG_CLIP_PATH, SVG_MASK):
                svg.add_clip_path_affected_node(child, current_group, value)
            elif name == "cx":
                cx = float(value)
            elif name == "cy":
                cy = float(value)
            elif name == "rx":
                rx = float(value)
            elif name == "ry":
                ry = float(value)
            elif name == "class":
                svg.add_affected_node_to_style_class("ellipse." + value, child)
                svg.add_affected_node_to_style_class("." + value, child)

        if not pure_transparent and not math.isnan(cx) and not math.isnan(cy) and rx > 0 and ry > 0:
            # "M cx -rx, cy a rx,ry 0 1,0 (rx * 2),0 a rx,ry 0 1,0 -(rx * 2),0"
            builder = PathBuilder()
            builder.absolute_move_to(cx - rx, cy)
            builder.relative_arc_to(rx, ry, False, True, False, 2 * rx, 0)
            builder.relative_arc_to(rx, ry, False, True, False, -2 * rx, 0)
            builder.relative_close()
            child.set_path_data(builder.to_string())

def extract_line_item(svg: SvgTree, child: SvgLeafNode, current_group_node: Node,
                      current_group: SvgGroupNode):
    logger.debug("line found" + current_group_node.textContent)

    if current_group_node.nodeType == Node.ELEMENT_NODE:
        x1 = 0.0
        y1 = 0.0
        x2 = 0.0
        y2 = 0.0

        a = current_group_node.attributes
        pure_transparent = False
        for j in range(a.length):
            n = a.item(j)
            name = n.nodeName
            value = n.nodeValue
            if name == SVG_STYLE:
                add_style_to_path(child, value)
                if "opacity:0;" in value:
                    pure_transparent = True
            elif name in presentation_map:
                child.fill_presentation_attributes(name, value)
            elif name in (SVG_CLIP_PATH, SVG_MASK):
                svg.add_clip_path_affected_node(child, current_group, value)
            elif name == "x1":
                x1 = float(value)
            elif name == "y1":
                y1 = float(value)
            elif name == "x2":
                x2 = float(value)
            elif name == "y2":
                y2 = float(value)
            elif name == "class":
                svg.add_affected_node_to_style_class("line." + value, child)
                svg.add_affected_node_to_style_class("." + value, child)

        if (not pure_transparent
                and not math.isnan(x1)
                and not math.isnan(y1)
                and not math.isnan(x2)
                and not math.isnan(y2)):
            # "M x1, y1 L x2, y2"
            builder = PathBuilder()
            builder.absolute_move_to(x1, y1)
            builder.absolute_line_to(x2, y2)
            child.set_path_data(builder.to_string())

def extract_path_item(svg: SvgTree, child: SvgLeafNode, current_group_node: Node,
                      current_group: SvgGroupNode):
    logger.debug("Path found " + current_group_node.textContent)

    if current_group_node.nodeType == Node.ELEMENT_NODE:
        a = current_group_node.attributes
        for j in range(a.length):
            n = a.item(j)
            name = n.nodeName
            value = n.nodeValue
            if name == SVG_STYLE:
                add_style_to_path(child, value)
            elif name in presentation_map:
                child.fill_presentation_attributes(name, value)
            elif name in (SVG_CLIP_PATH, SVG_MASK):
                svg.add_clip_path_affected_node(child, current_group, value)
            elif name == SVG_D:
                path_data = re.sub(r"(\d)-", r"\1,-", value)
                child.set_path_data(path_data)
            elif name == "class":
                svg.add_affected_node_to_style_class("path." + value, child)
                svg.add_affected_node_to_style_class("." + value, child)

def add_style_to_path(path: SvgNode, value: Optional[str]):
    logger.debug("Style found is " + str(value))
    if value:
        parts = value.split(";")
        for k in range(len(parts) - 1, -1, -1):
            sub_style = parts[k]
            name_value = sub_style.split(":")
            if len(name_value) == 2 and name_value[0] and name_value[1]:
                attr = name_value[0].strip()
                val = name_value[1].strip()
                if attr in presentation_map:
                    path.fill_presentation_attributes(attr, val)
                elif attr == SVG_OPACITY:
                    # TODO: This is hacky, since we don't have a group level android:opacity.
                    #       This only works when the paths don't overlap.
                    path.fill_presentation_attributes(SVG_FILL_OPACITY, name_value[1])

                # We need to handle a clip-path or a mask within the style in a different way
                # than other styles. We treat it as an attribute clip-path = "#url(name)".
                if attr in (SVG_CLIP_PATH, SVG_MASK):
                    parent_node = path.get_tree().find_parent(path)
                    if parent_node:
                        path.get_tree().add_clip_path_affected_node(path, parent_node, val)

def write_file(out_stream, svg_tree: SvgTree):
    svg_tree.write_xml(out_stream)

def parse_svg_to_xml(input_svg: str, out_stream) -> str:
    """
    Converts a SVG file into VectorDrawable's XML content, if no error is found.

    :param input_svg: the input SVG file
    :param out_stream: the converted VectorDrawable's content. This can be empty if there is any
           error found during parsing
    :return: the error message that combines all logged errors and warnings, or an empty string if
           there were no errors
    """
    svg_tree = parse(input_svg)
    if svg_tree.get_has_leaf_node():
        write_file(out_stream, svg_tree)
    return svg_tree.get_error_message()
