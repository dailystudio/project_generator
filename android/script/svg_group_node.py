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
from svg_node import *
from com.android.ide.common.vectordrawable.svg_node import Visitor, \
    VisitResult  # Assuming SvgNode is in svg_node.py

logger = logging.getLogger(__name__)


class SvgGroupNode(SvgNode):
    """Represents an SVG file's group element."""

    def __init__(self, svg_tree: "SvgTree", doc_node: Element, name: Optional[str] = None):
        super().__init__(svg_tree, doc_node, name)
        self.children: List[SvgNode] = []

    def deep_copy(self) -> "SvgGroupNode":
        new_instance = SvgGroupNode(self.get_tree(), self.document_element, self.get_name())
        new_instance.copy_from(self)
        return new_instance

    def copy_from(self: "SvgGroupNode", from_node: "SvgGroupNode"):
        super().copy_from(from_node)
        for child in from_node.children:
            self.add_child(child.deep_copy())

    def add_child(self, child: SvgNode):
        # Pass the presentation map down to the children, who can override the attributes.
        self.children.append(child)
        # The child has its own attributes map. But the parents can still fill some attributes
        # if they don't exist.
        child.fill_empty_attributes(self.vd_attributes_map)

    def replace_child(self, old_child: SvgNode, new_child: SvgNode):
        """
        Replaces an existing child node with a new one.

        :param old_child: the child node to replace
        :param new_child: the node to replace the existing child node with
        """
        try:
            index = self.children.index(old_child)
            self.children[index] = new_child
        except ValueError:
            raise ValueError("The child being replaced doesn't belong to this group")

    def dump_node(self, indent: str):
        # Print the current group.
        logger.debug(f"{indent}group: {self.get_name()}")

        # Then print all the children.
        for node in self.children:
            node.dump_node(indent + INDENT_UNIT)

    def find_parent(self, node: SvgNode) -> Optional["SvgGroupNode"]:
        """
        Finds the parent node of the input node.

        :return: the parent node, or None if node is not in the tree.
        """
        for n in self.children:
            if n == node:
                return self
            if n.is_group_node():
                parent = n.find_parent(node)
                if parent:
                    return parent
        return None

    def is_group_node(self) -> bool:
        return True

    def transform_if_needed(self, root_transform: Tuple[float, float, float, float, float, float]):
        for child in self.children:
            child.transform_if_needed(root_transform)

    def flatten(self, transform: Tuple[float, float, float, float, float, float]):
        for node in self.children:
            self.stacked_transform = self.concatenate_transform(transform, self.local_transform)
            node.flatten(self.stacked_transform)

    def validate(self):
        for node in self.children:
            node.validate()

    def write_xml(self, writer: io.StringIO, indent: str):
        for node in self.children:
            node.write_xml(writer, indent)

    def accept(self, visitor: Visitor) -> int:
        result = visitor.visit(self)
        if result == VisitResult.CONTINUE:
            for node in self.children:
                if node.accept(visitor) == VisitResult.ABORT:
                    return VisitResult.ABORT
        return VisitResult.CONTINUE if result == VisitResult.SKIP_CHILDREN else result

    def fill_presentation_attributes(self, name: str, value: str):
        super().fill_presentation_attributes(name, value)
        for n in self.children:
            # Group presentation attribute should not override child.
            if name not in n.vd_attributes_map:
                n.fill_presentation_attributes(name, value)