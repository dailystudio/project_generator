import argparse
import re

from devbricksx.common.parser import append_common_developer_options_to_parse, append_common_file_options_to_parse
from devbricksx.development.log import debug, set_debug_enabled, set_silent_enabled, info

def format_float(value):
    """
    Formats a float value, removing the decimal part if it's zero.
    """
    if value == int(value):
        return str(int(value))
    return str(value)

def svg_path_to_android_path(svg_path_data, viewport_height):
    """
    Converts SVG path data to Android VectorDrawable path data, flipping the Y-coordinate.

    Args:
        svg_path_data: The SVG path data string.

    Returns:
        The Android VectorDrawable path data string.
    """

    commands = re.findall(r"([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)", svg_path_data)
    android_path_segments = []

    for command, values_str in commands:
        # Insert space around '-' if it's between digits, then replace comma with space, and split by space
        values_str_fixed = re.sub(r"(\d)-(\d)", r"\1 -\2", values_str.strip()).replace(',', ' ')
        value_tokens = values_str_fixed.split()

        values = []
        for token in value_tokens:
            if token: # Ignore empty tokens
                try:
                    values.append(float(token))
                except ValueError:
                    print(f"Warning: Could not convert token '{token}' to float: {token} in command {command}")
                    continue # Skip problematic token

        android_command = command
        android_values = []

        i = 0
        value_count = len(values)  # Get the number of values extracted

        print(f"\nProcessing command: {command}, values_str: '{values_str}'") # Debug print
        print(f"Extracted values: {values}") # Debug print

        while i < value_count: # Use value_count to control the loop
            try: # Add try-except block for potential index errors
                if command in ('M', 'L'): # Absolute coordinates - 2 values
                    x = values[i]
                    y = values[i+1]
                    android_values.extend([x, viewport_height + y])
                    i += 2
                elif command in ('m', 'l'):  # Absolute coordinates - 2 values
                    x = values[i]
                    y = values[i + 1]
                    android_values.extend([x, y])
                    i += 2
                elif command == 'Q': # Quadratic Bezier - 4 values
                    x1 = values[i]
                    y1 = values[i+1]
                    x = values[i+2]
                    y = values[i+3]
                    android_values.extend([x1, y1, x, y]) # No Y flip for Q command now, as per requirement.
                    i += 4
                elif command in ('q'):
                    x1 = values[i]
                    y1 = values[i + 1]
                    x = values[i + 2]
                    y = values[i + 3]
                    android_values.extend([x1, y1, x, y])  # No Y flip for Q command now, as per requirement.
                    i += 4
                elif command in ('t'): # Relative Quadratic Bezier - 4 values
                    x = values[i]
                    y = values[i + 1]
                    android_values.extend([x, y])
                    i += 2
                elif command == 'T': # Smooth Quadratic Bezier - 2 values (Corrected for 'T')
                    x = values[i]
                    y = values[i+1]
                    android_values.extend([x, viewport_height + y])
                    i += 2
                elif command in ('h'): # relative horizontal line - 1 value
                    x = values[i]
                    android_values.append(x) # No change in x
                    i += 1
                elif command in ('v'): # relative vertical line - 1 value
                    y = values[i]
                    android_values.append(y) # Invert relative y
                    i += 1
                elif command.upper() in ('Z'): # Close path - 0 values
                    pass # No values for Z


                elif command.upper() in ('C', 'S'): # Cubic Bezier - 6 values
                    x1 = values[i]
                    y1 = values[i+1]
                    x2 = values[i+2]
                    y2 = values[i+3]
                    x = values[i+4]
                    y = values[i+5]
                    android_values.extend([x1, viewport_height - y1, x2, viewport_height - y2, x, viewport_height - y])
                    i += 6
                elif command == 'Q': # Quadratic Bezier - 4 values
                    x1 = values[i]
                    y1 = values[i+1]
                    x = values[i+2]
                    y = values[i+3]
                    android_values.extend([x1, y1, x, y]) # No Y flip for Q command now, as per requirement.
                    i += 4

                elif command.upper() == 'A': # Arc command - 7 values
                    android_values.extend([values[i], values[i+1], values[i+2], values[i+3], values[i+4], values[i+5], 960 - values[i+6]])
                    i += 7
                elif command.upper() in ('V'): # Absolute vertical line - 1 value
                    y = values[i]
                    android_values.append(y)
                    i += 1
                elif command.upper() in ('H'): # Absolute horizontal line - 1 value
                    x = values[i]
                    android_values.append(x)
                    i += 1
                elif command.lower() in ('m', 'l'): # Relative coordinates - 2 values
                    x = values[i]
                    y = values[i+1]
                    android_values.extend([x, -y]) # Invert relative y
                    i += 2
                elif command.lower() in ('c', 's'): # Relative Cubic Bezier - 6 values
                    x1 = values[i]
                    y1 = values[i+1]
                    x2 = values[i+2]
                    y2 = values[i+3]
                    x = values[i+4]
                    y = values[i+5]
                    android_values.extend([x1, -y1, x2, -y2, x, -y]) # Invert relative y
                    i += 6
                elif command.lower() == 'a': # Relative Arc command - 7 values
                    android_values.extend([values[i], values[i+1], values[i+2], values[i+3], values[i+4], values[i+5], -values[i+6]]) # Invert relative y for last value? - check spec!
                    i += 7
            except IndexError:
                print(f"Warning: Insufficient values for command '{command}'. Skipping remaining part of this command.")
                break # Break out of the inner while loop if index error occurs

        print(f"Android values: {android_values}") # Debug print
        android_path_segments.append(android_command + ",".join([format_float(v) for v in android_values])) # Use format_float here

    return "".join(android_path_segments)

def convert_svg_to_vector(input_file, output_file):
    """
    Converts an SVG file to an Android VectorDrawable XML file.

    Args:
        input_file: Path to the input SVG file.
        output_file: Path to the output Android VectorDrawable XML file.

    Returns:
        True if conversion was successful, False otherwise.
    """
    try:
        with open(input_file, 'r') as f_in:
            svg_content = f_in.read()
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return False
    except Exception as e:
        print(f"Error reading input file '{input_file}': {e}")
        return False

    # Extract viewBox from SVG content
    viewbox_match = re.search(r'<svg.*?viewBox="([^"]+)"', svg_content)
    if viewbox_match:
        viewbox_values = [float(v) for v in viewbox_match.group(1).strip().split()]
        if len(viewbox_values) == 4:
            viewport_width = viewbox_values[2]
            viewport_height = viewbox_values[3]
        else:
            print("Warning: viewBox attribute does not contain 4 values. Using default viewport 960x960.")
    else:
        print("Warning: viewBox attribute not found in SVG. Using default viewport 960x960.")

    # Extract path data from SVG content (assuming simple SVG structure like in the example)
    path_match = re.search(r'<path d="([^"]+)"', svg_content)
    if path_match:
        original_svg_path = path_match.group(1)
    else:
        print("Error: Could not find path data in the SVG content.")
        return False

    android_path_data = svg_path_to_android_path(original_svg_path, viewport_height)

    vector_drawable_xml = f"<vector xmlns:android=\"http://schemas.android.com/apk/res/android\"\n" \
                           f"    android:width=\"24dp\"\n" \
                           f"    android:height=\"24dp\"\n" \
                           f"    android:viewportWidth=\"960\"\n" \
                           f"    android:viewportHeight=\"960\">\n" \
                           f"  <path\n" \
                           f"      android:pathData=\"{android_path_data}\"\n" \
                           f"      android:fillColor=\"#5f6368\"/>\n" \
                           f"</vector>"

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


