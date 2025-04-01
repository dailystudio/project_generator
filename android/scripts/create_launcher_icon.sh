#!/bin/bash

convert_vector_xml() {
  local input_file="$1"
  local output_file="$2"
  local scale_percent="$3"

  local scale_factor=$(echo "scale=2; $scale_percent / 100" | bc)

  local original_svg=$(cat "$input_file")

  local vector_attrs=$(echo "$original_svg" | grep '<vector' | sed 's/.*<vector \(.*\)>.*/\1/')

  local viewport_width=$(echo "$vector_attrs" | grep 'android:viewportWidth' | sed 's/.*android:viewportWidth="\([^"]*\)".*/\1/')
  local viewport_width_value=$(echo "$viewport_width" | sed 's/android:viewportWidth="//' | sed 's/"//')

  local translate_x=$(echo "scale=2; (1 - $scale_factor) * $viewport_width_value / 2" | bc)
  local translate_y=$(echo "scale=2; (1 - $scale_factor) * $viewport_width_value / 2" | bc)

  local group_attrs="android:scaleX=\"$scale_factor\" android:scaleY=\"$scale_factor\" android:translateX=\"$translate_x\" android:translateY=\"$translate_y\""

  local content=$(echo "$original_svg" | sed -n '/<vector.*>/,/<\/vector>/ { /<vector.*>/d; /<\/vector>/d; p; }')

  local width=$(echo "$vector_attrs" | grep 'android:width' | sed 's/.*android:width="\([^"]*\)".*/\1/')
  local height=$(echo "$vector_attrs" | grep 'android:height' | sed 's/.*android:height="\([^"]*\)".*/\1/')

  local new_svg="<vector $vector_attrs>\n  <group $group_attrs>\n$content  </group>\n</vector>"

  echo -e "$new_svg" | xmllint --format - > "$output_file"
}

replace_vector_colors() {
  local input_file="$1"
  local output_file="$2"
  local new_color="$3"

  local original_xml=$(cat "$input_file")

  local replaced_xml=$(echo "$original_xml" | \
    sed -E "s/android:(fillColor|strokeColor)=\"([^\"]*)\"/android:\1=\"${new_color}\"/g")

  echo -e "$replaced_xml" | xmllint --format - > "$output_file"
}

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -f FG_IMAGE_FILE -o OUTPUT_DIR"
  echo "    This script will generate image assets of launcher icon for an Android application."
  echo ""
  echo "    -f FG_IMAGE_FILE:           the SVG File used as foreground"
  echo "    -o OUTPUT_DIR:              the output directory for assets"
  echo "    -c FG_COLOR:                the color used as foreground"
  echo "    -b BG_COLOR:                the color used as background"
  echo "    -s FG_SCALE:                the scale of foreground in composition"
  echo "    -q WEBP_QUALITY:            the quality of webp output"
  echo "    -p:                         use PNG format for mipmap assets"
  echo "    -h:                         display this message"
  echo
}

function exit_abnormal {
	print_usage
	exit 1
}

foreground=""
foreground_color=""
background="#008577"
scale=80
quality=90
png_format=false
output_dir=""

while getopts :f:c:b:s:q:o:phH opt; do
  case ${opt} in
    f)
      foreground=${OPTARG}
      ;;
    b)
      background=${OPTARG}
      ;;
    c)
      foreground_color=${OPTARG}
      ;;
    s)
      scale=${OPTARG}
      ;;
    q)
      quality=${OPTARG}
      ;;
    p)
      png_format=true
      ;;
    o)
      output_dir=${OPTARG}
      ;;
    h|H)
      print_usage
      exit 2
      ;;
    :)
      echo "[ERROR] $0: -${OPTARG} requires an argument."
      exit_abnormal
      ;;
    *)
      echo "[ERROR] $0: -${OPTARG} is unsuppported."
      exit_abnormal
      ;;
  esac
done

if [ -z "${foreground}" ] || [ -z "${output_dir}" ]; then
    echo "[ERROR] required options is missing."
    exit_abnormal
fi

if command -v magick &> /dev/null; then
    IMAGEMAGICK_CMD="magick"
elif command -v convert &> /dev/null; then
    IMAGEMAGICK_CMD="convert"
else
    echo "[ERROR] ImageMagick is NOT installed." >&2
    exit 1
fi

if command -v rsvg-convert &> /dev/null; then
    SVG_CONVERT_CMD="rsvg-convert"
else
    echo "[ERROR] rsvg-convert is NOT installed." >&2
    exit 1
fi

if ! [[ "$scale" =~ ^[1-9][0-9]?$|^100$ ]]; then
    echo "[ERROR] scale must be an integer between 1 and 100."
    exit 1
fi

if ! [[ "$quality" =~ ^[1-9][0-9]?$|^100$ ]]; then
    echo "[ERROR] quality must be an integer between 1 and 100."
    exit 1
fi

if ${png_format}; then
    format="PNG"
else
    format="WEBP"
    if [ -n "${quality}" ]; then
      echo "[WARN] WEBP quality will be ignored as using PNG format for mipmap assets."
    fi
fi

echo
echo "--------------- Code Generation for Android project ---------------"
echo "Icon Foreground:                [${foreground}]"
echo "Output Directory:               [${output_dir}]"
echo "ImageMagick Command:            [${IMAGEMAGICK_CMD}]"
echo "Icon Foreground Color:          [${foreground_color}]"
echo "Icon Foreground Scale:          [${scale}]"
echo "Icon Background:                [${background}]"
echo "DPI Assets Format:              [${format}]"
if ! ${png_format}; then
echo "Webp Compression Quality:       [${quality}]"
fi
echo "-------------------------------------------------------------------"

