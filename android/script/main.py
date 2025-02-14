import argparse
import re
import xml.etree.ElementTree as ET

from devbricksx.common.parser import append_common_developer_options_to_parse, append_common_file_options_to_parse
from devbricksx.development.log import debug, set_debug_enabled, set_silent_enabled, info, warn, error


def format_float(value):
    """
    Formats a float value, removing the decimal part if it's zero.
    """
    if value == int(value):
        return str(int(value))
    return str(value)

def element_to_android_path(element, viewport_height):
    """
    Converts an SVG element (path, rect, line) to Android VectorDrawable path data.

    Args:
        element: The ElementTree element (e.g., path, rect, line).
        viewport_height: The height of the SVG viewport, used for Y-flipping.

    Returns:
        The Android VectorDrawable path data string, or None if element is not supported.
    """
    android_path_segments = []
    tag = element.tag.split('}')[-1]
    fill_color = element.attrib.get('fill') # Get fill attribute

    info(f"processing tag: {tag}")
    if tag == 'path':
        path_data = element.attrib.get('d')
        if not path_data:
            return None  # Skip if no path data

        commands = re.findall(r"([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)", path_data)

        for command, values_str in commands:
            # Insert space around '-' if it's between digits, then replace comma with space, and split by space
            values_str_fixed = re.sub(r"(\d)-(\d)", r"\1 -\2", values_str.strip()).replace(',', ' ')
            value_tokens = values_str_fixed.split()

            values = []
            for token in value_tokens:
                if token:
                    try:
                        values.append(float(token))
                    except ValueError:
                        print(f"Warning: Could not convert path token '{token}' to float in command {command}")
                        continue

            android_command = command
            android_values = []
            i = 0
            value_count = len(values)

            while i < value_count:
                try:
                    if command in ('M', 'L'):  # Absolute coordinates - 2 values
                        x = values[i]
                        y = values[i + 1]
                        android_values.extend([x, viewport_height + y])
                        i += 2
                    elif command in ('m', 'l'):  # Absolute coordinates - 2 values
                        x = values[i]
                        y = values[i + 1]
                        android_values.extend([x, y])
                        i += 2
                    elif command == 'Q':  # Quadratic Bezier - 4 values
                        x1 = values[i]
                        y1 = values[i + 1]
                        x = values[i + 2]
                        y = values[i + 3]
                        android_values.extend([x1, y1, x, y])  # No Y flip for Q command now, as per requirement.
                        i += 4
                    elif command in ('q'):
                        x1 = values[i]
                        y1 = values[i + 1]
                        x = values[i + 2]
                        y = values[i + 3]
                        android_values.extend([x1, y1, x, y])  # No Y flip for Q command now, as per requirement.
                        i += 4
                    elif command in ('t'):  # Relative Quadratic Bezier - 4 values
                        x = values[i]
                        y = values[i + 1]
                        android_values.extend([x, y])
                        i += 2
                    elif command == 'T':  # Smooth Quadratic Bezier - 2 values (Corrected for 'T')
                        x = values[i]
                        y = values[i + 1]
                        android_values.extend([x, viewport_height + y])
                        i += 2
                    elif command in ('h'):  # relative horizontal line - 1 value
                        x = values[i]
                        android_values.append(x)  # No change in x
                        i += 1
                    elif command in ('v'):  # relative vertical line - 1 value
                        y = values[i]
                        android_values.append(y)  # Invert relative y
                        i += 1
                    elif command.upper() in ('Z'):  # Close path - 0 values
                        pass  # No values for Z


                    elif command.upper() in ('C', 'S'):  # Cubic Bezier - 6 values
                        x1 = values[i]
                        y1 = values[i + 1]
                        x2 = values[i + 2]
                        y2 = values[i + 3]
                        x = values[i + 4]
                        y = values[i + 5]
                        android_values.extend(
                            [x1, viewport_height - y1, x2, viewport_height - y2, x, viewport_height - y])
                        i += 6
                    elif command == 'Q':  # Quadratic Bezier - 4 values
                        x1 = values[i]
                        y1 = values[i + 1]
                        x = values[i + 2]
                        y = values[i + 3]
                        android_values.extend([x1, y1, x, y])  # No Y flip for Q command now, as per requirement.
                        i += 4

                    elif command.upper() == 'A':  # Arc command - 7 values
                        android_values.extend(
                            [values[i], values[i + 1], values[i + 2], values[i + 3], values[i + 4], values[i + 5],
                             960 - values[i + 6]])
                        i += 7
                    elif command.upper() in ('V'):  # Absolute vertical line - 1 value
                        y = values[i]
                        android_values.append(y)
                        i += 1
                    elif command.upper() in ('H'):  # Absolute horizontal line - 1 value
                        x = values[i]
                        android_values.append(x)
                        i += 1
                    elif command.lower() in ('m', 'l'):  # Relative coordinates - 2 values
                        x = values[i]
                        y = values[i + 1]
                        android_values.extend([x, -y])  # Invert relative y
                        i += 2
                    elif command.lower() in ('c', 's'):  # Relative Cubic Bezier - 6 values
                        x1 = values[i]
                        y1 = values[i + 1]
                        x2 = values[i + 2]
                        y2 = values[i + 3]
                        x = values[i + 4]
                        y = values[i + 5]
                        android_values.extend([x1, -y1, x2, -y2, x, -y])  # Invert relative y
                        i += 6
                    elif command.lower() == 'a':  # Relative Arc command - 7 values
                        android_values.extend(
                            [values[i], values[i + 1], values[i + 2], values[i + 3], values[i + 4], values[i + 5],
                             -values[i + 6]])  # Invert relative y for last value? - check spec!
                        i += 7
                except IndexError:
                    print(
                        f"Warning: Insufficient values for command '{command}'. Skipping remaining part of this command.")
                    break
            android_path_segments.append(android_command + ",".join([format_float(v) for v in android_values]))
        ret_val = ("".join(android_path_segments), fill_color)
        return ret_val

    elif tag == 'rect':
        x = float(element.attrib.get('x', 0))
        y = float(element.attrib.get('y', 0))
        width = float(element.attrib.get('width', 0))
        height = float(element.attrib.get('height', 0))
        rx = float(element.attrib.get('rx', 0))
        ry = float(element.attrib.get('ry', 0))

        if rx == 0 and ry == 0:  # Simple rectangle
            android_path_segments.extend([
                f"M{format_float(x)},{format_float(viewport_height + y)}",
                f"H{format_float(x + width)}",
                f"V{format_float(viewport_height - (y + height))}",
                f"H{format_float(x)}",
                "Z"
            ])
        else:  # Rounded rectangle (basic approximation, might need more sophisticated arc handling for perfect round corners)
            android_path_segments.extend([
                f"M{format_float(x + rx)},{format_float(viewport_height - y)}",
                f"H{format_float(x + width - rx)}",
                f"q{format_float(rx)},0 {format_float(rx)},{format_float(ry)}",  # Approximate top-right corner
                f"V{format_float(viewport_height - (y + height - ry))}",
                f"q0,{format_float(ry)} {format_float(-rx)},{format_float(ry)}",  # Approximate bottom-right corner
                f"H{format_float(x + rx)}",
                f"q{format_float(-rx)},0 {format_float(-rx)},{format_float(-ry)}",  # Approximate bottom-left corner
                f"V{format_float(viewport_height - (y + ry))}",
                f"q0,{format_float(-ry)} {format_float(rx)},{format_float(-ry)}",  # Approximate top-left corner
                "Z"
            ])
        ret_val = ("".join(android_path_segments), fill_color)
        return ret_val

    elif tag == 'line':
        x1 = float(element.attrib.get('x1', 0))
        y1 = float(element.attrib.get('y1', 0))
        x2 = float(element.attrib.get('x2', 0))
        y2 = float(element.attrib.get('y2', 0))
        android_path_segments.extend([
            f"M{format_float(x1)},{format_float(viewport_height - y1)}",
            f"L{format_float(x2)},{format_float(viewport_height - y2)}"
        ])
        ret_val = ("".join(android_path_segments), fill_color)
        return ret_val

    ret_val = (None, None)
    return ret_val