#temp_dir=$(mktemp -d)
temp_dir="./tmp"
mkdir -p "${temp_dir}"
mkdir -p "${temp_dir}/drawable-v24"

mkdir -p "${output_dir}"

background_asset="${temp_dir}/background.png"
foreground_asset="${temp_dir}/foreground.png"
foreground_scaled="${temp_dir}/foreground_scaled.svg"
composition_asset="${temp_dir}/composition.png"
compressed_asset="${temp_dir}/composition.webp"
rounded_mask_asset="${temp_dir}/rounded_mask.png"
circle_mask_asset="${temp_dir}/circle_mask.png"
composition_rounded_asset="${temp_dir}/rounded_output.png"
composition_circle_asset="${temp_dir}/circle_output.png"

dpi_types=("mdpi" "hdpi" "xhdpi" "xxhdpi" "xxxhdpi")
# Define corresponding DPI values
dpi_output_dimens=(48 72 96 144 192)
width=512
height=512
ic_launcher_fname="ic_launcher"
ic_launcher_round_fname="ic_launcher_round"
ic_launcher_playstore="ic_launcher-playstore.png"
ic_launcher_vector="ic_launcher_foreground.xml"

VECTOR_DRAWABLE_DIR=$(realpath "${temp_dir}/drawable-v24")
vector_asset="${VECTOR_DRAWABLE_DIR}/${ic_launcher_vector}"

echo "Generating background image: ${background_asset}"
$IMAGEMAGICK_CMD -size ${width}x${height} xc:"${background}" "${background_asset}"

echo "Generating foreground image: ${foreground_asset}"
#$IMAGEMAGICK_CMD "${foreground}" -background none "${foreground_asset}"
$SVG_CONVERT_CMD -w ${width} -h ${height} -b none "${foreground}" -o "${foreground_asset}"

if [ -n "${foreground_color}" ]; then
  echo "Tinting foreground color: ${foreground_color}"
  $IMAGEMAGICK_CMD "${foreground_asset}" \( -clone 0 -fill "${foreground_color}" -colorize 100% \) -compose Over -composite "${foreground_asset}"
fi

echo "Compositing foreground and background: ${composition_asset}"
$IMAGEMAGICK_CMD \
  "${background_asset}" \
  \( "${foreground_asset}" -resize "${scale}"% \) \
  -gravity center -composite "${composition_asset}"

$IMAGEMAGICK_CMD -size "${width}x${height}" xc:none -fill white \
    -draw "roundrectangle 0,0 $width,$height 50,50" "${rounded_mask_asset}"
$IMAGEMAGICK_CMD -size "${width}x${height}" xc:none -fill white \
    -draw "circle $((width/2)),$((height/2)) $((width/2)),0" "${circle_mask_asset}"

echo "Clipping to round shape: ${composition_rounded_asset}"
$IMAGEMAGICK_CMD "${composition_asset}" "${rounded_mask_asset}" -alpha off -compose CopyOpacity -composite "${composition_rounded_asset}"
echo "Clipping to circle shape: ${composition_circle_asset}"
$IMAGEMAGICK_CMD "${composition_asset}" "${circle_mask_asset}" -alpha off -compose CopyOpacity -composite "${composition_circle_asset}"

echo "Generating vector icon: ${vector_asset}"
OLD_PWD=${PWD}
cd "vd-tool"
./vd-tool.sh -i "${foreground}" -o "${vector_asset}" -d 108
cd ${OLD_PWD}
convert_vector_xml "${vector_asset}" "${vector_asset}" 40
if [ -n "${foreground_color}" ]; then
  echo "Tinting foreground color: ${foreground_color}"
  replace_vector_colors "${vector_asset}" "${vector_asset}"  "${foreground_color}"
fi

# Generating launcher icons for dpi
for i in "${!dpi_types[@]}"; do
    dpi="${dpi_types[$i]}"
    size="${dpi_output_dimens[$i]}"

    echo "Scaling to DPI: $dpi (${size}x${size})"
    mipmap_dir="${temp_dir}/mipmap-${dpi}"
    mkdir -p "${mipmap_dir}"

    icon_file_png="${mipmap_dir}/${ic_launcher_fname}.png"
    icon_round_file_png="${mipmap_dir}/${ic_launcher_round_fname}.png"
    icon_file_webp="${mipmap_dir}/${ic_launcher_fname}.webp"
    icon_round_file_webp="${mipmap_dir}/${ic_launcher_round_fname}.webp"

    $IMAGEMAGICK_CMD "${composition_circle_asset}" -resize "${size}x${size}" "${icon_file_png}"
    $IMAGEMAGICK_CMD "${composition_rounded_asset}" -resize "${size}x${size}" "${icon_round_file_png}"

    if [ "$format" = "WEBP" ]; then
      $IMAGEMAGICK_CMD "${icon_file_png}" -quality "${quality}" "${icon_file_webp}"
      $IMAGEMAGICK_CMD "${icon_round_file_png}" -quality "${quality}" "${icon_round_file_webp}"
      rm "${icon_file_png}"
      rm "${icon_round_file_png}"
    fi

done

playstore_asset="${temp_dir}/${ic_launcher_playstore}"

echo "Generating icon for Google Play: ${playstore_asset}"
cp "${composition_asset}" "${playstore_asset}"

echo "Cleanup intermediate resources ..."
rm ${foreground_asset}
rm ${background_asset}
rm ${composition_asset}
rm ${rounded_mask_asset}
rm ${circle_mask_asset}
rm ${composition_rounded_asset}
rm ${composition_circle_asset}

echo "Moving assets to target directory: ${output_dir}"
cp -a ${temp_dir}/* "${output_dir}"

rm -rf "${temp_dir}"