def convert_svg_to_vector(input_file, output_file):
    """
    Converts an SVG file to an Android VectorDrawable XML file, handling paths, rects, and lines.
    Parses and applies fill color from SVG.
    """
    viewport_width = 30  # Default viewport values, matching the provided SVG
    viewport_height = 30
    svg_namespace = "{http://www.w3.org/2000/svg}" # Define the SVG namespace

    try:
        tree = ET.parse(input_file)
        root = tree.getroot()
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return False
    except ET.ParseError as e:
        print(f"Error parsing input file '{input_file}': {e}")
        return False
    except Exception as e:
        print(f"Error reading input file '{input_file}': {e}")
        return False


    # Extract viewBox from SVG root element
    viewbox_attr = root.attrib.get('viewBox')
    if viewbox_attr:
        viewbox_values = [float(v) for v in viewbox_attr.strip().split()]
        if len(viewbox_values) == 4:
            viewport_width = viewbox_values[2]
            viewport_height = viewbox_values[3]
        else:
            print("Warning: viewBox attribute does not contain 4 values. Using default viewport 30x30.")
    else:
        print("Warning: viewBox attribute not found in SVG. Using default viewport 30x30.")

    svg_fill_color = root.attrib.get('fill')
    info(f'svg_fill_color: {svg_fill_color}')
    if svg_fill_color is None:
        svg_fill_color = "#fff"

    android_path_data_segments = []
    fill_colors = {} # Dictionary to store fill colors, keyed by path segment index

    # Directly find path, rect, and line elements in the SVG namespace
    for element_tag in ['path', 'rect', 'line']:
        for index, element in enumerate(root.findall(f'.//{svg_namespace}{element_tag}')): # Use enumerate to track index
            return_value = element_to_android_path(element, viewport_height) # Get path data and fill color
            print(f"DEBUG: Return from element_to_android_path:", return_value) # Debug print
            android_path, fill_color = return_value # Unpack here
            if android_path:
                android_path_data_segments.append(android_path)
                if fill_color:
                    fill_colors[index] = fill_color # Store fill color if found
                else:
                    fill_colors[index] = svg_fill_color


    android_path_data = "".join(android_path_data_segments)


    vector_drawable_xml_lines = [f"<vector xmlns:android=\"http://schemas.android.com/apk/res/android\"",
                           f"    android:width=\"24dp\"",
                           f"    android:height=\"24dp\"",
                           f"    android:viewportWidth=\"{format_float(viewport_width)}\"",
                           f"    android:viewportHeight=\"{format_float(viewport_height)}\">"]

    path_data_segments = android_path_data_segments # Rename for clarity in loop
    for index, path_data in enumerate(path_data_segments):
        fill_color_attr = "" # Default no fill color attribute
        if index in fill_colors:
            fill_color_attr = f"      android:fillColor=\"{fill_colors[index]}\"" # Apply extracted fill color
        vector_drawable_xml_lines.append(f"  <path\n"
                                   f"      android:pathData=\"{path_data}\"\n"
                                   + fill_color_attr + # Add fill color attribute here
                                   f"      />") # Close path tag

    vector_drawable_xml_lines.append(f"</vector>") # Close vector tag
    vector_drawable_xml = "\n".join(vector_drawable_xml_lines)


    try:
        with open(output_file, 'w') as f_out:
            f_out.write(vector_drawable_xml)
        return True
    except Exception as e:
        print(f"Error writing to output file '{output_file}': {e}")
        return False

if __name__ == '__main__':
    ap = argparse.ArgumentParser()

    append_common_developer_options_to_parse(ap)
    append_common_file_options_to_parse(ap)
    args = ap.parse_args()

    set_debug_enabled(args.verbose)
    if args.silent:
        set_silent_enabled(True)

    info(f"Input:{args.input_file}")
    info(f"Output:{args.output_file}")

    convert_svg_to_vector(args.input_file, args.output_file)


